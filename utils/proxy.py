"""
代理管理模块
支持：
  - 单代理配置（PROXY_URL）
  - 代理池轮换（PROXY_LIST，逗号分隔）
  - 格式：http://user:pass@host:port 或 socks5://host:port
"""

import os
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


@dataclass
class ProxyPool:
    proxies: list[str] = field(default_factory=list)
    _index: int = 0
    _fail_counts: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "ProxyPool":
        pool = cls()
        # 单个代理
        single = os.getenv("PROXY_URL", "").strip()
        if single:
            pool.proxies.append(single)
        # 代理列表（逗号分隔）
        proxy_list_raw = os.getenv("PROXY_LIST", "").strip()
        if proxy_list_raw:
            for p in proxy_list_raw.split(","):
                p = p.strip()
                if p and p not in pool.proxies:
                    pool.proxies.append(p)
        if pool.proxies:
            console.log(f"[green]代理池已加载: {len(pool.proxies)} 个[/green]")
        else:
            console.log("[dim]未配置代理，使用本机 IP（有封号风险）[/dim]")
        return pool

    def has_proxy(self) -> bool:
        return bool(self.proxies)

    def get(self) -> Optional[str]:
        """轮换获取下一个代理"""
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy

    def get_random(self) -> Optional[str]:
        """随机获取一个代理"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def mark_failed(self, proxy: str):
        """标记代理失败，超过阈值则移除"""
        self._fail_counts[proxy] = self._fail_counts.get(proxy, 0) + 1
        if self._fail_counts[proxy] >= 3:
            console.log(f"[yellow]代理 {proxy[:30]}... 失败次数过多，已从池中移除[/yellow]")
            if proxy in self.proxies:
                self.proxies.remove(proxy)
            del self._fail_counts[proxy]

    def to_httpx_dict(self, proxy: Optional[str] = None) -> Optional[dict]:
        """转为 httpx proxies 格式"""
        p = proxy or self.get()
        if not p:
            return None
        return {"http://": p, "https://": p}

    def to_requests_dict(self, proxy: Optional[str] = None) -> Optional[dict]:
        """转为 requests proxies 格式"""
        p = proxy or self.get()
        if not p:
            return None
        return {"http": p, "https": p}


# 全局代理池单例
_pool: Optional[ProxyPool] = None


def get_proxy_pool() -> ProxyPool:
    global _pool
    if _pool is None:
        _pool = ProxyPool.from_env()
    return _pool


# ─── 请求频率控制 ──────────────────────────────────────────────────────────────

class RateLimiter:
    """
    自适应速率限制：
      - 正常请求间隔 min_delay ~ max_delay 秒（随机）
      - 遇到限流响应后自动退避
    """

    def __init__(self, min_delay: float = 1.5, max_delay: float = 4.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._backoff = 0
        self._last_call = 0.0

    def wait(self):
        """在每次请求前调用"""
        now = time.time()
        elapsed = now - self._last_call
        delay = random.uniform(self.min_delay, self.max_delay) + self._backoff
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_call = time.time()

    def on_rate_limited(self):
        """遇到 429 / 限流时调用，指数退避"""
        self._backoff = min(self._backoff * 2 + 10, 120)
        console.log(f"[yellow]触发限流，等待 {self._backoff:.0f}s 后重试...[/yellow]")
        time.sleep(self._backoff)

    def on_success(self):
        """成功后逐渐恢复正常速率"""
        if self._backoff > 0:
            self._backoff = max(0, self._backoff - 2)
