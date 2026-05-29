# ProxyPool

基于 [fir-proxy](https://github.com/11firefly11/fir-proxy) 二开的图形化代理池。

主要用来做三件事：

1. 获取/导入代理
2. 验证、筛选、轮换代理
3. 在本地开 HTTP / SOCKS5 代理入口

本地服务端口：

- SOCKS5：`127.0.0.1:1800`
- HTTP：`127.0.0.1:1801`

## 功能

- 在线代理源抓取
- TXT / JSON 导入代理
- Fofa / Hunter / Quake 空间测绘搜索
- 订阅转换：Clash / V2Ray / SS / Trojan / VLESS / Hysteria2
- 延迟、速度、匿名度、地区检测
- 按地区、延迟、关键词筛选
- 手动轮换、定时轮换、逐请求轮换
- 自动重测和失效代理清理
- 导出 TXT / CSV / JSON

## 安装

```bash
pip install -r requirements.txt
```

运行：

```bash
python main.py
```

建议 Python 3.10+。

## 订阅转换

订阅转换依赖 Docker 和 mihomo。

先确认 Docker 可用：

```bash
docker version
```

程序会自动启动容器：

```text
proxypool-mihomo
```

退出程序时会尝试清理这个容器。

## 配置

配置模板见：

```text
config.example.json
```

里面可以配置：

- 验证线程数
- 失败清理阈值
- 自动重测
- Fofa / Hunter 查询
- 订阅链接

空间测绘 Key 也可以用环境变量：

```text
PROXYPOOL_FOFA_KEY
PROXYPOOL_QUAKE_KEY
PROXYPOOL_HUNTER_KEY
```

## 导入格式

TXT 示例：

```text
1.2.3.4:8080
http://1.2.3.4:8080
socks5://1.2.3.4:1080
socks5,1.2.3.4:1080
```

JSON 示例：

```json
[
  {"protocol": "socks5", "proxy": "1.2.3.4:1080"},
  {"url": "http://5.6.7.8:8080"},
  {"ip": "8.8.8.8", "port": 8080, "protocol": "http"}
]
```

## 本地使用

启动服务后，在软件里配置代理：

```text
HTTP   127.0.0.1:1801
SOCKS5 127.0.0.1:1800
```

命令行测试：

```bash
curl -x http://127.0.0.1:1801 https://httpbin.org/ip
curl --socks5 127.0.0.1:1800 https://httpbin.org/ip
```

## 说明

这个版本在原项目基础上加了订阅转换、空间测绘搜索、逐请求轮换、自动重测，以及一些稳定性处理。

仅用于学习和自用测试。
