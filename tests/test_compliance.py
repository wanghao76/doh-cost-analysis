"""
测试DoH合规性检测模块
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.compliance.doh_compliance import DoHComplianceChecker


class TestDoHCompliance:
    """测试DoH合规性检测"""

    def test_google_compliance(self):
        """测试Google DoH服务器合规性"""
        checker = DoHComplianceChecker()
        result = checker.check_server("Google", "https://dns.google/dns-query")

        assert result.supports_post, "Google应支持POST方法"
        assert result.supports_get, "Google应支持GET方法"
        assert result.supports_wire_format, "Google应支持wire format"
        assert result.content_type_correct, "Content-Type应正确"
        print(f"  [合规] Google DoH - POST:{result.supports_post}, GET:{result.supports_get}, "
              f"HTTP/2:{result.supports_http2}, Padding:{result.supports_padding}")

    def test_cloudflare_compliance(self):
        """测试Cloudflare DoH服务器合规性"""
        checker = DoHComplianceChecker()
        result = checker.check_server("Cloudflare", "https://cloudflare-dns.com/dns-query")

        assert result.supports_post, "Cloudflare应支持POST方法"
        assert result.supports_get, "Cloudflare应支持GET方法"
        assert result.content_type_correct, "Content-Type应正确"
        print(f"  [合规] Cloudflare DoH - POST:{result.supports_post}, GET:{result.supports_get}, "
              f"HTTP/2:{result.supports_http2}, Padding:{result.supports_padding}")

    def test_check_result_fields(self):
        """验证检测结果数据完整性"""
        checker = DoHComplianceChecker()
        result = checker.check_server("Google", "https://dns.google/dns-query")

        assert result.server_name == "Google"
        assert result.server_url == "https://dns.google/dns-query"
        assert result.status_code == 200
        print(f"  [合规] 数据完整性验证通过, HTTP状态码: {result.status_code}")
