"""
DNS-over-TLS (DoT) 客户端模块
==============================
实现基于TLS加密的DNS查询功能（端口853）。
DoT是DNS加密传输的早期方案，在TCP基础上加TLS层。

论文对照:
    论文将DoT作为DoH的前代方案进行对比。
    DoT使用专用端口853，容易被网络管理员识别和封锁。
    这是DoH相比DoT的一个重要优势——DoH使用标准HTTPS端口443，
    与正常网页流量混合，更难被识别和封锁。

RFC参考:
    RFC 7858 - Specification for DNS over Transport Layer Security (DNS over TLS)
"""

import ssl
import socket
import struct
import dns.message
import dns.rdatatype
from typing import List

from src.utils.helpers import QueryResult, Timer


class DoTClient:
    """
    DNS-over-TLS客户端
    ===================
    通过TLS加密的TCP连接（端口853）进行DNS查询。
    提供传输层加密，防止中间人窃听DNS查询内容。

    参数:
        server_ip: DoT服务器IP地址
        server_name: 服务器名称标识
        hostname: TLS验证用的主机名
        port: DoT服务端口，默认853
        timeout: 超时时间（秒）
    """

    def __init__(self, server_ip: str, server_name: str = "Unknown",
                 hostname: str = "", port: int = 853, timeout: float = 5.0):
        self.server_ip = server_ip
        self.server_name = server_name
        self.hostname = hostname or server_ip
        self.port = port
        self.timeout = timeout

    def _create_tls_connection(self) -> ssl.SSLSocket:
        """
        创建TLS加密的TCP连接

        返回:
            已建立TLS握手的SSL套接字

        说明:
            DoT的连接建立过程:
            1. TCP三次握手
            2. TLS握手（协商加密参数、验证证书）
            3. 之后在此加密通道上发送DNS查询
        """
        # 创建SSL上下文，验证服务器证书
        context = ssl.create_default_context()
        # 创建TCP连接
        sock = socket.create_connection(
            (self.server_ip, self.port),
            timeout=self.timeout
        )
        # 在TCP连接上建立TLS
        tls_sock = context.wrap_socket(sock, server_hostname=self.hostname)
        return tls_sock

    def query(self, domain: str, rdtype: str = "A") -> QueryResult:
        """
        执行DoT查询

        参数:
            domain: 要查询的域名
            rdtype: DNS记录类型

        返回:
            QueryResult 包含查询结果和耗时

        说明:
            DoT使用TCP传输DNS消息，需要在消息前添加2字节长度前缀，
            这是DNS over TCP的标准格式（RFC 1035 Section 4.2.2）。
        """
        timer = Timer()
        tls_sock = None
        try:
            # 构建DNS查询报文
            request = dns.message.make_query(domain, rdtype)
            wire_data = request.to_wire()

            # 建立TLS连接并发送查询（计入总耗时）
            timer.start()
            tls_sock = self._create_tls_connection()

            # TCP DNS消息需要2字节长度前缀
            tcp_msg = struct.pack("!H", len(wire_data)) + wire_data
            tls_sock.sendall(tcp_msg)

            # 接收响应：先读2字节长度，再读数据
            length_data = self._recv_exact(tls_sock, 2)
            response_length = struct.unpack("!H", length_data)[0]
            response_data = self._recv_exact(tls_sock, response_length)
            query_time = timer.stop()

            # 解析DNS响应
            response = dns.message.from_wire(response_data)

            # 提取IP地址和TTL
            ip_addresses = []
            ttl = 0
            for rrset in response.answer:
                ttl = rrset.ttl
                for rdata in rrset:
                    ip_addresses.append(str(rdata))

            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoT",
                query_time_ms=query_time,
                response_size=len(response_data),
                status="success",
                ip_addresses=ip_addresses,
                ttl=ttl
            )

        except Exception as e:
            timer.stop()
            return QueryResult(
                domain=domain,
                resolver=self.server_name,
                transport="DoT",
                query_time_ms=timer.elapsed_ms,
                status="error",
                error_message=str(e)
            )
        finally:
            if tls_sock:
                tls_sock.close()

    def _recv_exact(self, sock: ssl.SSLSocket, length: int) -> bytes:
        """
        从套接字中精确读取指定长度的数据

        参数:
            sock: SSL套接字
            length: 需要读取的字节数

        返回:
            读取到的字节数据
        """
        data = b""
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("连接在接收数据时被关闭")
            data += chunk
        return data

    def query_batch(self, domains: List[str], rdtype: str = "A") -> List[QueryResult]:
        """
        批量执行DoT查询

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
