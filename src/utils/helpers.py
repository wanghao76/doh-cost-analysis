"""
工具函数模块
============
提供项目中通用的辅助函数，包括配置加载、时间测量、结果保存等功能。
"""

import json
import os
import time
import csv
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 配置文件路径
CONFIG_PATH = PROJECT_ROOT / "config" / "servers.json"

# 结果输出目录
RESULTS_DIR = PROJECT_ROOT / "results"


@dataclass
class QueryResult:
    """
    DNS查询结果数据类
    ==================
    存储单次DNS查询的完整信息，包括域名、解析IP、耗时、使用的传输协议等。

    属性:
        domain: 查询的域名
        resolver: 解析器名称（如 Google, Cloudflare）
        transport: 传输协议类型（DNS, DoT, DoH）
        query_time_ms: 查询耗时（毫秒）
        response_size: 响应数据大小（字节）
        status: 查询状态（success/error）
        ip_addresses: 解析得到的IP地址列表
        error_message: 错误信息（如果查询失败）
        ttl: DNS记录的TTL值
    """
    domain: str
    resolver: str
    transport: str
    query_time_ms: float
    response_size: int = 0
    status: str = "success"
    ip_addresses: List[str] = field(default_factory=list)
    error_message: str = ""
    ttl: int = 0


@dataclass
class ComplianceResult:
    """
    DoH服务器合规性检测结果
    ========================
    根据RFC 8484标准检测DoH服务器的合规性。

    属性:
        server_name: 服务器名称
        server_url: 服务器URL
        supports_post: 是否支持POST方法
        supports_get: 是否支持GET方法
        supports_wire_format: 是否支持DNS wire format
        supports_http2: 是否支持HTTP/2
        content_type_correct: Content-Type是否正确（application/dns-message）
        cache_control_present: 是否包含Cache-Control头
        supports_padding: 是否支持EDNS padding
        status_code: HTTP状态码
        error_message: 错误信息
    """
    server_name: str
    server_url: str
    supports_post: bool = False
    supports_get: bool = False
    supports_wire_format: bool = False
    supports_http2: bool = False
    content_type_correct: bool = False
    cache_control_present: bool = False
    supports_padding: bool = False
    status_code: int = 0
    error_message: str = ""


def load_config() -> dict:
    """
    加载服务器配置文件

    返回:
        包含所有DNS服务器配置信息的字典
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_results_dir():
    """确保结果输出目录存在"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def save_results_to_csv(results: List[QueryResult], filename: str):
    """
    将查询结果保存为CSV文件

    参数:
        results: QueryResult对象列表
        filename: 输出文件名（不含路径）
    """
    ensure_results_dir()
    filepath = RESULTS_DIR / filename
    if not results:
        return

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            row = asdict(result)
            # 将列表转为逗号分隔的字符串
            row["ip_addresses"] = ",".join(row["ip_addresses"])
            writer.writerow(row)

    print(f"[保存] 结果已保存至: {filepath}")


def save_compliance_to_csv(results: List[ComplianceResult], filename: str):
    """
    将合规性检测结果保存为CSV文件

    参数:
        results: ComplianceResult对象列表
        filename: 输出文件名
    """
    ensure_results_dir()
    filepath = RESULTS_DIR / filename
    if not results:
        return

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))

    print(f"[保存] 合规性结果已保存至: {filepath}")


class Timer:
    """
    高精度计时器
    =============
    用于精确测量DNS查询等操作的耗时（毫秒级）。

    使用方法:
        timer = Timer()
        timer.start()
        # ... 执行操作 ...
        elapsed = timer.stop()  # 返回毫秒数
    """
    def __init__(self):
        self._start = 0.0
        self._elapsed = 0.0

    def start(self):
        """开始计时"""
        self._start = time.perf_counter()

    def stop(self) -> float:
        """
        停止计时并返回耗时

        返回:
            耗时（毫秒）
        """
        self._elapsed = (time.perf_counter() - self._start) * 1000
        return self._elapsed

    @property
    def elapsed_ms(self) -> float:
        """获取最后一次测量的耗时（毫秒）"""
        return self._elapsed
