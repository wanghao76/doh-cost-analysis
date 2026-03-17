"""
DNS-over-HTTPS 实证研究 - 主入口
=================================
复现论文 "An Empirical Study of the Cost of DNS-over-HTTPS" 的核心实验。

论文信息:
    作者: Timm Böttger, Felix Cuadrado, Gianni Antichi 等
    会议: ACM Internet Measurement Conference (IMC) 2019
    arXiv: 1909.06192

使用方法:
    运行全部实验:
        python main.py

    运行指定实验:
        python main.py --experiment compliance
        python main.py --experiment performance
        python main.py --experiment pageload
        python main.py --experiment visualize

    快速模式（减少重复次数）:
        python main.py --quick

    仅生成图表（使用已有数据）:
        python main.py --experiment visualize
"""

import argparse
import sys
import time

from src.compliance.doh_compliance import DoHComplianceChecker
from src.measurement.performance import PerformanceMeasurer
from src.measurement.page_load import PageLoadMeasurer
from src.visualization.plots import generate_all_plots
from src.utils.helpers import (
    load_config, save_results_to_csv, save_compliance_to_csv, ensure_results_dir
)


def run_compliance_check():
    """
    实验一: DoH服务器RFC 8484合规性检测

    对应论文第3节 "DoH Compliance"。
    检测多个公共DoH服务器对RFC 8484标准的支持程度。
    """
    print("\n" + "=" * 70)
    print("  实验一: DoH服务器 RFC 8484 合规性检测")
    print("  (论文第3节 DoH Compliance)")
    print("=" * 70)

    checker = DoHComplianceChecker()
    results = checker.check_all_servers()
    save_compliance_to_csv(results, "compliance_results.csv")

    return results


def run_performance_test(quick: bool = False):
    """
    实验二: DNS传输协议性能对比

    对应论文第4-5节 "Transport Comparison" 和 "Overheads"。
    对比DNS-UDP、DoT、DoH的查询响应时间。
    """
    print("\n" + "=" * 70)
    print("  实验二: DNS传输协议性能对比")
    print("  (论文第4-5节 Transport Comparison & Overheads)")
    print("=" * 70)

    repeat = 2 if quick else 5
    measurer = PerformanceMeasurer(repeat=repeat, timeout=10.0)

    config = load_config()
    domains = config["test_domains"][:3] if quick else config["test_domains"][:5]

    results = measurer.measure_all(domains)
    stats_list = measurer.calculate_stats(results)
    measurer.print_stats_summary(stats_list)
    measurer.measure_overhead(results)

    # 保存原始查询结果
    all_results = []
    for transport_results in results.values():
        all_results.extend(transport_results)
    save_results_to_csv(all_results, "performance_results.csv")

    return results


def run_page_load_test(quick: bool = False):
    """
    实验三: 网页加载时间影响分析

    对应论文第5节 "Impact on Page Load Times"。
    测量不同DNS传输协议对网页加载时间的影响。
    """
    print("\n" + "=" * 70)
    print("  实验三: 网页加载时间影响分析")
    print("  (论文第5节 Impact on Page Load Times)")
    print("=" * 70)

    repeat = 1 if quick else 3
    measurer = PageLoadMeasurer(repeat=repeat, timeout=10.0)

    urls = [
        "https://example.com",
        "https://www.google.com",
    ]
    if not quick:
        urls.append("https://www.baidu.com")

    results = measurer.measure_all_transports(urls)
    summary = measurer.analyze_page_load_impact(results)

    return results


def run_visualization(performance_results=None, compliance_results=None,
                      page_load_results=None):
    """
    生成所有实验结果的可视化图表

    生成的图表:
    1. 协议性能对比柱状图
    2. 查询时间分布箱线图
    3. 协议开销分解图
    4. 合规性热力图
    5. 网页加载时间影响图
    6. DNS解析时间占比饼图
    """
    print("\n" + "=" * 70)
    print("  生成可视化图表")
    print("=" * 70)

    generate_all_plots(performance_results, compliance_results, page_load_results)


def main():
    parser = argparse.ArgumentParser(
        description="DNS-over-HTTPS 实证研究 — 论文复现工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 运行全部实验
  python main.py --quick            # 快速模式
  python main.py -e compliance      # 仅合规性检测
  python main.py -e performance     # 仅性能测试
  python main.py -e pageload        # 仅网页加载测试
  python main.py -e visualize       # 仅生成图表（需要先运行其他实验）
        """
    )
    parser.add_argument(
        "-e", "--experiment",
        choices=["compliance", "performance", "pageload", "visualize", "all"],
        default="all",
        help="选择要运行的实验 (默认: all)"
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="快速模式: 减少重复次数和测试域名数"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  DNS-over-HTTPS 实证研究")
    print("  论文: An Empirical Study of the Cost of DNS-over-HTTPS")
    print("  作者: Bottger, Cuadrado, Antichi 等 (ACM IMC 2019)")
    print("=" * 70)
    if args.quick:
        print("  [模式] 快速模式已启用")

    ensure_results_dir()
    start_time = time.time()

    compliance_results = None
    performance_results = None
    page_load_results = None

    if args.experiment in ("compliance", "all"):
        compliance_results = run_compliance_check()

    if args.experiment in ("performance", "all"):
        performance_results = run_performance_test(args.quick)

    if args.experiment in ("pageload", "all"):
        page_load_results = run_page_load_test(args.quick)

    if args.experiment in ("visualize", "all"):
        run_visualization(performance_results, compliance_results, page_load_results)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"  全部实验完成! 总耗时: {elapsed:.1f}秒")
    print(f"  结果保存目录: results/")
    print("=" * 70)


if __name__ == "__main__":
    main()
