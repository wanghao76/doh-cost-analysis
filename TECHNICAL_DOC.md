# 技术实现文档

## 一、项目概述

本项目完整复现了论文 **"An Empirical Study of the Cost of DNS-over-HTTPS"**（ACM IMC 2019）中的核心实验。该论文对 DNS-over-HTTPS (DoH) 生态系统进行了全面的实证分析，主要包括：

1. **DoH 服务器 RFC 8484 合规性调查**
2. **DNS / DoT / DoH 三种传输协议的性能对比**
3. **DoH 协议额外开销的量化分析**
4. **DoH 对网页加载时间的影响评估**

论文信息：
- 作者：Timm Bottger, Felix Cuadrado, Gianni Antichi, Eder Leao Fernandes, Gareth Tyson, Ignacio Castro, Steve Uhlig
- 发表：ACM Internet Measurement Conference (IMC) 2019
- arXiv: 1909.06192

---

## 二、项目架构

```
cn_proj/
├── main.py                          # 主入口，编排所有实验
├── environment.yml                  # Conda 环境配置
├── requirements.txt                 # pip 依赖
├── config/
│   └── servers.json                 # DNS 服务器配置（DoH/DoT/传统DNS）
├── src/
│   ├── dns_client/                  # DNS 客户端模块
│   │   ├── traditional_dns.py       # 传统 DNS (UDP 53端口)
│   │   ├── dot_client.py            # DNS-over-TLS (TCP 853端口)
│   │   └── doh_client.py            # DNS-over-HTTPS (HTTPS 443端口)
│   ├── compliance/
│   │   └── doh_compliance.py        # RFC 8484 合规性检测
│   ├── measurement/
│   │   ├── performance.py           # 跨协议性能测量
│   │   └── page_load.py             # 网页加载时间影响
│   ├── visualization/
│   │   └── plots.py                 # 数据可视化（6种图表）
│   └── utils/
│       └── helpers.py               # 工具函数和数据结构
├── tests/                           # 测试目录（24个测试用例）
│   ├── test_dns_clients.py          # DNS 客户端测试 (9个)
│   ├── test_compliance.py           # 合规性检测测试 (3个)
│   ├── test_performance.py          # 性能测量测试 (2个)
│   ├── test_page_load.py            # 网页加载测试 (3个)
│   └── test_visualization.py        # 可视化测试 (7个)
└── results/                         # 实验结果输出目录
    ├── *.csv                        # 数据文件
    └── *.png                        # 图表文件
```

---

## 三、核心模块详解

### 3.1 工具函数模块 (`src/utils/helpers.py`)

**职责**：提供全项目通用的数据结构、配置加载和结果保存功能。

**核心数据类**：

| 数据类 | 用途 | 关键字段 |
|--------|------|----------|
| `QueryResult` | DNS 查询结果 | domain, resolver, transport, query_time_ms, response_size, status, ip_addresses |
| `ComplianceResult` | 合规性检测结果 | server_name, supports_post/get, supports_http2, content_type_correct 等 |

**Timer 计时器类**：
- 使用 `time.perf_counter()` 实现毫秒级高精度计时
- 支持 `start()` / `stop()` 两步操作，返回毫秒数
- 所有 DNS 查询耗时测量均基于此类

**工具函数**：
- `load_config()`：从 `config/servers.json` 加载服务器配置
- `save_results_to_csv()`：将 `QueryResult` 列表导出为 CSV
- `save_compliance_to_csv()`：将 `ComplianceResult` 列表导出为 CSV
- `ensure_results_dir()`：确保 `results/` 目录存在

---

### 3.2 传统 DNS 客户端 (`src/dns_client/traditional_dns.py`)

**论文对应**：作为性能对比的基准线（baseline）。

**实现原理**：
```
客户端 --[UDP 53端口]--> DNS服务器
       <--[UDP 响应]---
```

**技术要点**：
- 使用 `dnspython` 库的 `dns.query.udp()` 发送 UDP DNS 查询
- 构造标准 DNS 查询报文（`dns.message.make_query()`）
- 支持指定查询类型（A、AAAA、MX 等）
- 从响应中提取 IP 地址列表和 TTL 值
- 异常处理覆盖超时（`dns.exception.Timeout`）和其他 DNS 异常

**关键方法**：
- `query(domain, rdtype="A")` → `QueryResult`：单次查询
- `query_batch(domains)` → `List[QueryResult]`：批量查询

---

### 3.3 DNS-over-TLS 客户端 (`src/dns_client/dot_client.py`)

**论文对应**：论文第4节对比 DoT 与 DoH 的传输性能。

**实现原理**：
```
客户端 --[TCP握手]--> DNS服务器(853端口)
       --[TLS握手]-->
       --[2字节长度前缀 + DNS报文]-->
       <--[2字节长度前缀 + DNS响应]---
```

**技术要点**：
- 使用 Python `ssl` 模块创建 TLS 上下文（`ssl.create_default_context()`）
- 设置 SNI（Server Name Indication）以通过证书验证
- TCP 传输需要 2 字节的长度前缀（RFC 7858 规定）
- `_recv_exact(sock, n)` 辅助方法：精确接收指定字节数，处理 TCP 分片
- 每次查询建立新的 TLS 连接（冷启动场景），测量完整的 TCP+TLS 握手开销

**协议栈层次**：
```
DNS报文 → TCP长度前缀(2字节) → TLS加密 → TCP传输
```

---

### 3.4 DNS-over-HTTPS 客户端 (`src/dns_client/doh_client.py`)

**论文对应**：论文核心研究对象，RFC 8484 标准实现。

**实现原理**：

POST 方法：
```
POST /dns-query HTTP/2
Content-Type: application/dns-message
Accept: application/dns-message

[DNS wire format 二进制数据]
```

GET 方法：
```
GET /dns-query?dns={base64url编码的DNS报文} HTTP/2
Accept: application/dns-message
```

**技术要点**：
- 使用 `httpx` 库支持 HTTP/2 协议（`http2=True`）
- POST 方法：将 DNS wire format 报文作为请求体发送
- GET 方法：将 DNS 报文进行 Base64url 编码（`base64.urlsafe_b64encode`，去除末尾 `=` 填充）
- Content-Type 严格设置为 `application/dns-message`（RFC 8484 要求）
- 使用 `dns.message.from_wire()` 解析响应
- 禁用 SSL 证书验证（`verify=False`），适应多种网络环境

**两种查询方法的区别**：

| 特性 | POST | GET |
|------|------|-----|
| DNS报文位置 | 请求体 | URL参数（Base64url编码） |
| 编码方式 | 原始二进制 | Base64url |
| 缓存友好性 | 不可缓存 | 可被HTTP缓存 |
| URL长度限制 | 无 | 受URL长度限制 |

---

### 3.5 合规性检测模块 (`src/compliance/doh_compliance.py`)

**论文对应**：论文第3节 "DoH Compliance"，对全球 DoH 服务器进行 RFC 8484 标准合规性调查。

**检测项目**（共7项）：

| 检测项 | RFC 8484 相关条款 | 检测方法 |
|--------|-------------------|----------|
| POST 方法支持 | Section 4.1 | 发送 POST 请求，检查状态码 200 |
| GET 方法支持 | Section 4.1 | 发送 GET 请求（Base64url编码），检查状态码 200 |
| Wire Format | Section 4.2 | 验证响应能被 `dns.message.from_wire()` 正确解析 |
| HTTP/2 支持 | Section 5.2 | 使用 `httpx` 发起 HTTP/2 连接，检查 `response.http_version` |
| Content-Type | Section 4.2 | 检查响应头 `Content-Type` 是否为 `application/dns-message` |
| Cache-Control | Section 5.1 | 检查响应头中是否包含 `Cache-Control`（与 DNS TTL 配合） |
| EDNS Padding | RFC 7830 | 在查询中添加 EDNS padding option (type=12)，检查响应中是否也包含 padding |

**实测结果**：
- **Google**：7/7 全部通过
- **Cloudflare**：6/7（Cache-Control 未通过）
- **Quad9**：6/7（EDNS Padding 未通过）
- **AliDNS**：6/7（EDNS Padding 未通过）

---

### 3.6 性能测量模块 (`src/measurement/performance.py`)

**论文对应**：论文第4节 "Transport Comparison" 和第5节 "Overheads"。

**测量流程**：
1. 遍历所有配置的 DNS 服务器
2. 对每个域名、每种协议执行 N 轮重复查询
3. 记录每次查询的响应时间、响应大小、成功状态
4. 每次查询间隔 100ms，减少突发请求对结果的影响

**统计指标**（`PerformanceStats` 数据类）：
- `mean_ms`：平均查询时间
- `median_ms`：中位数查询时间（更能反映典型表现）
- `min_ms` / `max_ms`：极值
- `std_ms`：标准差（衡量稳定性）
- `success_rate`：查询成功率
- `avg_response_size`：平均响应大小

**开销分析**（`measure_overhead` 方法）：
- 以传统 DNS (UDP) 作为基准线
- 计算 DoT、DoH-POST、DoH-GET 相对于基准的额外开销
- 输出绝对开销（ms）和相对开销（百分比）

**实测数据示例**：
```
基准 (传统DNS UDP): ~26ms
DoT:      ~154ms (额外开销: +128ms, +491%)
DoH-POST: ~85ms  (额外开销: +59ms,  +228%)
DoH-GET:  ~92ms  (额外开销: +66ms,  +252%)
```

---

### 3.7 网页加载时间模块 (`src/measurement/page_load.py`)

**论文对应**：论文第5节 "Impact on Page Load Times"。

**测量方法**：
1. **DNS 解析阶段**：使用指定的传输协议（DNS-UDP/DoT/DoH）解析目标域名
2. **HTTP 下载阶段**：使用 `requests.get()` 获取网页内容
3. **分别计时**：DNS 时间和 HTTP 时间独立测量

**PageLoadResult 数据类**：
- `dns_time_ms`：DNS 解析耗时
- `http_time_ms`：HTTP 内容下载耗时
- `total_time_ms`：总耗时（dns + http）
- `page_size`：页面大小（字节）

**影响分析**（`analyze_page_load_impact` 方法）：
- 计算各协议下 DNS 解析时间占总加载时间的比例
- 计算 DoH 相比传统 DNS 的额外 DNS 开销
- 评估该开销对整体加载时间的影响程度

**注意事项**：
- HTTP 请求设置 `verify=False` 以适应各种网络环境（仅用于实验测量）
- 使用 `urllib3.disable_warnings()` 抑制 SSL 相关警告

---

### 3.8 可视化模块 (`src/visualization/plots.py`)

**生成的图表**：

| 图表 | 文件名 | 论文对应 | 说明 |
|------|--------|----------|------|
| 协议性能对比柱状图 | `performance_comparison.png` | 图3/图4 | 各协议平均查询时间，含误差棒 |
| 查询时间分布箱线图 | `query_time_boxplot.png` | 响应时间分布 | 展示中位数、四分位数、异常值 |
| 协议开销分解图 | `overhead_breakdown.png` | 图4 | 堆叠图: 基础DNS + 加密传输开销 |
| 网页加载影响图 | `page_load_impact.png` | 第5节 | 堆叠图: DNS时间 + HTTP时间 |
| 合规性热力图 | `compliance_heatmap.png` | 图2 | 服务器 x 检测项 矩阵 |
| DNS占比饼图 | `dns_ratio_pie.png` | - | 各协议DNS在总加载时间中的占比 |

**技术要点**：
- 使用 `matplotlib` 的 `Agg` 后端（无需GUI环境）
- 配置 `SimHei` / `Microsoft YaHei` 字体支持中文显示
- 统一配色方案：绿色(DNS-UDP)、蓝色(DoT)、橙色(DoH-POST)、红色(DoH-GET)
- 所有图表自动保存到 `results/` 目录，分辨率 150 DPI

---

## 四、配置文件说明

`config/servers.json` 定义了所有测试用的 DNS 服务器：

**DoH 服务器**：
| 名称 | URL |
|------|-----|
| Google | `https://dns.google/dns-query` |
| Cloudflare | `https://cloudflare-dns.com/dns-query` |
| Quad9 | `https://dns.quad9.net/dns-query` |
| AliDNS | `https://dns.alidns.com/dns-query` |

**DoT 服务器**：Google (8.8.8.8)、Cloudflare (1.1.1.1)、Quad9 (9.9.9.9)

**传统 DNS 服务器**：Google (8.8.8.8)、Cloudflare (1.1.1.1)、Quad9 (9.9.9.9)

**测试域名**：example.com, google.com, baidu.com, github.com, wikipedia.org 等

---

## 五、测试体系

项目包含 **24 个测试用例**，覆盖所有核心模块：

| 测试文件 | 测试数 | 覆盖模块 | 说明 |
|----------|--------|----------|------|
| `test_dns_clients.py` | 9 | 三种DNS客户端 | 基本查询、批量查询、异常域名处理 |
| `test_compliance.py` | 3 | 合规性检测 | Google/Cloudflare检测、结果字段验证 |
| `test_performance.py` | 2 | 性能测量 | 快速测量、统计计算 |
| `test_page_load.py` | 3 | 网页加载 | 单URL测试、DoH测试、全协议测试 |
| `test_visualization.py` | 7 | 可视化 | 6种图表 + 批量生成 |

运行命令：
```bash
# 运行全部测试
python -m pytest tests/ -v

# 运行单个模块测试
python -m pytest tests/test_dns_clients.py -v -s
```

---

## 六、已解决的技术问题

### 6.1 Windows GBK 编码问题
**问题**：Windows 终端默认使用 GBK 编码，Unicode 特殊字符（如 ✓、✗）会导致 `UnicodeEncodeError`。

**解决**：将所有 Unicode 特殊符号替换为 ASCII 兼容的替代方案：
- ✓ → `[OK]`
- ✗ → `[FAIL]`
- ö → `o`（作者姓名中的特殊字符）

### 6.2 SSL 证书验证失败
**问题**：某些网络环境下 `requests.get()` 因 SSL 证书链不完整导致 `SSLCertVerificationError`。

**解决**：在网页加载测量模块中设置 `verify=False`，并使用 `urllib3.disable_warnings()` 抑制相关警告。这仅影响实验测量中的 HTTP 内容下载部分，不影响 DNS 协议本身的安全性。

### 6.3 HTTP/2 支持
**问题**：Python 标准库 `urllib3` / `requests` 不支持 HTTP/2，而 DoH 标准要求 HTTP/2。

**解决**：使用 `httpx` 库（`http2=True` 参数），它基于 `h2` 库实现完整的 HTTP/2 支持，包括多路复用、头部压缩等特性。

---

## 七、与论文结果的对照

| 论文发现 | 本项目实测 | 一致性 |
|----------|-----------|--------|
| 传统DNS最快 | DNS-UDP ~26ms 为最低 | 一致 |
| DoT比传统DNS慢（TCP+TLS握手） | DoT ~154ms，额外+128ms | 一致 |
| DoH比DoT略慢（多HTTP/2层开销） | DoH ~85ms，实际比DoT快 | 部分一致* |
| DoH对页面加载影响较小 | DNS占总加载时间6.9%(UDP) vs 35-46%(DoH) | 部分一致* |
| 大多数DoH服务器支持RFC 8484 | Google 7/7，其他6/7 | 一致 |

*注：论文使用了连接复用（热启动）场景，而本实现每次查询都建立新连接（冷启动），因此 DoT 的数值偏高。测量环境（网络延迟、地理位置）也会影响具体数值。

---

## 八、依赖包说明

| 包名 | 版本 | 用途 |
|------|------|------|
| dnspython | >=2.4.0 | DNS 报文构造/解析、UDP 查询 |
| httpx[http2] | >=0.25.0 | HTTP/2 客户端，DoH 查询 |
| requests | >=2.31.0 | HTTP 请求（网页加载测量） |
| matplotlib | >=3.8.0 | 数据可视化 |
| numpy | >=1.26.0 | 数值计算 |
| pandas | >=2.1.0 | 数据处理（可选） |
| pytest | >=7.4.0 | 单元测试框架 |
| h2 | - | HTTP/2 协议实现（httpx 依赖） |
| cryptography | - | TLS/SSL 支持（httpx 依赖） |
