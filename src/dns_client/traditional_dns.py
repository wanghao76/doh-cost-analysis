"""
传统DNS客户端模块
==================
实现基于UDP(端口53)的传统DNS查询功能。
这是最基础的DNS解析方式，不提供加密保护。

论文对照:
    论文中将传统DNS作为基准(baseline)，与DoT和DoH进行性能对比。
    传统DNS使用UDP传输，无需TLS握手和HTTP层开销，因此查询速度最快。
"""

import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
from typing import List, Optional

from src.utils.helpers import QueryResult, Timer


class TraditionalDNSClient:
    """
    传统DNS客户端
    ==============
    使用标准UDP协议在端口53上进行DNS查询。
    不提供加密，查询内容对中间人可见。

    参数:
        server_ip: DNS服务器IP地址
        server_name: DNS服务器名称标识
        port: DNS服务端口，默认53
        timeout: 查询超时时间（秒）
    """

    def __init__(self, server_ip: str, server_name: str = "Unknown",
                 port: int = 53, timeout: float = 5.0):
        self.server_ip = server_ip
        self.server_name = server_name
        self.port = port
        self.timeout = timeout

    def query(self, domain: str, rdtype: str = "A") -> QueryResult:
        """
        执行传统DNS查询

        参数:
            domain: 要查询的域名
            rdtype: DNS记录类型，默认为A记录

        返回:
            QueryResult 包含查询结果和耗时信息
        """
        timer = Timer()
        try:
            # 构建DNS查询报文
            request = dns.message.make_query(domain, rdtype)

            # 使用UDP发送查询并计时
            timer.start()
            response = dns.query.udp(
                request,
                self.server_ip,
                port=self.port,
                timeout=self.timeout
            )
            query_time = timer.stop()

            # 提取响应中的IP地址
            ip_addresses = []
            ttl = 0
            for rrset in response.answer:
                ttl = rrset.ttl
                for rdata in rrset:
                    ip_addresses.append(str(rdata))

            # 将响应序列化为wire format以获取大小
            response_wire = response.to_wire()

            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DNS-UDP",
                query_time_ms=query_time,
                response_size=len(response_wire),
                status="success",
                ip_addresses=ip_addresses,
                ttl=ttl
            )

        except Exception as e:
            timer.stop()
            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DNS-UDP",
                query_time_ms=timer.elapsed_ms,
                status="error",
                error_message=str(e)
            )

    def query_batch(self, domains: List[str], rdtype: str = "A") -> List[QueryResult]:
        """
        批量执行DNS查询

        参数:
            domains: 域名列表
            rdtype: DNS记录类型

        返回:
            QueryResult列表
        """
        results = []
        for domain in domains:
            result = self.query(domain, rdtype)
            results.append(result)
        return results
