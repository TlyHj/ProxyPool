# ProxyPool

基于 [fir-proxy](https://github.com/11firefly11/fir-proxy) 二开的图形化代理池。

仓库地址：

```bash
git clone https://github.com/TlyHj/ProxyPool.git
cd ProxyPool
```

安装运行：

```bash
pip install -r requirements.txt
python main.py
```

本地代理端口：

```text
HTTP   127.0.0.1:1801
SOCKS5 127.0.0.1:1800
```

## 新增功能

- 新增订阅转换，支持 Clash / V2Ray / SS / Trojan / VLESS / Hysteria2 等格式。
- 新增 Docker + mihomo 转换订阅节点为本地 HTTP / SOCKS5 代理端口。
- 新增 Fofa / Hunter / Quake 空间测绘搜索。
- 新增按地区、延迟、关键词筛选代理。
- 新增逐请求轮换模式，间隔设置为 `0` 时每个请求自动切换代理。
- 新增自动重测，可定时重新验证代理池。
- 新增 TXT / CSV / JSON 导出。
- 新增 `config.example.json` 配置模板。

## 优化内容

- 优化代理验证流程，加入 TCP 预检、延迟、速度、匿名度、地区检测。
- 优化代理评分逻辑，按延迟、速度、匿名度综合排序。
- 优化失败代理处理，上游代理连接失败后会自动标记不可用。
- 修复筛选条件无匹配时轮换器可能卡死的问题。
- 优化任务取消和进度显示，预检失败也会正常推进进度。
- 移除默认硬编码内置代理，改为可选配置。
- 订阅链接日志做脱敏处理。
- API Key 支持通过环境变量读取：

```text
PROXYPOOL_FOFA_KEY
PROXYPOOL_QUAKE_KEY
PROXYPOOL_HUNTER_KEY
```

## 说明

仅用于学习和自用测试。
