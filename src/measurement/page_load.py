"""
网页加载时间测量模块
=====================
测量不同DNS传输协议对网页加载时间的影响。

论文对照:
    论文第5节 "Impact on Page Load Times":
    论文将DoH集成到Firefox浏览器中，测量使用不同DNS传输方式时的网页加载时间差异。
    
    我们采用模拟方式实现:
    1. 先用不同DNS协议解析域名获取IP
    2. 然后通过HTTP请求获取网页内容
    3. 将DNS解析时间和HTTP加载时间分开测量
    
    论文核心发现:
    - DoH带来的额外DNS解析延迟对整体网页加载时间影响很小
    - 因为现代网页的加载瓶颈在于资源下载、渲染等，DNS只占很小一部分
    - 使用HTTP/2连接复用后，后续DNS查询几乎不增加额外开销

测量指标:
    - DNS解析时间
    - HTTP内容下载时间
    - 总加载时间（DNS + HTTP）
"""

import time
import requests
import statistics
import urllib3
from typing import List, Dict
from dataclasses import dataclass, field

# 在纯实验测量场景下抑制SSL警告（仅影响HTTP时间测量部分）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.dns_client.traditional_dns import TraditionalDNSClient
from src.dns_client.dot_client import DoTClient
from src.dns_client.doh_client import DoHClient
from src.utils.helpers import Timer


@dataclass
class PageLoadResult:
    """
    网页加载测量结果
    ================

    属性:
        url: 目标URL
        transport: DNS传输协议
        resolver: DNS解析器名称
        dns_time_ms: DNS解析耗时（毫秒）
        http_time_ms: HTTP下载耗时（毫秒）
        total_time_ms: 总耗时（毫秒）
        page_size: 页面大小（字节）
        status: 状态（success/error）
        error_message: 错误信息
    """
    url: str
    transport: str
    resolver: str
    dns_time_ms: float = 0.0
    http_time_ms: float = 0.0
    total_time_ms: float = 0.0
    page_size: int = 0
    status: str = "success"
    error_message: str = ""


class PageLoadMeasurer:
    """
    网页加载时间测量器
    ===================
    测量使用不同DNS传输协议时的网页加载性能。

    方法:
    1. 使用指定的DNS协议解析域名
    2. 使用解析得到的IP地址请求网页
    3. 记录DNS解析时间和HTTP下载时间

    参数:
        repeat: 重复次数
        timeout: 超时时间（秒）
    """

    def __init__(self, repeat: int = 3, timeout: float = 10.0):
        self.repeat = repeat
        self.timeout = timeout

    def measure_page_load(self, url: str, transport: str = "DNS-UDP",
                          resolver_name: str = "Google") -> PageLoadResult:
        """
        测量单个URL的加载时间

        步骤:
        1. 从URL中提取域名
        2. 用指定DNS协议解析域名
        3. 用HTTP GET请求获取页面内容
        4. 汇总各阶段耗时

        参数:
            url: 目标URL
            transport: DNS传输协议
            resolver_name: 解析器名称

        返回:
            PageLoadResult
        """
        # 从URL提取域名
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.hostname

        try:
            # 阶段1: DNS解析
            dns_result = self._resolve(domain, transport, resolver_name)
            dns_time = dns_result.query_time_ms

            if dns_result.status != "success" or not dns_result.ip_addresses:
                return PageLoadResult(
                    url=url,
                    transport=transport,
                    resolver=resolver_name,
                    dns_time_ms=dns_time,
                    status="error",
                    error_message=f"DNS解析失败: {dns_result.error_message}"
                )

            # 阶段2: HTTP请求（使用原始URL，让系统DNS解析）
            http_timer = Timer()
            http_timer.start()
            # verify=False仅用于实验测量场景，避免环境证书链不完整导致失败
            response = requests.get(
                url, timeout=self.timeout, allow_redirects=True, verify=False
            )
            http_time = http_timer.stop()

            total_time = dns_time + http_time

            return PageLoadResult(
                url=url,
                transport=transport,
                resolver=resolver_name,
                dns_time_ms=dns_time,
                http_time_ms=http_time,
                total_time_ms=total_time,
                page_size=len(response.content),
                status="success"
            )

        except Exception as e:
            return PageLoadResult(
                url=url,
                transport=transport,
                resolver=resolver_name,
                status="error",
                error_message=str(e)
            )

    def _resolve(self, domain: str, transport: str, resolver_name: str):
        """
        使用指定的传输协议解析域名

        根据transport参数选择对应的DNS客户端进行查询。
        """
        if transport == "DNS-UDP":
            client = TraditionalDNSClient("8.8.8.8", resolver_name)
            return client.query(domain)
        elif transport == "DoT":
            client = DoTClient("8.8.8.8", resolver_name, hostname="dns.google")
            return client.query(domain)
        elif transport == "DoH-POST":
            client = DoHClient("https://dns.google/dns-query", resolver_name)
            return client.query_post(domain)
        elif transport == "DoH-GET":
            client = DoHClient("https://dns.google/dns-query", resolver_name)
            return client.query_get(domain)
        else:
            raise ValueError(f"不支持的传输协议: {transport}")

    def measure_all_transports(self, urls: List[str] = None) -> Dict[str, List[PageLoadResult]]:
        """
        对所有URL使用所有传输协议进行测量

        参数:
            urls: URL列表

        返回:
            按传输协议分组的测量结果
        """
        if urls is None:
            urls = [
                "https://example.com",
                "https://www.google.com",
                "https://www.baidu.com",
            ]

        transports = ["DNS-UDP", "DoT", "DoH-POST", "DoH-GET"]
        results = {t: [] for t in transports}

        for transport in transports:
            print(f"\n--- 测量传输协议: {transport} ---")
            for url in urls:
                for i in range(self.repeat):
                    result = self.measure_page_load(url, transport, "Google")
                    results[transport].append(result)

                    if result.status == "success":
                        print(f"  [OK] {url} (第{i+1}/{self.repeat}轮) "
                              f"DNS:{result.dns_time_ms:.1f}ms "
                              f"HTTP:{result.http_time_ms:.1f}ms "
                              f"总计:{result.total_time_ms:.1f}ms")
                    else:
                        print(f"  [FAIL] {url} (第{i+1}/{self.repeat}轮) "
                              f"错误: {result.error_message}")

                    time.sleep(0.2)

        return results

    def analyze_page_load_impact(self, results: Dict[str, List[PageLoadResult]]):
        """
        分析DNS传输协议对网页加载时间的影响

        计算各协议下:
        1. DNS解析占比
        2. 总加载时间对比
        3. DoH额外开销占总加载时间的百分比
        """
        print("\n" + "=" * 80)
        print("【网页加载时间影响分析】")
        print("=" * 80)
        print(f"{'协议':<12} {'DNS平均(ms)':<15} {'HTTP平均(ms)':<15} "
              f"{'总计平均(ms)':<15} {'DNS占比':<10}")
        print("-" * 80)

        summary = {}
        for transport, transport_results in results.items():
            successful = [r for r in transport_results if r.status == "success"]
            if successful:
                avg_dns = statistics.mean([r.dns_time_ms for r in successful])
                avg_http = statistics.mean([r.http_time_ms for r in successful])
                avg_total = statistics.mean([r.total_time_ms for r in successful])
                dns_ratio = avg_dns / avg_total if avg_total > 0 else 0

                summary[transport] = {
                    "avg_dns": avg_dns,
                    "avg_http": avg_http,
                    "avg_total": avg_total,
                    "dns_ratio": dns_ratio
                }

                print(f"{transport:<12} {avg_dns:<15.2f} {avg_http:<15.2f} "
                      f"{avg_total:<15.2f} {dns_ratio:<10.1%}")

        # 计算DoH相比传统DNS的额外开销对总加载时间的影响
        if "DNS-UDP" in summary and "DoH-POST" in summary:
            baseline_dns = summary["DNS-UDP"]["avg_dns"]
            doh_dns = summary["DoH-POST"]["avg_dns"]
            baseline_total = summary["DNS-UDP"]["avg_total"]
            extra_overhead = doh_dns - baseline_dns
            impact_ratio = extra_overhead / baseline_total if baseline_total > 0 else 0

            print(f"\n  DoH额外DNS开销: {extra_overhead:.2f}ms")
            print(f"  DoH额外开销占总加载时间比例: {impact_ratio:.1%}")
            print(f"  结论: DoH的额外开销对网页加载时间影响{'很小' if impact_ratio < 0.1 else '显著'}")

        return summary
