# modules/rotator.py

import threading
from collections import defaultdict

class ProxyRotator:
    """代理轮换器，负责管理、轮换和筛选代理。"""
    def __init__(self):
        self.all_proxies = []
        self.proxies_by_country = defaultdict(list)
        self.indices = defaultdict(lambda: -1)
        self.current_proxy = None
        # RLock 让内部方法后续扩展时即使发生嵌套调用也不会自锁。
        # get_next_proxy 当前已避免递归回调 set_filters/get_next_proxy，但这里仍保留可重入锁提高健壮性。
        self.lock = threading.RLock()
        
        # 新增：保存当前激活的过滤器状态
        self.current_filter_region = "All"
        self.current_filter_quality_latency_ms = None

    def clear(self):
        """清空所有代理，并重置内部状态。"""
        with self.lock:
            self.all_proxies = []
            self.proxies_by_country.clear()
            self.indices.clear()
            self.current_proxy = None
    
    def set_filters(self, region="All", quality_latency_ms=None):
        """设置轮换器当前使用的筛选条件。"""
        with self.lock:
            self.current_filter_region = region
            self.current_filter_quality_latency_ms = quality_latency_ms

    def add_proxy(self, proxy_info: dict):
        """添加一个新代理，如果代理地址已存在则忽略。"""
        with self.lock:
            proxy_address = proxy_info.get('proxy')
            if any(p.get('proxy') == proxy_address for p in self.all_proxies):
                return 

            proxy_info.setdefault('consecutive_failures', 0)
            proxy_info.setdefault('status', 'Working')
            self.all_proxies.append(proxy_info)
            country = proxy_info.get('location', 'Unknown')
            self.proxies_by_country[country].append(proxy_info)

    def remove_proxy(self, proxy_address: str):
        """根据代理地址移除一个代理。"""
        with self.lock:
            proxy_to_remove = None
            for p_info in self.all_proxies:
                if p_info.get('proxy') == proxy_address:
                    proxy_to_remove = p_info
                    break
            
            if proxy_to_remove:
                self.all_proxies.remove(proxy_to_remove)
                
                country = proxy_to_remove.get('location', 'Unknown')
                if country in self.proxies_by_country:
                    try:
                        self.proxies_by_country[country].remove(proxy_to_remove)
                        if not self.proxies_by_country[country]:
                            del self.proxies_by_country[country]
                    except ValueError:
                        pass
                
                if self.current_proxy and self.current_proxy.get('proxy') == proxy_address:
                    self.current_proxy = None
                return True
            return False

    def report_failure(self, proxy_address: str):
        """
        报告一个代理连接失败，立即将其状态设置为不可用。
        这个方法是线程安全的。

        Returns:
            dict | None: 被更新代理的快照，未找到时返回 None。
        """
        with self.lock:
            for p_info in self.all_proxies:
                if p_info.get('proxy') == proxy_address:
                    p_info['consecutive_failures'] = p_info.get('consecutive_failures', 0) + 1
                    p_info['status'] = 'Unavailable'
                    if self.current_proxy and self.current_proxy.get('proxy') == proxy_address:
                        self.current_proxy = None
                    return dict(p_info)
            return None

    def get_proxy_by_address(self, proxy_address: str):
        """根据代理地址查询代理的详细信息。"""
        with self.lock:
            for p_info in self.all_proxies:
                if p_info.get('proxy') == proxy_address:
                    return p_info
            return None

    def update_proxy(self, proxy_address: str, update_data: dict):
        """更新指定代理的信息，例如状态、延迟等。"""
        with self.lock:
            for p_info in self.all_proxies:
                if p_info.get('proxy') == proxy_address:
                    p_info.update(update_data)
                    return True
            return False

    def get_all_proxies_for_revalidation(self):
        """获取所有代理的副本，用于重新验证。"""
        with self.lock:
            return list(self.all_proxies)

    def get_active_proxies_count(self) -> int:
        """统计当前状态为 'Working' 的代理数量。"""
        with self.lock:
            return sum(1 for p in self.all_proxies if p.get('status') == 'Working')

    def get_available_regions_with_counts(self, quality_latency_ms=None) -> dict:
        """按地区统计 'Working' 状态的代理数量，支持按延迟筛选。"""
        with self.lock:
            counts = defaultdict(int)
            for p_info in self.all_proxies:
                if p_info.get('status') != 'Working':
                    continue
                
                if quality_latency_ms is not None:
                    latency_ms = p_info.get('latency', float('inf')) * 1000
                    if latency_ms > quality_latency_ms:
                        continue

                region = p_info.get('location', 'Unknown')
                counts[region] += 1
            return dict(counts)


    def get_next_proxy(self):
        """根据内部存储的筛选条件，轮换获取下一个可用代理，并按分数排序。"""
        with self.lock:
            def collect_candidates(region, latency_ms):
                candidates = []
                for p in self.all_proxies:
                    if p.get('status') != 'Working':
                        continue

                    region_match = (region == "All" or p.get('location') == region)
                    if not region_match:
                        continue

                    if latency_ms is not None:
                        latency = p.get('latency', float('inf')) * 1000
                        if latency > latency_ms:
                            continue

                    candidates.append(p)
                return candidates

            # 使用内部存储的过滤器
            effective_region = self.current_filter_region
            effective_latency = self.current_filter_quality_latency_ms

            candidate_proxies = collect_candidates(effective_region, effective_latency)
            index_region = effective_region
            index_latency = effective_latency

            if not candidate_proxies:
                # 如果当前条件下无代理, 尝试放宽条件(不限区域和延迟)
                if effective_region != "All" or effective_latency is not None:
                    candidate_proxies = collect_candidates("All", None)
                    index_region = "All"
                    index_latency = None

            if not candidate_proxies:
                self.current_proxy = None
                return None

            candidate_proxies.sort(key=lambda p: p.get('score', 0), reverse=True)
            
            quality_key = f"lt{index_latency}" if index_latency is not None else "any"
            index_key = f"{index_region}_{quality_key}"
            current_idx = self.indices.get(index_key, -1)
            next_idx = (current_idx + 1) % len(candidate_proxies)
            self.indices[index_key] = next_idx
            
            self.current_proxy = candidate_proxies[next_idx]
            return self.current_proxy

    def get_current_proxy(self):
        """获取当前正在使用的代理。"""
        with self.lock:
            if self.current_proxy and self.current_proxy.get('status') != 'Working':
                self.current_proxy = None
            return self.current_proxy

    def set_current_proxy_by_address(self, proxy_address: str):
        """根据地址手动设置当前代理，代理必须可用。"""
        with self.lock:
            for p_info in self.all_proxies:
                if p_info.get('proxy') == proxy_address and p_info.get('status') == 'Working':
                    self.current_proxy = p_info
                    return p_info
            return None
