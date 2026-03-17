"""
DoH服务器合规性检测模块
========================
根据RFC 8484标准，对公共DoH服务器进行合规性检测。

论文对照:
    论文第3节 "DoH Landscape" 对公共DoH服务器进行了系统性调查:
    1. 检测服务器是否支持GET和POST方法
    2. 检测Content-Type是否符合 application/dns-message
    3. 检测是否支持HTTP/2协议
    4. 检测是否返回正确的Cache-Control头部
    5. 检测是否支持DNS wire format
    6. 检测是否支持EDNS padding（增强隐私性）

    论文发现并非所有DoH服务器都完全遵守RFC 8484标准，
    一些服务器存在部分不合规的情况。

RFC 8484 关键要求:
    - 必须支持POST方法
    - 应该支持GET方法
    - Content-Type 必须为 application/dns-message
    - 必须支持DNS wire format
    - 推荐支持HTTP/2
    - 响应中应包含合适的Cache-Control头部
"""

import base64
import dns.message
import dns.rdatatype
import dns.edns
import httpx
from typing import List

from src.utils.helpers import ComplianceResult, load_config


class DoHComplianceChecker:
    """
    DoH服务器合规性检测器
    ======================
    按照RFC 8484标准对DoH服务器进行全面的合规性检测。

    参数:
        timeout: 请求超时时间（秒）
    """

    DNS_CONTENT_TYPE = "application/dns-message"
    TEST_DOMAIN = "example.com"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def check_server(self, server_name: str, server_url: str) -> ComplianceResult:
        """
        对单个DoH服务器执行全面的合规性检测

        参数:
            server_name: 服务器名称
            server_url: 服务器URL

        返回:
            ComplianceResult 合规性检测结果
        """
        result = ComplianceResult(
            server_name=server_name,
            server_url=server_url
        )

        # 1. 检测POST方法支持
        result.supports_post, post_response = self._check_post(server_url)

        # 2. 检测GET方法支持
        result.supports_get, get_response = self._check_get(server_url)

        # 3. 检测Content-Type是否正确
        if post_response:
            ct = post_response.headers.get("content-type", "")
            result.content_type_correct = self.DNS_CONTENT_TYPE in ct

        # 4. 检测是否支持DNS wire format
        result.supports_wire_format = self._check_wire_format(post_response)

        # 5. 检测HTTP/2支持
        result.supports_http2 = self._check_http2(server_url)

        # 6. 检测Cache-Control头部
        if post_response:
            result.cache_control_present = "cache-control" in post_response.headers

        # 7. 检测EDNS padding支持
        result.supports_padding = self._check_padding(server_url)

        # 记录HTTP状态码
        if post_response:
            result.status_code = post_response.status_code

        return result

    def _check_post(self, server_url: str):
        """
        检测POST方法支持

        RFC 8484规定DoH服务器必须支持POST方法。
        POST请求将DNS wire format放在请求体中。
        """
        try:
            request = dns.message.make_query(self.TEST_DOMAIN, "A")
            wire_data = request.to_wire()

            with httpx.Client(http2=True, verify=True, timeout=self.timeout) as client:
                response = client.post(
                    server_url,
                    content=wire_data,
                    headers={
                        "Content-Type": self.DNS_CONTENT_TYPE,
                        "Accept": self.DNS_CONTENT_TYPE
                    }
                )

            return response.status_code == 200, response
        except Exception as e:
            return False, None

    def _check_get(self, server_url: str):
        """
        检测GET方法支持

        RFC 8484规定DoH服务器应该支持GET方法。
        GET请求将DNS wire format进行Base64url编码后作为URL参数。
        """
        try:
            request = dns.message.make_query(self.TEST_DOMAIN, "A")
            wire_data = request.to_wire()
            dns_param = base64.urlsafe_b64encode(wire_data).decode().rstrip("=")

            with httpx.Client(http2=True, verify=True, timeout=self.timeout) as client:
                response = client.get(
                    server_url,
                    params={"dns": dns_param},
                    headers={"Accept": self.DNS_CONTENT_TYPE}
                )

            return response.status_code == 200, response
        except Exception:
            return False, None

    def _check_wire_format(self, response) -> bool:
        """
        检测响应是否为有效的DNS wire format

        尝试将响应内容解析为DNS消息来验证格式正确性。
        """
        if not response or response.status_code != 200:
            return False
        try:
            dns.message.from_wire(response.content)
            return True
        except Exception:
            return False

    def _check_http2(self, server_url: str) -> bool:
        """
        检测HTTP/2支持

        HTTP/2对DoH性能有重要影响:
        - 多路复用减少连接开销
        - 头部压缩(HPACK)减少传输数据量
        - 服务器推送等高级特性
        """
        try:
            request = dns.message.make_query(self.TEST_DOMAIN, "A")
            wire_data = request.to_wire()

            with httpx.Client(http2=True, verify=True, timeout=self.timeout) as client:
                response = client.post(
                    server_url,
                    content=wire_data,
                    headers={
                        "Content-Type": self.DNS_CONTENT_TYPE,
                        "Accept": self.DNS_CONTENT_TYPE
                    }
                )
                # 检查是否协商成功HTTP/2
                return response.http_version == "HTTP/2"
        except Exception:
            return False

    def _check_padding(self, server_url: str) -> bool:
        """
        检测EDNS padding支持

        EDNS padding (RFC 7830) 用于隐藏DNS查询的真实大小，
        通过填充数据使所有查询看起来大小相近，增强隐私保护。
        """
        try:
            request = dns.message.make_query(self.TEST_DOMAIN, "A")
            # 添加EDNS padding选项
            request.use_edns(edns=0, payload=4096, options=[dns.edns.GenericOption(12, b'\x00' * 128)])
            wire_data = request.to_wire()

            with httpx.Client(http2=True, verify=True, timeout=self.timeout) as client:
                response = client.post(
                    server_url,
                    content=wire_data,
                    headers={
                        "Content-Type": self.DNS_CONTENT_TYPE,
                        "Accept": self.DNS_CONTENT_TYPE
                    }
                )

            if response.status_code == 200:
                dns_response = dns.message.from_wire(response.content)
                # 检查响应中是否包含padding选项
                if dns_response.edns >= 0:
                    for option in dns_response.options:
                        if option.otype == 12:  # Padding option type
                            return True
            return False
        except Exception:
            return False

    def check_all_servers(self) -> List[ComplianceResult]:
        """
        检测配置文件中所有DoH服务器的合规性

        返回:
            ComplianceResult列表
        """
        config = load_config()
        results = []

        for server in config["doh_servers"]:
            print(f"[检测] 正在检测 {server['name']} ({server['url']})...")
            result = self.check_server(server["name"], server["url"])
            results.append(result)
            self._print_result(result)

        return results

    def _print_result(self, result: ComplianceResult):
        """打印单个服务器的合规性检测结果"""
        checks = {
            "POST方法": result.supports_post,
            "GET方法": result.supports_get,
            "Wire Format": result.supports_wire_format,
            "HTTP/2": result.supports_http2,
            "Content-Type": result.content_type_correct,
            "Cache-Control": result.cache_control_present,
            "EDNS Padding": result.supports_padding
        }

        print(f"  服务器: {result.server_name}")
        for check_name, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"    {status} {check_name}")
        print()
