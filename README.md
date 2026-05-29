# ProxyPool

基于 [11firefly11/fir-proxy](https://github.com/11firefly11/fir-proxy) 二次开发的图形化代理池工具。项目提供代理获取、导入、质量验证、打分、筛选、轮换，以及本地 HTTP/SOCKS5 代理服务能力；二开版本额外加入了空间测绘搜索、订阅转换、自动重测、逐请求轮换和若干稳定性/安全性改进。

> 适合需要临时维护一批可用代理，并通过本机统一入口 `127.0.0.1:1800/1801` 使用代理池的场景。

## 功能特性

- **图形化管理界面**：基于 Tkinter + ttkbootstrap，支持代理列表、实时日志、进度条和右键菜单。
- **多来源代理获取**：支持在线代理源、网页爬取源、本地 TXT/JSON 导入。
- **空间测绘搜索**：支持从 Fofa、Hunter、Quake 搜索 SOCKS5 代理资产。
- **订阅转换**：支持 Clash/V2Ray/SS/Trojan/VLESS/Hysteria2 等常见订阅格式，通过 Docker + mihomo 转成本地代理端口。
- **多阶段质量验证**：TCP 预检、延迟检测、匿名度检测、速度估算、归属地查询。
- **代理打分排序**：根据延迟、速度和匿名度计算分数，优先使用高质量代理。
- **过滤与搜索**：支持按国家/地区、延迟阈值和 IP:PORT 关键字筛选。
- **本地双协议服务**：一键启动本地 HTTP 与 SOCKS5 代理服务。
- **代理轮换**：支持手动轮换、定时自动轮换和逐请求轮换。
- **自动重测**：可定时重新验证代理池，失败次数超阈值后清理代理。
- **导出结果**：支持导出 TXT、CSV、JSON。
- **安全性改进**：订阅 URL 日志脱敏，API Key 支持环境变量，`config.json` 默认不建议提交。

## 相比上游 fir-proxy 的主要二开内容

上游项目已经提供 GUI 代理池、在线/本地代理获取、本地 HTTP/SOCKS5 服务和轮换管理。本二开版本主要增加/调整了：

1. 新增 `modules/subscription_converter.py`：订阅链接解析并通过 mihomo 转换为本地代理。
2. 新增设置窗口中的 **订阅转换** 选项卡。
3. 新增 Fofa / Hunter / Quake 空间测绘搜索入口。
4. 新增自动重测、失败阈值清理、逐请求轮换模式。
5. 优化代理验证流程，预检失败也回传结果，避免进度条卡住。
6. 修复轮换器在过滤条件无匹配时可能自锁的问题。
7. 本地代理服务连接上游失败时，会自动标记代理为不可用。
8. 移除默认硬编码内置代理，改成可选配置项。
9. 增加 `.gitignore` 和 `config.example.json`，降低敏感配置误提交风险。

## 项目结构

```text
ProxyPool/
├── main.py                         # GUI 主入口与任务调度
├── config.example.json             # 配置示例
├── config.json                     # 本地配置，可能包含订阅/API Key，默认不提交
├── requirements.txt                # Python 依赖
├── modules/
│   ├── asset_searcher.py           # Fofa / Quake / Hunter 空间测绘搜索
│   ├── checker.py                  # 代理验证、匿名度/速度/地区检测
│   ├── fetcher.py                  # 在线源与网页源代理获取
│   ├── rotator.py                  # 代理池管理、筛选和轮换
│   ├── server.py                   # 本地 HTTP/SOCKS5 转发服务
│   └── subscription_converter.py   # 订阅解析 + mihomo Docker 转换
└── .runtime/
    └── mihomo_config.yml           # 运行时/参考配置，可按需保留
```

## 环境要求

- Python 3.10+
- Windows / Linux / macOS 均可尝试运行；当前二开工作环境为 Windows。
- 可选：Docker Desktop
  - 只有使用“订阅转换”功能时需要。
  - 程序会启动 `metacubex/mihomo` 容器。

## 安装与运行

```bash
git clone <你的仓库地址> ProxyPool
cd ProxyPool
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Linux/macOS：

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

如果没有创建虚拟环境，也可以直接：

```bash
pip install -r requirements.txt
python main.py
```

## 基本使用

### 1. 获取并验证代理

点击左侧 **获取代理**：

1. 从 `modules/fetcher.py` 中配置的在线源/爬虫源获取代理。
2. 如果设置里启用了订阅转换，会继续从订阅中转换出本地代理。
3. 对所有代理执行 TCP 预检和完整质量验证。
4. 可用代理会进入表格并加入轮换池。

### 2. 导入本地代理

点击 **导入代理**，支持 TXT / JSON。

TXT 支持以下格式：

```text
1.2.3.4:8080
http://1.2.3.4:8080
socks5://1.2.3.4:1080
socks5,1.2.3.4:1080
```

JSON 支持列表格式，常见字段包括：

```json
[
  {"protocol": "socks5", "proxy": "1.2.3.4:1080"},
  {"url": "http://5.6.7.8:8080"},
  {"ip": "8.8.8.8", "port": 8080, "protocol": "http"}
]
```

### 3. 启动本地代理服务

当代理池中有可用代理后，点击 **启动服务**。

本地服务端口：

| 协议 | 地址 |
|---|---|
| SOCKS5 | `127.0.0.1:1800` |
| HTTP | `127.0.0.1:1801` |

在浏览器、命令行工具或其他软件里配置上述代理即可使用代理池。

示例：

```bash
curl -x http://127.0.0.1:1801 https://httpbin.org/ip
curl --socks5 127.0.0.1:1800 https://httpbin.org/ip
```

### 4. 轮换代理

- **手动轮换**：点击 **轮换IP**。
- **定时轮换**：设置间隔秒数，点击 **自动**。
- **逐请求轮换**：将间隔设置为 `0`，再点击 **自动**。此模式下本地服务每个新请求都会从代理池取下一个代理。

轮换会受当前筛选条件影响，例如国家/地区和优质延迟阈值。

### 5. 筛选、搜索和管理

- 国家/地区下拉框：按归属地过滤代理。
- “优质 ms <”：只显示/轮换延迟低于阈值的代理。
- 快速搜索：按 `IP:PORT` 关键字过滤。
- 表格右键：可手动使用或删除某个代理。
- 双击/复制：可复制代理地址。
- 全部重测：重新验证当前池内代理。
- 导出代理：支持 TXT、CSV、JSON。

## 订阅转换功能

订阅转换通过 `modules/subscription_converter.py` 完成，流程为：

1. 获取订阅链接内容。
2. 自动识别 Base64、YAML 或纯文本行格式。
3. 解析节点为 mihomo 支持的 `proxies` 配置。
4. 为每个节点分配本地端口，生成 mixed listener。
5. 启动 Docker 容器 `proxypool-mihomo`。
6. 将 `127.0.0.1:52000+` 端口作为 HTTP/SOCKS5 代理加入验证流程。

使用前请确认 Docker 可用：

```bash
docker version
```

首次使用会拉取镜像：

```bash
docker pull metacubex/mihomo
```

程序退出时会尝试清理容器：

```bash
docker stop proxypool-mihomo
docker rm -f proxypool-mihomo
```

> 注意：订阅转换产生的端口会通过 Docker 发布到宿主机 `127.0.0.1`，避免对局域网暴露。

## 配置说明

首次运行会读取/写入 `config.json`。建议从模板复制：

```bash
cp config.example.json config.json
```

Windows PowerShell：

```powershell
Copy-Item .\config.example.json .\config.json
```

主要配置：

```json
{
  "general": {
    "validation_threads": 100,
    "failure_threshold": 3,
    "auto_retest_enabled": false,
    "auto_retest_interval": 10,
    "builtin_proxy_enabled": false,
    "builtin_proxy": ""
  },
  "auto_fetch": {
    "fofa": {
      "enabled": false,
      "key": "",
      "query": "protocol==\"socks5\" && country==\"CN\" && banner=\"Method:No\"",
      "size": 500
    },
    "hunter": {
      "enabled": false,
      "key": "",
      "query": "app.name=\"SOCKS5\"",
      "size": 100
    }
  },
  "subscription": {
    "enabled": false,
    "urls": [],
    "output_http": false,
    "output_socks5": true
  }
}
```

### API Key 环境变量

为了避免 API Key 明文写入 `config.json`，空间测绘 Key 可通过环境变量提供：

| 平台 | 环境变量 |
|---|---|
| Fofa | `PROXYPOOL_FOFA_KEY` |
| Quake | `PROXYPOOL_QUAKE_KEY` |
| Hunter | `PROXYPOOL_HUNTER_KEY` |

PowerShell 示例：

```powershell
$env:PROXYPOOL_FOFA_KEY="email@example.com:your_fofa_key"
$env:PROXYPOOL_HUNTER_KEY="your_hunter_key"
python main.py
```

Linux/macOS 示例：

```bash
export PROXYPOOL_FOFA_KEY="email@example.com:your_fofa_key"
export PROXYPOOL_HUNTER_KEY="your_hunter_key"
python main.py
```

## 验证逻辑

验证器位于 `modules/checker.py`，主要检测项：

- TCP 端口连通性。
- 访问 `https://www.baidu.com` 测延迟。
- 访问 `http://httpbin.org/get?show_env=1` 判断匿名度。
- 下载测试内容估算速度。
- 通过多个 IP 地理位置 API 查询国家/地区。

代理分数由主程序根据延迟、速度、匿名度计算：

- 延迟越低分数越高。
- 速度越快分数越高。
- `Elite` 匿名度加分最高，其次为 `Anonymous`。

## 常见问题

### 1. 点击“获取代理”后可用数量很少

免费代理源质量波动很大，这是正常现象。建议：

- 导入自己维护的稳定代理列表。
- 开启订阅转换。
- 使用空间测绘搜索后再验证。
- 调低并发或延长超时时间后自行调整代码。

### 2. 订阅转换失败

请检查：

- Docker Desktop 是否启动。
- `docker version` 是否能正常输出。
- 是否能拉取 `metacubex/mihomo` 镜像。
- 端口 `52000+` 是否被占用。

### 3. 本地服务能启动但请求失败

可能原因：

- 当前选中的上游代理已经失效。
- 当前筛选条件下无可用代理。
- 目标站点不接受该代理出口。
- SOCKS4/5、HTTP 协议类型与实际代理不匹配。

可以尝试“全部重测”或切换代理。

### 4. `config.json` 是否可以提交？

不建议。它可能包含订阅链接和 API Key。本项目已在 `.gitignore` 中忽略 `config.json`，请提交 `config.example.json` 作为模板即可。

## 开发与检查

语法检查：

```bash
python -m py_compile main.py modules/*.py
```

Windows PowerShell：

```powershell
$files = @('main.py') + (Get-ChildItem .\modules -Filter '*.py' | ForEach-Object { $_.FullName })
python -m py_compile @files
```

## 致谢

本项目基于 [11firefly11/fir-proxy](https://github.com/11firefly11/fir-proxy) 二次开发，感谢原作者提供的图形化代理池基础实现。

## 免责声明

本项目仅用于学习、测试和自有环境中的代理可用性管理。请遵守目标网站、服务和所在地法律法规，不要将代理用于未授权访问或滥用行为。
