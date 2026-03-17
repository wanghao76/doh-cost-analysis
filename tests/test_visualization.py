"""
可视化模块测试
==============
测试各类图表的生成功能。
使用模拟数据避免依赖网络。
"""

import os
import pytest
from pathlib import Path

from src.utils.helpers import QueryResult, ComplianceResult, RESULTS_DIR
from src.visualization.plots import (
    plot_performance_comparison,
    plot_query_time_boxplot,
    plot_overhead_breakdown,
    plot_page_load_impact,
    plot_compliance_heatmap,
    plot_dns_ratio_pie,
    generate_all_plots,
)


def _make_query_results():
    """生成模拟的查询结果数据"""
    results = {
        "DNS-UDP": [],
        "DoT": [],
        "DoH-POST": [],
        "DoH-GET": [],
    }

    import random
    random.seed(42)

    # 模拟各协议的查询时间（参考论文和实际测量数据）
    time_ranges = {
        "DNS-UDP": (5, 30),
        "DoT": (80, 200),
        "DoH-POST": (60, 150),
        "DoH-GET": (55, 140),
    }

    domains = ["example.com", "google.com", "baidu.com"]
    for transport, (low, high) in time_ranges.items():
        for domain in domains:
            for _ in range(5):
                t = random.uniform(low, high)
                results[transport].append(QueryResult(
                    domain=domain,
                    resolver="Google",
                    transport=transport,
                    query_time_ms=t,
                    response_size=random.randint(40, 120),
                    status="success",
                    ip_addresses=["1.2.3.4"],
                ))
    return results


def _make_compliance_results():
    """生成模拟的合规性检测结果"""
    return [
        ComplianceResult(
            server_name="Google", server_url="https://dns.google/dns-query",
            supports_post=True, supports_get=True, supports_wire_format=True,
            supports_http2=True, content_type_correct=True,
            cache_control_present=True, supports_padding=True, status_code=200,
        ),
        ComplianceResult(
            server_name="Cloudflare", server_url="https://cloudflare-dns.com/dns-query",
            supports_post=True, supports_get=True, supports_wire_format=True,
            supports_http2=True, content_type_correct=True,
            cache_control_present=True, supports_padding=True, status_code=200,
        ),
        ComplianceResult(
            server_name="Quad9", server_url="https://dns.quad9.net/dns-query",
            supports_post=True, supports_get=False, supports_wire_format=True,
            supports_http2=True, content_type_correct=True,
            cache_control_present=False, supports_padding=False, status_code=200,
        ),
    ]


class _MockPageLoadResult:
    """模拟PageLoadResult"""
    def __init__(self, dns_time, http_time, status="success"):
        self.dns_time_ms = dns_time
        self.http_time_ms = http_time
        self.total_time_ms = dns_time + http_time
        self.status = status


def _make_page_load_results():
    """生成模拟的网页加载测量数据"""
    import random
    random.seed(42)
    results = {}
    configs = {
        "DNS-UDP": (5, 60),
        "DoT": (80, 55),
        "DoH-POST": (70, 65),
        "DoH-GET": (65, 60),
    }
    for transport, (dns_base, http_base) in configs.items():
        results[transport] = []
        for _ in range(6):
            dns_t = dns_base + random.uniform(-5, 15)
            http_t = http_base + random.uniform(-10, 20)
            results[transport].append(
                _MockPageLoadResult(dns_t, http_t)
            )
    return results


class TestVisualization:
    """可视化测试类"""

    def test_performance_comparison(self):
        """测试性能对比柱状图生成"""
        results = _make_query_results()
        plot_performance_comparison(results, "test_perf_comparison.png")
        filepath = RESULTS_DIR / "test_perf_comparison.png"
        assert filepath.exists(), "性能对比图未生成"
        assert filepath.stat().st_size > 0, "性能对比图为空"
        print(f"  性能对比图大小: {filepath.stat().st_size} bytes")

    def test_query_time_boxplot(self):
        """测试查询时间箱线图生成"""
        results = _make_query_results()
        plot_query_time_boxplot(results, "test_boxplot.png")
        filepath = RESULTS_DIR / "test_boxplot.png"
        assert filepath.exists(), "箱线图未生成"
        assert filepath.stat().st_size > 0
        print(f"  箱线图大小: {filepath.stat().st_size} bytes")

    def test_overhead_breakdown(self):
        """测试协议开销分解图生成"""
        results = _make_query_results()
        plot_overhead_breakdown(results, "test_overhead.png")
        filepath = RESULTS_DIR / "test_overhead.png"
        assert filepath.exists(), "开销分解图未生成"
        assert filepath.stat().st_size > 0
        print(f"  开销分解图大小: {filepath.stat().st_size} bytes")

    def test_page_load_impact(self):
        """测试网页加载影响图生成"""
        results = _make_page_load_results()
        plot_page_load_impact(results, "test_page_load.png")
        filepath = RESULTS_DIR / "test_page_load.png"
        assert filepath.exists(), "网页加载图未生成"
        assert filepath.stat().st_size > 0
        print(f"  网页加载图大小: {filepath.stat().st_size} bytes")

    def test_compliance_heatmap(self):
        """测试合规性热力图生成"""
        results = _make_compliance_results()
        plot_compliance_heatmap(results, "test_compliance.png")
        filepath = RESULTS_DIR / "test_compliance.png"
        assert filepath.exists(), "合规性热力图未生成"
        assert filepath.stat().st_size > 0
        print(f"  合规性热力图大小: {filepath.stat().st_size} bytes")

    def test_dns_ratio_pie(self):
        """测试DNS占比饼图生成"""
        results = _make_page_load_results()
        plot_dns_ratio_pie(results, "test_dns_ratio.png")
        filepath = RESULTS_DIR / "test_dns_ratio.png"
        assert filepath.exists(), "DNS占比饼图未生成"
        assert filepath.stat().st_size > 0
        print(f"  DNS占比饼图大小: {filepath.stat().st_size} bytes")

    def test_generate_all_plots(self):
        """测试批量生成所有图表"""
        perf = _make_query_results()
        comp = _make_compliance_results()
        page = _make_page_load_results()
        generate_all_plots(perf, comp, page)

        # 验证默认文件名的图表都已生成
        expected_files = [
            "performance_comparison.png",
            "query_time_boxplot.png",
            "overhead_breakdown.png",
            "compliance_heatmap.png",
            "page_load_impact.png",
            "dns_ratio_pie.png",
        ]
        for fname in expected_files:
            filepath = RESULTS_DIR / fname
            assert filepath.exists(), f"图表 {fname} 未生成"
            print(f"  [OK] {fname}: {filepath.stat().st_size} bytes")
