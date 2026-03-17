"""
测试性能测量模块
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.measurement.performance import PerformanceMeasurer


class TestPerformance:
    """测试性能测量功能"""

    def test_quick_measure(self):
        """快速性能测量测试（少量域名和重复次数）"""
        measurer = PerformanceMeasurer(repeat=2, timeout=10.0)

        # 只用一个域名快速测试
        results = measurer.measure_all(domains=["example.com"])

        # 验证各协议都有结果
        assert len(results["DNS-UDP"]) > 0, "传统DNS应有结果"
        assert len(results["DoT"]) > 0, "DoT应有结果"
        assert len(results["DoH-POST"]) > 0, "DoH-POST应有结果"
        assert len(results["DoH-GET"]) > 0, "DoH-GET应有结果"

        # 计算统计数据
        stats = measurer.calculate_stats(results)
        assert len(stats) > 0, "应有统计数据"

        # 打印摘要
        measurer.print_stats_summary(stats)

        # 计算开销
        overheads = measurer.measure_overhead(results)
        assert "DNS-UDP" in overheads

    def test_stats_calculation(self):
        """测试统计数据计算逻辑"""
        measurer = PerformanceMeasurer(repeat=3, timeout=10.0)
        results = measurer.measure_all(domains=["example.com"])
        stats = measurer.calculate_stats(results)

        for s in stats:
            if s.success_rate > 0:
                assert s.mean_ms > 0, f"{s.transport}/{s.resolver} 平均耗时应>0"
                assert s.median_ms > 0, f"{s.transport}/{s.resolver} 中位数应>0"
                assert s.min_ms <= s.mean_ms, "最小值应<=平均值"
                assert s.max_ms >= s.mean_ms, "最大值应>=平均值"
                print(f"  [{s.transport}/{s.resolver}] 平均: {s.mean_ms:.2f}ms, "
                      f"中位数: {s.median_ms:.2f}ms, 成功率: {s.success_rate:.0%}")
