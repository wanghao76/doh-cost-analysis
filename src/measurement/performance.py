"""
DNS性能测量模块
================
对比传统DNS、DoT、DoH三种传输协议的查询性能。

论文对照:
    论文第4节 "Transport Comparison" 和第5节 "Overheads":
    1. 对比三种DNS传输协议(DNS/DoT/DoH)的查询响应时间
    2. 分析各协议层的开销（TCP握手、TLS握手、HTTP/2帧等）
    3. 多次重复查询取平均值，减少网络波动影响
    4. 区分冷启动（首次连接，含握手）和热启动（复用连接）的性能差异

    论文发现:
    - 传统DNS最快，因为只有UDP+DNS两层
    - DoT比传统DNS慢，因为额外的TCP和TLS握手开销
    - DoH比DoT略慢，因为还有HTTP/2层的开销
    - 但在热启动场景下（复用连接），DoH和DoT的差距大幅缩小
    - DoH相比DoT的优势在于可以复用HTTP/2连接的多路复用特性

测量指标:
    - 查询响应时间（ms）
    - 响应大小（bytes）
    - 成功率
    - 各协议间的开销对比
"""

import time
import statistics
from typing import List, Dict
from dataclasses import dataclass, field

from src.dns_client.traditional_dns import TraditionalDNSClient
from src.dns_client.dot_client import DoTClient
from src.dns_client.doh_client import DoHClient
from src.utils.helpers import QueryResult, load_config, save_results_to_csv


@dataclass
class PerformanceStats:
    """
    性能统计数据
    ==============
    对多次查询结果进行统计分析。

    属性:
        transport: 传输协议名称
        resolver: 解析器名称
        mean_ms: 平均耗时（毫秒）
        median_ms: 中位数耗时
        min_ms: 最小耗时
        max_ms: 最大耗时
        std_ms: 标准差
        success_rate: 成功率
        avg_response_size: 平均响应大小
        sample_count: 样本数量
    """
    transport: str
    resolver: str
    mean_ms: float = 0.0
    median_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    std_ms: float = 0.0
    success_rate: float = 0.0
    avg_response_size: float = 0.0
    sample_count: int = 0


class PerformanceMeasurer:
    """
    DNS性能测量器
    ==============
    执行多轮DNS查询并统计各协议的性能。

    参数:
        repeat: 每个域名每种协议的重复查询次数
        timeout: 单次查询超时时间（秒）
    """

    def __init__(self, repeat: int = 5, timeout: float = 10.0):
        self.repeat = repeat
        self.timeout = timeout

    def measure_all(self, domains: List[str] = None) -> Dict[str, List[QueryResult]]:
        """
        对所有配置的服务器和域名执行性能测量

        参数:
            domains: 要测试的域名列表，为None时从配置文件读取

        返回:
            按传输协议分组的查询结果字典
        """
        config = load_config()
        if domains is None:
            domains = config["test_domains"][:5]  # 默认取前5个域名

        all_results = {
            "DNS-UDP": [],
            "DoT": [],
            "DoH-POST": [],
            "DoH-GET": []
        }

        # 1. 测量传统DNS
        print("\n" + "=" * 60)
        print("【传统DNS (UDP) 性能测量】")
        print("=" * 60)
        for server in config["traditional_dns_servers"]:
            client = TraditionalDNSClient(
                server["ip"], server["name"], timeout=self.timeout
            )
            results = self._measure_client(client, domains, "query")
            all_results["DNS-UDP"].extend(results)

        # 2. 测量DoT
        print("\n" + "=" * 60)
        print("【DNS-over-TLS (DoT) 性能测量】")
        print("=" * 60)
        for server in config["dot_servers"]:
            client = DoTClient(
                server["ip"], server["name"],
                hostname=server["host"], timeout=self.timeout
            )
            results = self._measure_client(client, domains, "query")
            all_results["DoT"].extend(results)

        # 3. 测量DoH (POST)
        print("\n" + "=" * 60)
        print("【DNS-over-HTTPS (DoH POST) 性能测量】")
        print("=" * 60)
        for server in config["doh_servers"]:
            client = DoHClient(
                server["url"], server["name"], timeout=self.timeout
            )
            results = self._measure_client(client, domains, "query_post")
            all_results["DoH-POST"].extend(results)

        # 4. 测量DoH (GET)
        print("\n" + "=" * 60)
        print("【DNS-over-HTTPS (DoH GET) 性能测量】")
        print("=" * 60)
        for server in config["doh_servers"]:
            client = DoHClient(
                server["url"], server["name"], timeout=self.timeout
            )
            results = self._measure_client(client, domains, "query_get")
            all_results["DoH-GET"].extend(results)

        return all_results

    def _measure_client(self, client, domains: List[str],
                        method_name: str) -> List[QueryResult]:
        """
        对单个客户端执行多轮测量

        参数:
            client: DNS客户端实例
            domains: 域名列表
            method_name: 要调用的查询方法名

        返回:
            所有查询结果
        """
        results = []
        method = getattr(client, method_name)
        server_name = client.server_name

        for domain in domains:
            for i in range(self.repeat):
                result = method(domain)
                results.append(result)

                status_icon = "[OK]" if result.status == "success" else "[FAIL]"
                print(f"  {status_icon} [{server_name}] {domain} "
                      f"(第{i + 1}/{self.repeat}轮) "
                      f"-> {result.query_time_ms:.2f}ms")

                # 每次查询之间短暂等待，减少请求频率
                time.sleep(0.1)

        return results

    def calculate_stats(self, results: Dict[str, List[QueryResult]]) -> List[PerformanceStats]:
        """
        计算各协议的性能统计数据

        参数:
            results: 按传输协议分组的查询结果

        返回:
            PerformanceStats列表
        """
        stats_list = []

        for transport, transport_results in results.items():
            # 按解析器分组
            by_resolver = {}
            for r in transport_results:
                if r.resolver not in by_resolver:
                    by_resolver[r.resolver] = []
                by_resolver[r.resolver].append(r)

            for resolver, resolver_results in by_resolver.items():
                successful = [r for r in resolver_results if r.status == "success"]
                times = [r.query_time_ms for r in successful]
                sizes = [r.response_size for r in successful]

                stats = PerformanceStats(
                    transport=transport,
                    resolver=resolver,
                    sample_count=len(resolver_results),
                    success_rate=len(successful) / len(resolver_results) if resolver_results else 0.0,
                )

                if times:
                    stats.mean_ms = statistics.mean(times)
                    stats.median_ms = statistics.median(times)
                    stats.min_ms = min(times)
                    stats.max_ms = max(times)
                    stats.std_ms = statistics.stdev(times) if len(times) > 1 else 0.0
                    stats.avg_response_size = statistics.mean(sizes) if sizes else 0

                stats_list.append(stats)

        return stats_list

    def print_stats_summary(self, stats_list: List[PerformanceStats]):
        """
        打印性能统计摘要

        以表格形式展示各协议和解析器的性能统计数据。
        """
        print("\n" + "=" * 80)
        print("【性能统计摘要】")
        print("=" * 80)
        print(f"{'协议':<12} {'解析器':<12} {'平均(ms)':<12} {'中位数(ms)':<12} "
              f"{'最小(ms)':<12} {'最大(ms)':<12} {'成功率':<8}")
        print("-" * 80)

        for stats in stats_list:
            print(f"{stats.transport:<12} {stats.resolver:<12} "
                  f"{stats.mean_ms:<12.2f} {stats.median_ms:<12.2f} "
                  f"{stats.min_ms:<12.2f} {stats.max_ms:<12.2f} "
                  f"{stats.success_rate:<8.1%}")

    def measure_overhead(self, results: Dict[str, List[QueryResult]]) -> Dict[str, float]:
        """
        计算各加密DNS协议相对于传统DNS的额外开销

        论文的核心发现之一——量化DoH和DoT相比传统DNS的额外开销。

        返回:
            各协议的平均开销（毫秒）
        """
        # 计算每种传输的平均耗时
        avg_times = {}
        for transport, transport_results in results.items():
            successful = [r for r in transport_results if r.status == "success"]
            if successful:
                avg_times[transport] = statistics.mean(
                    [r.query_time_ms for r in successful]
                )

        baseline = avg_times.get("DNS-UDP", 0)
        overheads = {}

        print("\n" + "=" * 60)
        print("【协议开销分析】")
        print("=" * 60)
        print(f"  基准 (传统DNS UDP): {baseline:.2f}ms")

        for transport, avg_time in avg_times.items():
            overhead = avg_time - baseline
            overheads[transport] = overhead
            if transport != "DNS-UDP":
                print(f"  {transport}: {avg_time:.2f}ms (额外开销: +{overhead:.2f}ms, "
                      f"+{overhead / baseline * 100:.1f}%)" if baseline > 0 else
                      f"  {transport}: {avg_time:.2f}ms")

        return overheads
