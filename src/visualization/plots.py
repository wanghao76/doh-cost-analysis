"""
可视化模块
==========
将DNS性能测量结果可视化，生成多种图表。

论文对照:
    论文中包含了多种图表展示实验结果:
    - 图2: 各DoH服务器RFC 8484合规性对比（热力图/表格形式）
    - 图3: DNS/DoT/DoH三种协议的查询响应时间CDF
    - 图4: 各协议层的开销分解（堆叠柱状图）
    - 图5: 不同网站的页面加载时间对比

    本模块实现:
    1. 协议性能对比柱状图（平均查询时间）
    2. 查询时间分布箱线图
    3. 协议开销分解图
    4. 网页加载时间影响图
    5. DoH服务器合规性热力图
"""

import os
import statistics
from typing import List, Dict, Optional

import matplotlib
matplotlib.use("Agg")  # 非交互式后端，适合服务器/CI环境

import matplotlib.pyplot as plt
import numpy as np

from src.utils.helpers import (
    QueryResult, ComplianceResult, RESULTS_DIR, ensure_results_dir
)
from src.measurement.performance import PerformanceStats

# 设置中文字体（优先使用系统已有字体）
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 统一配色方案
COLORS = {
    "DNS-UDP": "#4CAF50",    # 绿色 - 传统DNS
    "DoT": "#2196F3",        # 蓝色 - DNS-over-TLS
    "DoH-POST": "#FF9800",   # 橙色 - DoH POST
    "DoH-GET": "#F44336",    # 红色 - DoH GET
}


def _save_figure(fig, filename: str):
    """保存图表到results目录"""
    ensure_results_dir()
    filepath = RESULTS_DIR / filename
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[保存] 图表已保存至: {filepath}")


def plot_performance_comparison(
    results: Dict[str, List[QueryResult]],
    filename: str = "performance_comparison.png"
):
    """
    绘制协议性能对比柱状图

    对应论文图3/图4：展示不同DNS传输协议的平均查询时间。

    参数:
        results: 按传输协议分组的查询结果
        filename: 输出文件名
    """
    # 计算各协议的平均查询时间
    protocols = []
    means = []
    stds = []
    colors = []

    for transport, transport_results in results.items():
        successful = [r for r in transport_results if r.status == "success"]
        if successful:
            times = [r.query_time_ms for r in successful]
            protocols.append(transport)
            means.append(statistics.mean(times))
            stds.append(statistics.stdev(times) if len(times) > 1 else 0)
            colors.append(COLORS.get(transport, "#9E9E9E"))

    if not protocols:
        print("[警告] 无有效数据，跳过性能对比图")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(protocols))
    bars = ax.bar(x, means, yerr=stds, capsize=5, color=colors,
                  edgecolor="black", linewidth=0.5, alpha=0.85)

    # 在柱子上方标注数值
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{mean:.1f}ms", ha="center", va="bottom", fontsize=10)

    ax.set_xlabel("DNS传输协议", fontsize=12)
    ax.set_ylabel("平均查询时间 (ms)", fontsize=12)
    ax.set_title("DNS传输协议性能对比", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)

    _save_figure(fig, filename)


def plot_query_time_boxplot(
    results: Dict[str, List[QueryResult]],
    filename: str = "query_time_boxplot.png"
):
    """
    绘制查询时间分布箱线图

    对应论文对响应时间分布的分析：展示各协议查询时间的分布特征。

    参数:
        results: 按传输协议分组的查询结果
        filename: 输出文件名
    """
    data = []
    labels = []
    box_colors = []

    for transport, transport_results in results.items():
        successful = [r for r in transport_results if r.status == "success"]
        if successful:
            times = [r.query_time_ms for r in successful]
            data.append(times)
            labels.append(transport)
            box_colors.append(COLORS.get(transport, "#9E9E9E"))

    if not data:
        print("[警告] 无有效数据，跳过箱线图")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.5)

    # 设置箱体颜色
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # 设置中位线颜色
    for median in bp["medians"]:
        median.set_color("black")
        median.set_linewidth(2)

    ax.set_xlabel("DNS传输协议", fontsize=12)
    ax.set_ylabel("查询时间 (ms)", fontsize=12)
    ax.set_title("DNS查询时间分布", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    _save_figure(fig, filename)


def plot_overhead_breakdown(
    results: Dict[str, List[QueryResult]],
    filename: str = "overhead_breakdown.png"
):
    """
    绘制协议开销分解图

    对应论文图4：展示DoT和DoH相比传统DNS的额外开销，
    分解为基础DNS开销和加密传输额外开销两部分。

    参数:
        results: 按传输协议分组的查询结果
        filename: 输出文件名
    """
    avg_times = {}
    for transport, transport_results in results.items():
        successful = [r for r in transport_results if r.status == "success"]
        if successful:
            avg_times[transport] = statistics.mean(
                [r.query_time_ms for r in successful]
            )

    baseline = avg_times.get("DNS-UDP", 0)
    if baseline == 0:
        print("[警告] 无DNS-UDP基准数据，跳过开销分解图")
        return

    protocols = []
    base_parts = []     # 基础DNS查询时间（等于UDP基准）
    overhead_parts = []  # 额外开销

    for transport, avg_time in avg_times.items():
        protocols.append(transport)
        base_parts.append(baseline)
        overhead_parts.append(max(0, avg_time - baseline))

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(protocols))
    width = 0.5

    # 堆叠柱状图：底部是基础DNS耗时，上部是额外开销
    bars1 = ax.bar(x, base_parts, width, label="基础DNS查询",
                   color="#4CAF50", edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x, overhead_parts, width, bottom=base_parts,
                   label="加密传输额外开销", color="#FF5722",
                   edgecolor="black", linewidth=0.5, alpha=0.85)

    # 标注总时间
    for i, (b, o) in enumerate(zip(base_parts, overhead_parts)):
        total = b + o
        ax.text(i, total + 1, f"{total:.1f}ms", ha="center", va="bottom",
                fontsize=10, fontweight="bold")

    ax.set_xlabel("DNS传输协议", fontsize=12)
    ax.set_ylabel("查询时间 (ms)", fontsize=12)
    ax.set_title("协议开销分解 (相对于传统DNS)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, fontsize=11)
    ax.legend(fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)

    _save_figure(fig, filename)


def plot_page_load_impact(
    page_results: Dict[str, list],
    filename: str = "page_load_impact.png"
):
    """
    绘制网页加载时间影响图

    对应论文第5节：展示不同DNS传输协议下，DNS解析时间和HTTP下载时间的对比。

    参数:
        page_results: 按传输协议分组的PageLoadResult列表
        filename: 输出文件名
    """
    protocols = []
    dns_times = []
    http_times = []

    for transport, results in page_results.items():
        successful = [r for r in results if r.status == "success"]
        if successful:
            protocols.append(transport)
            dns_times.append(statistics.mean([r.dns_time_ms for r in successful]))
            http_times.append(statistics.mean([r.http_time_ms for r in successful]))

    if not protocols:
        print("[警告] 无有效数据，跳过网页加载影响图")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(protocols))
    width = 0.5

    # 堆叠柱状图：DNS + HTTP
    bars1 = ax.bar(x, dns_times, width, label="DNS解析时间",
                   color="#2196F3", edgecolor="black", linewidth=0.5)
    bars2 = ax.bar(x, http_times, width, bottom=dns_times,
                   label="HTTP下载时间", color="#FF9800",
                   edgecolor="black", linewidth=0.5, alpha=0.85)

    # 在每段标注时间
    for i in range(len(protocols)):
        # DNS时间标注
        if dns_times[i] > 5:
            ax.text(i, dns_times[i] / 2, f"{dns_times[i]:.1f}ms",
                    ha="center", va="center", fontsize=9, color="white",
                    fontweight="bold")
        # 总时间标注
        total = dns_times[i] + http_times[i]
        ax.text(i, total + 2, f"总计: {total:.1f}ms", ha="center",
                va="bottom", fontsize=10, fontweight="bold")

    ax.set_xlabel("DNS传输协议", fontsize=12)
    ax.set_ylabel("时间 (ms)", fontsize=12)
    ax.set_title("DNS传输协议对网页加载时间的影响", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(protocols, fontsize=11)
    ax.legend(fontsize=11)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)

    _save_figure(fig, filename)


def plot_compliance_heatmap(
    compliance_results: List[ComplianceResult],
    filename: str = "compliance_heatmap.png"
):
    """
    绘制DoH服务器合规性热力图

    对应论文图2：展示各DoH服务器对RFC 8484各项检测指标的通过情况。

    参数:
        compliance_results: ComplianceResult列表
        filename: 输出文件名
    """
    if not compliance_results:
        print("[警告] 无合规性数据，跳过热力图")
        return

    # 提取服务器名和检测项
    servers = [r.server_name for r in compliance_results]
    check_names = [
        "POST方法", "GET方法", "Wire格式",
        "HTTP/2", "Content-Type", "Cache-Control", "EDNS填充"
    ]

    # 构建数据矩阵（1=通过, 0=未通过）
    matrix = []
    for r in compliance_results:
        row = [
            int(r.supports_post),
            int(r.supports_get),
            int(r.supports_wire_format),
            int(r.supports_http2),
            int(r.content_type_correct),
            int(r.cache_control_present),
            int(r.supports_padding),
        ]
        matrix.append(row)

    matrix = np.array(matrix)

    fig, ax = plt.subplots(figsize=(10, max(4, len(servers) * 0.8 + 2)))

    # 绘制热力图
    cmap = plt.cm.RdYlGn  # 红-黄-绿渐变
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)

    # 设置坐标轴标签
    ax.set_xticks(np.arange(len(check_names)))
    ax.set_yticks(np.arange(len(servers)))
    ax.set_xticklabels(check_names, fontsize=10, rotation=30, ha="right")
    ax.set_yticklabels(servers, fontsize=10)

    # 在每个格子中心标注通过/未通过
    for i in range(len(servers)):
        for j in range(len(check_names)):
            text = "PASS" if matrix[i, j] == 1 else "FAIL"
            color = "white" if matrix[i, j] == 0 else "black"
            ax.text(j, i, text, ha="center", va="center",
                    fontsize=9, color=color, fontweight="bold")

    ax.set_title("DoH服务器 RFC 8484 合规性检测", fontsize=14, fontweight="bold")

    # 添加颜色条
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(["未通过", "通过"])

    _save_figure(fig, filename)


def plot_dns_ratio_pie(
    page_results: Dict[str, list],
    filename: str = "dns_ratio_pie.png"
):
    """
    绘制DNS解析时间占比饼图

    展示不同协议下DNS解析时间在总加载时间中的占比。

    参数:
        page_results: 按传输协议分组的PageLoadResult列表
        filename: 输出文件名
    """
    fig, axes = plt.subplots(1, min(4, len(page_results)),
                             figsize=(4 * min(4, len(page_results)), 5))
    if len(page_results) == 1:
        axes = [axes]

    idx = 0
    for transport, results in page_results.items():
        if idx >= len(axes):
            break
        successful = [r for r in results if r.status == "success"]
        if not successful:
            continue

        avg_dns = statistics.mean([r.dns_time_ms for r in successful])
        avg_http = statistics.mean([r.http_time_ms for r in successful])

        ax = axes[idx]
        sizes = [avg_dns, avg_http]
        labels = [f"DNS\n{avg_dns:.1f}ms", f"HTTP\n{avg_http:.1f}ms"]
        colors_pie = ["#2196F3", "#FF9800"]
        explode = (0.05, 0)

        ax.pie(sizes, explode=explode, labels=labels, colors=colors_pie,
               autopct="%1.1f%%", startangle=90, textprops={"fontsize": 9})
        ax.set_title(transport, fontsize=12, fontweight="bold")

        idx += 1

    fig.suptitle("各协议DNS解析时间占比", fontsize=14, fontweight="bold", y=1.02)

    _save_figure(fig, filename)


def generate_all_plots(
    performance_results: Optional[Dict[str, List[QueryResult]]] = None,
    compliance_results: Optional[List[ComplianceResult]] = None,
    page_load_results: Optional[Dict[str, list]] = None
):
    """
    生成所有图表

    参数:
        performance_results: 性能测量结果
        compliance_results: 合规性检测结果
        page_load_results: 网页加载结果
    """
    print("\n" + "=" * 60)
    print("【生成可视化图表】")
    print("=" * 60)

    if performance_results:
        print("\n--- 生成性能对比图 ---")
        plot_performance_comparison(performance_results)
        print("--- 生成查询时间箱线图 ---")
        plot_query_time_boxplot(performance_results)
        print("--- 生成协议开销分解图 ---")
        plot_overhead_breakdown(performance_results)

    if compliance_results:
        print("\n--- 生成合规性热力图 ---")
        plot_compliance_heatmap(compliance_results)

    if page_load_results:
        print("\n--- 生成网页加载影响图 ---")
        plot_page_load_impact(page_load_results)
        print("--- 生成DNS占比饼图 ---")
        plot_dns_ratio_pie(page_load_results)

    print("\n[完成] 所有图表已生成！")
