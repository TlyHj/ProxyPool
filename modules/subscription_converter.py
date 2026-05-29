# modules/subscription_converter.py

import yaml
import requests
import base64
import urllib.parse
import subprocess
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor


class SubscriptionConverter:
    """
    订阅转换模块：将订阅链接中的节点通过 Docker + mihomo 转换为本地可用的 HTTP/SOCKS5 代理。

    工作流程：
    1. 获取订阅链接内容，解析出节点信息
    2. 为每个节点生成 mihomo 的 listener 配置（每个节点占用一个端口）
    3. 通过 Docker Desktop 启动 mihomo 容器
    4. 返回 127.0.0.1:port 格式的代理列表
    """

    LOCAL_IP = "127.0.0.1"
    START_PORT = 52000
    CONTAINER_NAME = "proxypool-mihomo"

    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        self._config_file_path = None  # 临时配置文件路径

    def log(self, message):
        self.log_queue.put(f"[SubConverter] {message}")

    @staticmethod
    def _mask_url(url):
        """日志中隐藏订阅 URL 的 query、fragment 和长 token。"""
        try:
            parsed = urllib.parse.urlsplit(url)
            path = parsed.path or ""
            if len(path) > 24:
                path = f"{path[:12]}...{path[-8:]}"
            host = parsed.netloc or parsed.hostname or "unknown"
            return urllib.parse.urlunsplit((parsed.scheme, host, path, "", ""))
        except Exception:
            return "<invalid-url>"

    # ============================================================
    # 订阅获取
    # ============================================================
    def _fetch_subscription(self, url):
        """获取单个订阅链接的内容，自动处理 Base64 编码和 YAML 格式。"""
        self.log(f"[*] 正在获取订阅: {self._mask_url(url)}")
        try:
            res = self.session.get(url, timeout=15)
            res.raise_for_status()
            content = res.text.strip()

            # 尝试1: Base64 解码（常见的 V2Ray/SS 订阅格式）
            try:
                decoded = base64.b64decode(content).decode('utf-8')
                decoded = urllib.parse.unquote(decoded)
                lines = [l.strip() for l in decoded.splitlines() if l.strip()]
                if lines:
                    self.log(f"[+] 订阅 Base64 解码成功，获取 {len(lines)} 行")
                    return lines
            except Exception:
                pass

            # 尝试2: YAML 格式（Clash 订阅）
            try:
                data = yaml.safe_load(content)
                if isinstance(data, dict) and 'proxies' in data:
                    self.log(f"[+] 订阅 YAML 解析成功，获取 {len(data['proxies'])} 个节点")
                    return data  # 返回整个 dict，后续特殊处理
            except yaml.YAMLError:
                pass

            # 尝试3: 纯文本行（每行一个节点链接）
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            if lines:
                self.log(f"[+] 订阅纯文本解析，获取 {len(lines)} 行")
                return lines

        except requests.RequestException as e:
            self.log(f"[!] 获取订阅失败 {self._mask_url(url)}: {e}")
        return None

    # ============================================================
    # 节点解析
    # ============================================================
    @staticmethod
    def _base64_decode(data: str) -> str:
        """安全的 Base64 解码，自动补齐 padding。"""
        data += '=' * (-len(data) % 4)
        return base64.urlsafe_b64decode(data.encode()).decode()

    def _parse_hysteria2(self, url):
        """解析 hysteria2:// 协议的节点。"""
        try:
            parsed = urllib.parse.urlparse(url)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else parsed.hostname
            proxy = {
                "name": name,
                "type": "hysteria2",
                "server": parsed.hostname,
                "port": int(parsed.port),
                "password": parsed.username or "",
                "skip-cert-verify": True,
            }
            if params.get('sni'):
                proxy['sni'] = params['sni']
            if params.get('obfs'):
                proxy['obfs'] = params['obfs']
            if params.get('obfs-password'):
                proxy['obfs-password'] = params['obfs-password']
            return proxy
        except Exception as e:
            self.log(f"[!] 解析 Hysteria2 节点失败: {e}")
            return None

    def _parse_ss(self, url):
        """解析 ss:// 协议的节点。"""
        try:
            raw = url[5:]  # 去掉 "ss://"
            remark = ""
            if "#" in raw:
                raw, remark = raw.rsplit("#", 1)

            if "@" in raw:
                user_part, host_part = raw.split("@", 1)
                try:
                    user_decoded = self._base64_decode(user_part)
                except Exception:
                    user_decoded = user_part
            else:
                decoded = self._base64_decode(raw)
                user_decoded, host_part = decoded.split("@", 1)

            cipher, password = user_decoded.split(":", 1)
            server, port_str = host_part.split(":", 1)
            port = int(port_str.split("?")[0].split("/")[0])  # 去掉可能的查询参数

            proxy = {
                "name": urllib.parse.unquote(remark) if remark else f"{server}:{port}",
                "type": "ss",
                "server": server,
                "port": port,
                "password": password,
                "cipher": cipher,
            }
            return proxy
        except Exception as e:
            self.log(f"[!] 解析 SS 节点失败: {e}")
            return None

    def _parse_vmess(self, url):
        """解析 vmess:// 协议的节点。"""
        try:
            raw = url[8:]  # 去掉 "vmess://"
            decoded = base64.b64decode(raw + '=' * (-len(raw) % 4)).decode('utf-8')
            import json
            config = json.loads(decoded)
            proxy = {
                "name": config.get("ps", config.get("add", "vmess")),
                "type": "vmess",
                "server": config.get("add"),
                "port": int(config.get("port")),
                "uuid": config.get("id"),
                "alterId": int(config.get("aid", 0)),
                "cipher": config.get("scy", "auto"),
            }
            net = config.get("net", "tcp")
            if net == "ws":
                proxy["network"] = "ws"
                proxy["ws-opts"] = {
                    "path": config.get("path", "/"),
                    "headers": {"Host": config.get("host", "")}
                }
            elif net == "grpc":
                proxy["network"] = "grpc"
                proxy["grpc-opts"] = {
                    "grpc-service-name": config.get("path", "")
                }
            tls = config.get("tls", "")
            if tls == "tls":
                proxy["tls"] = True
                sni = config.get("sni", config.get("host", ""))
                if sni:
                    proxy["servername"] = sni
                proxy["skip-cert-verify"] = True
            return proxy
        except Exception as e:
            self.log(f"[!] 解析 VMess 节点失败: {e}")
            return None

    def _parse_trojan(self, url):
        """解析 trojan:// 协议的节点。"""
        try:
            parsed = urllib.parse.urlparse(url)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else parsed.hostname
            proxy = {
                "name": name,
                "type": "trojan",
                "server": parsed.hostname,
                "port": int(parsed.port),
                "password": parsed.username or urllib.parse.unquote(parsed.netloc.split('@')[0]),
                "skip-cert-verify": True,
            }
            if params.get('sni'):
                proxy['sni'] = params['sni']
            if params.get('type') == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {
                    'path': params.get('path', '/'),
                    'headers': {'Host': params.get('host', '')}
                }
            return proxy
        except Exception as e:
            self.log(f"[!] 解析 Trojan 节点失败: {e}")
            return None

    def _parse_vless(self, url):
        """解析 vless:// 协议的节点。"""
        try:
            parsed = urllib.parse.urlparse(url)
            params = dict(urllib.parse.parse_qsl(parsed.query))
            name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else parsed.hostname
            proxy = {
                "name": name,
                "type": "vless",
                "server": parsed.hostname,
                "port": int(parsed.port),
                "uuid": parsed.username,
                "skip-cert-verify": True,
            }
            flow = params.get('flow', '')
            if flow:
                proxy['flow'] = flow
            security = params.get('security', '')
            if security == 'tls':
                proxy['tls'] = True
                if params.get('sni'):
                    proxy['servername'] = params['sni']
            elif security == 'reality':
                proxy['tls'] = True
                proxy['reality-opts'] = {
                    'public-key': params.get('pbk', ''),
                    'short-id': params.get('sid', ''),
                }
                if params.get('sni'):
                    proxy['servername'] = params['sni']
            net_type = params.get('type', 'tcp')
            if net_type == 'ws':
                proxy['network'] = 'ws'
                proxy['ws-opts'] = {
                    'path': params.get('path', '/'),
                    'headers': {'Host': params.get('host', '')}
                }
            elif net_type == 'grpc':
                proxy['network'] = 'grpc'
                proxy['grpc-opts'] = {
                    'grpc-service-name': params.get('serviceName', '')
                }
            return proxy
        except Exception as e:
            self.log(f"[!] 解析 VLESS 节点失败: {e}")
            return None

    def _parse_node_line(self, line):
        """根据协议前缀解析单行节点链接。"""
        line = line.strip()
        if line.startswith("hysteria2://") or line.startswith("hy2://"):
            return self._parse_hysteria2(line)
        elif line.startswith("ss://"):
            return self._parse_ss(line)
        elif line.startswith("vmess://"):
            return self._parse_vmess(line)
        elif line.startswith("trojan://"):
            return self._parse_trojan(line)
        elif line.startswith("vless://"):
            return self._parse_vless(line)
        return None

    def _ensure_unique_names(self, nodes):
        """确保所有节点名称唯一（mihomo 要求 proxy name 不重复）。"""
        seen = {}
        for node in nodes:
            name = node.get('name', 'unknown')
            if name in seen:
                seen[name] += 1
                node['name'] = f"{name}_{seen[name]}"
            else:
                seen[name] = 0
        return nodes

    # ============================================================
    # mihomo 配置生成与 Docker 管理
    # ============================================================
    def _generate_mihomo_config(self, all_nodes, output_protocols):
        """
        生成 mihomo 的 YAML 配置。每个节点分配一个端口，使用 mixed 类型 listener。

        Args:
            all_nodes: 解析后的节点字典列表
            output_protocols: 输出协议列表, 如 ['http', 'socks5']

        Returns:
            (config_dict, proxy_list): 配置字典和最终的代理地址列表
        """
        config = {
            # 容器内需要监听所有接口，宿主机暴露范围由 docker -p 绑定到 127.0.0.1 来收敛。
            "allow-lan": True,
            "bind-address": "*",
            "log-level": "warning",
            "dns": {
                "enable": True,
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "default-nameserver": ["8.8.8.8", "114.114.114.114"],
                "nameserver": ["https://doh.pub/dns-query"]
            },
            "listeners": [],
            "proxies": []
        }

        proxy_list = {'http': [], 'socks5': []}
        port_counter = self.START_PORT

        for node in all_nodes:
            listener_name = f"{node['name']}_mixed_{port_counter}"
            config["listeners"].append({
                "name": listener_name,
                "type": "mixed",
                "port": port_counter,
                "proxy": node["name"]
            })
            config["proxies"].append(node)

            # 根据用户选择的输出协议生成代理地址
            # mixed 类型 listener 同时支持 HTTP 和 SOCKS5
            for proto in output_protocols:
                proxy_list[proto].append(f"{self.LOCAL_IP}:{port_counter}")

            port_counter += 1

        end_port = port_counter
        return config, proxy_list, end_port

    def _stop_existing_container(self):
        """停止并移除已存在的 mihomo 容器。"""
        try:
            subprocess.run(
                ["docker", "stop", self.CONTAINER_NAME],
                capture_output=True, timeout=15
            )
            subprocess.run(
                ["docker", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True, timeout=10
            )
            self.log("[*] 已清理旧的 mihomo 容器。")
        except Exception:
            pass  # 容器不存在时忽略

    def _start_docker(self, config_dict, end_port):
        """
        将配置写入临时文件，并启动 Docker 容器运行 mihomo。

        Returns:
            bool: 是否启动成功
        """
        # 先停止旧容器
        self._stop_existing_container()

        # 写入临时配置文件
        try:
            config_dir = os.path.join(tempfile.gettempdir(), "proxypool_mihomo")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.yaml")

            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

            self._config_file_path = config_path
            self.log(f"[+] mihomo 配置已写入: {config_path}")
        except Exception as e:
            self.log(f"[!] 写入配置文件失败: {e}")
            return False

        # 构造 Docker 命令
        port_range = f"{self.START_PORT}-{end_port - 1}"
        abs_config_path = os.path.abspath(config_path)

        cmd = [
            "docker", "run", "-d",
            "--name", self.CONTAINER_NAME,
            "-v", f"{abs_config_path}:/root/.config/mihomo/config.yaml",
            "-p", f"{self.LOCAL_IP}:{port_range}:{port_range}",
            "metacubex/mihomo",
            "-f", "/root/.config/mihomo/config.yaml"
        ]

        self.log(f"[*] 正在启动 Docker 容器...")
        self.log(f"    端口范围: {port_range}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                self.log(f"[!] Docker 启动失败: {result.stderr.strip()}")
                return False

            container_id = result.stdout.strip()[:12]
            self.log(f"[+] Docker 容器启动成功 (ID: {container_id})")

            # 等待 mihomo 初始化
            self.log("[*] 等待 mihomo 初始化 (3秒)...")
            time.sleep(3)
            return True

        except FileNotFoundError:
            self.log("[!] 未找到 docker 命令，请确认 Docker Desktop 已安装并运行。")
            return False
        except subprocess.TimeoutExpired:
            self.log("[!] Docker 启动超时。")
            return False
        except Exception as e:
            self.log(f"[!] Docker 启动异常: {e}")
            return False

    def stop_docker(self):
        """停止 mihomo Docker 容器（在程序退出或清理时调用）。"""
        self._stop_existing_container()

    # ============================================================
    # 主入口
    # ============================================================
    def convert(self, sub_settings, cancel_event=None):
        """
        执行完整的订阅转换流程。

        Args:
            sub_settings: 订阅转换设置字典，包含:
                - enabled: bool
                - urls: list[str] 订阅链接列表
                - output_http: bool 是否输出 HTTP 代理
                - output_socks5: bool 是否输出 SOCKS5 代理
            cancel_event: 取消事件

        Returns:
            dict: {'http': [...], 'socks5': [...]} 代理地址列表
        """
        result = {'http': [], 'socks5': []}

        if not sub_settings.get('enabled', False):
            return result

        urls = sub_settings.get('urls', [])
        urls = [u.strip() for u in urls if u.strip() and u.strip().startswith(('http://', 'https://'))]

        if not urls:
            self.log("[!] 未配置有效的订阅链接。")
            return result

        output_protocols = []
        if sub_settings.get('output_http', False):
            output_protocols.append('http')
        if sub_settings.get('output_socks5', True):
            output_protocols.append('socks5')

        if not output_protocols:
            self.log("[!] 未选择任何输出协议。")
            return result

        self.log(f"[*] 开始订阅转换，共 {len(urls)} 条订阅，输出协议: {', '.join(output_protocols)}")

        # 1. 并发获取所有订阅
        if cancel_event and cancel_event.is_set():
            return result

        all_nodes = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self._fetch_subscription, url): url for url in urls}
            for future in futures:
                if cancel_event and cancel_event.is_set():
                    return result
                try:
                    data = future.result(timeout=20)
                    if data is None:
                        continue

                    # 处理 YAML 格式（Clash 订阅，已经是 proxy dict 列表）
                    if isinstance(data, dict) and 'proxies' in data:
                        for proxy in data['proxies']:
                            if isinstance(proxy, dict) and 'name' in proxy and 'type' in proxy:
                                all_nodes.append(proxy)
                        continue

                    # 处理行列表（每行一个节点链接）
                    if isinstance(data, list):
                        for line in data:
                            if isinstance(line, str):
                                node = self._parse_node_line(line)
                                if node:
                                    all_nodes.append(node)
                except Exception as e:
                    self.log(f"[!] 处理订阅时出错: {e}")

        if not all_nodes:
            self.log("[!] 未能从订阅中解析出任何有效节点。")
            return result

        # 确保节点名唯一
        all_nodes = self._ensure_unique_names(all_nodes)
        self.log(f"[+] 共解析 {len(all_nodes)} 个有效节点。")

        if cancel_event and cancel_event.is_set():
            return result

        # 2. 生成 mihomo 配置
        config_dict, proxy_list, end_port = self._generate_mihomo_config(all_nodes, output_protocols)

        # 3. 启动 Docker
        if cancel_event and cancel_event.is_set():
            return result

        success = self._start_docker(config_dict, end_port)
        if not success:
            return result

        total_count = sum(len(v) for v in proxy_list.values())
        self.log(f"[+] 订阅转换完成! 共生成 {total_count} 个代理地址。")

        return proxy_list
