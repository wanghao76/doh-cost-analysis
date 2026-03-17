"""
测试DNS客户端模块
==================
验证传统DNS、DoT、DoH三种客户端的基本功能。
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dns_client.traditional_dns import TraditionalDNSClient
from src.dns_client.dot_client import DoTClient
from src.dns_client.doh_client import DoHClient


class TestTraditionalDNS:
    """测试传统DNS客户端"""

    def test_basic_query(self):
        """测试基本A记录查询"""
        client = TraditionalDNSClient("8.8.8.8", "Google")
        result = client.query("example.com")
        assert result.status == "success", f"查询失败: {result.error_message}"
        assert len(result.ip_addresses) > 0, "未获取到IP地址"
        assert result.query_time_ms > 0, "查询时间应大于0"
        assert result.transport == "DNS-UDP"
        print(f"  [传统DNS] example.com -> {result.ip_addresses}, 耗时: {result.query_time_ms:.2f}ms")

    def test_batch_query(self):
        """测试批量查询"""
        client = TraditionalDNSClient("8.8.8.8", "Google")
        domains = ["example.com", "google.com"]
        results = client.query_batch(domains)
        assert len(results) == 2
        for r in results:
            assert r.status == "success", f"{r.domain} 查询失败: {r.error_message}"
            print(f"  [传统DNS] {r.domain} -> {r.ip_addresses}, 耗时: {r.query_time_ms:.2f}ms")

    def test_invalid_domain(self):
        """测试无效域名处理"""
        client = TraditionalDNSClient("8.8.8.8", "Google")
        result = client.query("this-domain-does-not-exist-12345.com")
        # 可能返回 NXDOMAIN 错误或空结果
        print(f"  [传统DNS] 无效域名测试 -> 状态: {result.status}")


class TestDoTClient:
    """测试DNS-over-TLS客户端"""

    def test_basic_query(self):
        """测试DoT基本查询"""
        client = DoTClient("8.8.8.8", "Google", hostname="dns.google")
        result = client.query("example.com")
        assert result.status == "success", f"DoT查询失败: {result.error_message}"
        assert len(result.ip_addresses) > 0
        assert result.transport == "DoT"
        print(f"  [DoT] example.com -> {result.ip_addresses}, 耗时: {result.query_time_ms:.2f}ms")

    def test_batch_query(self):
        """测试DoT批量查询"""
        client = DoTClient("8.8.8.8", "Google", hostname="dns.google")
        results = client.query_batch(["example.com", "google.com"])
        assert len(results) == 2
        for r in results:
            assert r.status == "success", f"{r.domain} DoT查询失败: {r.error_message}"
            print(f"  [DoT] {r.domain} -> {r.ip_addresses}, 耗时: {r.query_time_ms:.2f}ms")


class TestDoHClient:
    """测试DNS-over-HTTPS客户端"""

    def test_post_query(self):
        """测试DoH POST方法"""
        client = DoHClient("https://dns.google/dns-query", "Google")
        result = client.query_post("example.com")
        assert result.status == "success", f"DoH POST查询失败: {result.error_message}"
        assert len(result.ip_addresses) > 0
        assert result.transport == "DoH-POST"
        print(f"  [DoH-POST] example.com -> {result.ip_addresses}, 耗时: {result.query_time_ms:.2f}ms")

    def test_get_query(self):
        """测试DoH GET方法"""
        client = DoHClient("https://dns.google/dns-query", "Google")
        result = client.query_get("example.com")
        assert result.status == "success", f"DoH GET查询失败: {result.error_message}"
        assert len(result.ip_addresses) > 0
        assert result.transport == "DoH-GET"
        print(f"  [DoH-GET] example.com -> {result.ip_addresses}, 耗时: {result.query_time_ms:.2f}ms")

    def test_cloudflare(self):
        """测试Cloudflare DoH服务器"""
        client = DoHClient("https://cloudflare-dns.com/dns-query", "Cloudflare")
        result = client.query_post("example.com")
        assert result.status == "success", f"Cloudflare DoH查询失败: {result.error_message}"
        print(f"  [DoH-Cloudflare] example.com -> {result.ip_addresses}, 耗时: {result.query_time_ms:.2f}ms")

    def test_batch_query(self):
        """测试DoH批量查询"""
        client = DoHClient("https://dns.google/dns-query", "Google")
        results = client.query_batch(["example.com", "google.com"])
        assert len(results) == 2
        for r in results:
            assert r.status == "success", f"{r.domain} DoH查询失败: {r.error_message}"
            print(f"  [DoH] {r.domain} -> {r.ip_addresses}, 耗时: {r.query_time_ms:.2f}ms")
