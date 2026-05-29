# ProxyPool

基于 [fir-proxy](https://github.com/11firefly11/fir-proxy) 的图形化代理池进行二开。

新增订阅转换、空间测绘搜索、逐请求轮换、自动重测，并优化了代理验证、失败代理处理和轮换稳定性。

本地代理端口：

```text
HTTP   127.0.0.1:1801
SOCKS5 127.0.0.1:1800
```

## 安装

```bash
git clone https://github.com/TlyHj/ProxyPool.git
cd ProxyPool
pip install -r requirements.txt
python main.py
```

建议使用 Python 3.10+。

## 订阅转换

订阅转换支持 Clash / V2Ray / SS / Trojan / VLESS / Hysteria2 等常见节点格式。

该功能依赖 Docker 和 mihomo 镜像。环境无 Docker 情况下不可用，使用前先确认 Docker 可用：

```bash
docker version
```

程序会自动启动 mihomo 容器：

```text
proxypool-mihomo
```

订阅节点会被转换成本地代理端口，再进入代理池验证流程。

## 配置

配置模板：

```text
config.example.json
```

可配置内容包括：

- 验证线程数
- 失败清理阈值
- 自动重测
- Fofa / Hunter 查询
- 订阅链接
- 输出 HTTP / SOCKS5

空间测绘 Key 可写在配置里，也可以用环境变量：

```text
PROXYPOOL_FOFA_KEY
PROXYPOOL_QUAKE_KEY
PROXYPOOL_HUNTER_KEY
```

仅用于学习和自用测试。

<!-- readme-refresh-1780067011 -->

