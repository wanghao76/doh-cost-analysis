# DNS-over-HTTPS 实证研究

> 论文复现项目 — **"An Empirical Study of the Cost of DNS-over-HTTPS"** (ACM IMC 2019)

## 项目简介

本项目基于论文 "An Empirical Study of the Cost of DNS-over-HTTPS" 进行代码实现，完整复现了论文中的四大核心实验：

1. **DoH 服务器合规性检测** — 检测公共 DoH 服务器对 RFC 8484 标准的支持程度
2. **传输协议性能对比** — 对比 DNS-UDP / DoT / DoH 三种协议的查询延迟
3. **协议开销量化分析** — 量化加密 DNS 协议相比传统 DNS 的额外开销
4. **网页加载时间影响** — 评估 DoH 对实际网页加载速度的影响

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10 |
| 环境管理 | Conda |
| DNS 协议 | dnspython (DNS/DoT)、httpx (DoH/HTTP2) |
| HTTP 请求 | requests |
| 数据可视化 | matplotlib、numpy |
| 测试框架 | pytest |
| 数据格式 | CSV (结果导出)、JSON (配置) |

---

## 项目结构

```
cn_proj/
├── main.py                    # 主入口（支持命令行参数）
├── environment.yml            # Conda 环境配置
├── requirements.txt           # pip 依赖
├── config/
│   └── servers.json           # DNS 服务器配置
├── src/
│   ├── dns_client/            # DNS 客户端（3种协议）
│   │   ├── traditional_dns.py #   传统 DNS (UDP)
│   │   ├── dot_client.py      #   DNS-over-TLS
│   │   └── doh_client.py      #   DNS-over-HTTPS
│   ├── compliance/
│   │   └── doh_compliance.py  # RFC 8484 合规性检测
│   ├── measurement/
│   │   ├── performance.py     # 跨协议性能测量
│   │   └── page_load.py       # 网页加载时间影响
│   ├── visualization/
│   │   └── plots.py           # 图表生成（6种）
│   └── utils/
│       └── helpers.py         # 工具函数
├── tests/                     # 测试（24个用例，全部通过）
│   ├── test_dns_clients.py
│   ├── test_compliance.py
│   ├── test_performance.py
│   ├── test_page_load.py
│   └── test_visualization.py
├── results/                   # 实验结果（CSV + PNG）
├── TECHNICAL_DOC.md           # 详细技术文档
└── README.md                  # 本文件
```

---

## 快速开始

### 1. 创建 Conda 环境

```bash
conda env create -f environment.yml
conda activate doh_study
```

或者使用 pip：
```bash
pip install -r requirements.txt
```

### 2. 运行全部实验

```bash
python main.py
```

### 3. 快速模式（减少重复次数）

```bash
python main.py --quick
```

### 4. 运行指定实验

```bash
# 仅合规性检测
python main.py -e compliance

# 仅性能对比
python main.py -e performance

# 仅网页加载测试
python main.py -e pageload

# 仅生成图表
python main.py -e visualize
```

### 5. 运行测试

```bash
# 全部测试
python -m pytest tests/ -v

# 单模块测试
python -m pytest tests/test_dns_clients.py -v -s
```

---

## 实验结果

### 实验一：DoH 合规性检测

检测 4 个公共 DoH 服务器对 RFC 8484 的 7 项指标：

| 服务器 | POST | GET | Wire格式 | HTTP/2 | Content-Type | Cache-Control | EDNS填充 |
|--------|------|-----|----------|--------|-------------|--------------|----------|
| Google | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Cloudflare | PASS | PASS | PASS | PASS | PASS | FAIL | PASS |
| Quad9 | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| AliDNS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |

### 实验二：协议性能对比

```
基准 (传统DNS UDP): ~26ms
DoT:      ~154ms (额外开销: +128ms, +491%)
DoH-POST: ~85ms  (额外开销: +59ms,  +228%)
DoH-GET:  ~92ms  (额外开销: +66ms,  +252%)
```

### 实验三：网页加载影响

不同协议下 DNS 解析时间占总加载时间的比例：
- DNS-UDP: 6.9%
- DoT: 45.9%
- DoH-POST: 34.9%
- DoH-GET: 40.2%

### 生成的图表

运行实验后在 `results/` 目录生成 6 种可视化图表：
- `performance_comparison.png` — 协议性能对比柱状图
- `query_time_boxplot.png` — 查询时间分布箱线图
- `overhead_breakdown.png` — 协议开销分解图
- `compliance_heatmap.png` — 合规性热力图
- `page_load_impact.png` — 网页加载影响图
- `dns_ratio_pie.png` — DNS 时间占比饼图

---

## 论文信息

- **标题**: An Empirical Study of the Cost of DNS-over-HTTPS
- **作者**: Timm Bottger, Felix Cuadrado, Gianni Antichi, Eder Leao Fernandes, Gareth Tyson, Ignacio Castro, Steve Uhlig
- **会议**: ACM Internet Measurement Conference (IMC) 2019
- **arXiv**: [1909.06192](https://arxiv.org/abs/1909.06192)

---

## 相关技术标准

- [RFC 8484](https://datatracker.ietf.org/doc/html/rfc8484) — DNS Queries over HTTPS (DoH)
- [RFC 7858](https://datatracker.ietf.org/doc/html/rfc7858) — DNS over Transport Layer Security (DoT)
- [RFC 7830](https://datatracker.ietf.org/doc/html/rfc7830) — The EDNS(0) Padding Option
