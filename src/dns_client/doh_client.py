"""
DNS-over-HTTPS (DoH) 客户端模块
=================================
实现基于HTTPS的DNS查询功能（端口443）。
这是论文研究的核心协议——DoH。

论文对照:
    DoH (RFC 8484) 将DNS查询封装在HTTPS请求中。
    优势:
    1. 使用标准HTTPS端口443，与正常网页流量混合，难以被单独封锁
    2. 可以复用HTTP/2的多路复用特性，减少连接开销
    3. 利用成熟的HTTPS生态（CDN缓存、负载均衡等）

    开销:
    1. HTTP层额外的头部开销
    2. TLS握手开销（首次连接时）
    3. HTTP/2帧开销

    论文发现DoH的额外开销对网页加载时间的影响是有限的。

RFC参考:
    RFC 8484 - DNS Queries over HTTPS (DoH)
"""

import base64
import dns.message
import dns.rdatatype
import httpx
from typing import List, Optional

from src.utils.helpers import QueryResult, Timer


class DoHClient:
    """
    DNS-over-HTTPS客户端
    =====================
    通过HTTPS协议（端口443）进行DNS查询。
    支持RFC 8484定义的GET和POST两种方法。

    参数:
        server_url: DoH服务器URL（如 https://dns.google/dns-query）
        server_name: 服务器名称标识
        timeout: 超时时间（秒）
        use_http2: 是否使用HTTP/2协议
    """

    # RFC 8484规定的Content-Type
    DNS_MESSAGE_CONTENT_TYPE = "application/dns-message"

    def __init__(self, server_url: str, server_name: str = "Unknown",
                 timeout: float = 5.0, use_http2: bool = True):
        self.server_url = server_url
        self.server_name = server_name
        self.timeout = timeout
        self.use_http2 = use_http2

    def query_post(self, domain: str, rdtype: str = "A") -> QueryResult:
        """
        使用HTTP POST方法执行DoH查询

        POST方法: 将DNS wire format消息放在HTTP请求体中
        Content-Type: application/dns-message

        参数:
            domain: 查询的域名
            rdtype: 记录类型

        返回:
            QueryResult
        """
        timer = Timer()
        try:
            # 构建DNS查询报文（wire format）
            request = dns.message.make_query(domain, rdtype)
            wire_data = request.to_wire()

            # 发送HTTPS POST请求
            timer.start()
            with httpx.Client(
                http2=self.use_http2,
                verify=True,
                timeout=self.timeout
            ) as client:
                response = client.post(
                    self.server_url,
                    content=wire_data,
                    headers={
                        "Content-Type": self.DNS_MESSAGE_CONTENT_TYPE,
                        "Accept": self.DNS_MESSAGE_CONTENT_TYPE
                    }
                )
            query_time = timer.stop()

            if response.status_code != 200:
                return QueryResult(
                    domain=domain,
                    resolver=self.server_name,
                    transport="DoH-POST",
                    query_time_ms=query_time,
                    status="error",
                    error_message=f"HTTP状态码: {response.status_code}"
                )

            # 解析DNS响应
            dns_response = dns.message.from_wire(response.content)

            ip_addresses = []
            ttl = 0
            for rrset in dns_response.answer:
                ttl = rrset.ttl
                for rdata in rrset:
                    ip_addresses.append(str(rdata))

            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoH-POST",
                query_time_ms=query_time,
                response_size=len(response.content),
                status="success",
                ip_addresses=ip_addresses,
                ttl=ttl
            )

        except Exception as e:
            timer.stop()
            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoH-POST",
                query_time_ms=timer.elapsed_ms,
                status="error",
                error_message=str(e)
            )

    def query_get(self, domain: str, rdtype: str = "A") -> QueryResult:
        """
        使用HTTP GET方法执行DoH查询

        GET方法: 将DNS wire format消息进行Base64url编码后放在URL参数中
        GET /dns-query?dns=<base64url编码的查询>

        参数:
            domain: 查询的域名
            rdtype: 记录类型

        返回:
            QueryResult
        """
        timer = Timer()
        try:
            # 构建DNS查询报文并进行Base64url编码
            request = dns.message.make_query(domain, rdtype)
            wire_data = request.to_wire()
            # RFC 8484要求使用Base64url编码（无填充）
            dns_param = base64.urlsafe_b64encode(wire_data).decode().rstrip("=")

            timer.start()
            with httpx.Client(
                http2=self.use_http2,
                verify=True,
                timeout=self.timeout
            ) as client:
                response = client.get(
                    self.server_url,
                    params={"dns": dns_param},
                    headers={
                        "Accept": self.DNS_MESSAGE_CONTENT_TYPE
                    }
                )
            query_time = timer.stop()

            if response.status_code != 200:
                return QueryResult(
                    domain=domain,
                    resolver=self.server_name,
                    transport="DoH-GET",
                    query_time_ms=query_time,
                    status="error",
                    error_message=f"HTTP状态码: {response.status_code}"
                )

            # 解析DNS响应
            dns_response = dns.message.from_wire(response.content)

            ip_addresses = []
            ttl = 0
            for rrset in dns_response.answer:
                ttl = rrset.ttl
                for rdata in rrset:
                    ip_addresses.append(str(rdata))

            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoH-GET",
                query_time_ms=query_time,
                response_size=len(response.content),
                status="success",
                ip_addresses=ip_addresses,
                ttl=ttl
            )

        except Exception as e:
            timer.stop()
            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoH-GET",
                query_time_ms=timer.elapsed_ms,
                status="error",
                error_message=str(e)
            )

    def query(self, domain: str, rdtype: str = "A",
              method: str = "POST") -> QueryResult:
        """
        执行DoH查询（通用接口）

        参数:
            domain: 查询的域名
            rdtype: 记录类型
            method: HTTP方法 (POST 或 GET)

        返回:
            QueryResult
        """
        if method.upper() == "GET":
            return self.query_get(domain, rdtype)
        return self.query_post(domain, rdtype)

    def query_batch(self, domains: List[str], rdtype: str = "A",
                    method: str = "POST") -> List[QueryResult]:
        """
        批量执行DoH查询

        参数:
            domains: 域名列表
            rdtype: 记录类型
            method: HTTP方法

        返回:
            QueryResult列表
        """
        results = []
        for domain in domains:
            result = self.query(domain, rdtype, method)
            results.append(result)
        return results
