"""
测试网页加载时间测量模块
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.measurement.page_load import PageLoadMeasurer


class TestPageLoad:
    """测试网页加载时间测量"""

    def test_single_page_load(self):
        """测试单个URL的加载测量"""
        measurer = PageLoadMeasurer(repeat=1)
        result = measurer.measure_page_load(
            "https://example.com", "DNS-UDP", "Google"
        )
        assert result.status == "success", f"加载失败: {result.error_message}"
        assert result.dns_time_ms > 0
        assert result.http_time_ms > 0
        assert result.total_time_ms > 0
        print(f"  DNS: {result.dns_time_ms:.1f}ms, HTTP: {result.http_time_ms:.1f}ms, "
              f"总计: {result.total_time_ms:.1f}ms")

    def test_doh_page_load(self):
        """测试使用DoH的网页加载"""
        measurer = PageLoadMeasurer(repeat=1)
        result = measurer.measure_page_load(
            "https://example.com", "DoH-POST", "Google"
        )
        assert result.status == "success", f"DoH加载失败: {result.error_message}"
        print(f"  [DoH] DNS: {result.dns_time_ms:.1f}ms, HTTP: {result.http_time_ms:.1f}ms, "
              f"总计: {result.total_time_ms:.1f}ms")

    def test_quick_all_transports(self):
        """快速测试所有传输协议的网页加载"""
        measurer = PageLoadMeasurer(repeat=1)
        results = measurer.measure_all_transports(urls=["https://example.com"])

        for transport, transport_results in results.items():
            assert len(transport_results) > 0, f"{transport} 应有结果"

        summary = measurer.analyze_page_load_impact(results)
        assert len(summary) > 0
