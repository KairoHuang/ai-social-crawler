"""
Instagram 爬虫 — 基于 instagrapi
使用 Instagram 移动端私有 API，完全免费。

反风控策略：
  1. 设备指纹模拟 — 固定一套真实 Android 设备参数，session 缓存避免频繁登录
  2. 代理 IP — 每个账号绑定固定代理（"一机一号一 IP" 原则）
  3. 随机延迟 — delay_range 模拟人类操作节奏
  4. 请求量控制 — 单次获取不超过合理数量，避免触发批量检测
  5. Session 复用 — 登录后缓存到本地，不重复触发登录行为
"""

import json
import os
import random
from pathlib import Path
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, TwoFactorRequired, BadPassword, PleaseWaitFewMinutes
from rich.console import Console

from .base import BaseCrawler
from utils.proxy import get_proxy_pool, RateLimiter

console = Console()

SESSION_DIR = Path(__file__).parent.parent / "output" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

_rate_limiter = RateLimiter(min_delay=3.0, max_delay=8.0)  # Instagram 更严格，间隔更长

# 模拟常见 Android 设备列表（随机选一个，固定到 session）
DEVICE_PROFILES = [
    {
        "app_version": "269.0.0.18.75",
        "android_version": 26,
        "android_release": "8.0.0",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "OnePlus",
        "device": "ONEPLUS A3010",
        "model": "OnePlus3T",
        "cpu": "qcom",
        "version_code": "314665256",
    },
    {
        "app_version": "269.0.0.18.75",
        "android_version": 28,
        "android_release": "9.0",
        "dpi": "420dpi",
        "resolution": "1080x2220",
        "manufacturer": "samsung",
        "device": "SM-G965F",
        "model": "star2qltecs",
        "cpu": "samsungexynos9810",
        "version_code": "314665256",
    },
    {
        "app_version": "269.0.0.18.75",
        "android_version": 29,
        "android_release": "10.0",
        "dpi": "440dpi",
        "resolution": "1080x2400",
        "manufacturer": "Xiaomi",
        "device": "Mi 10",
        "model": "Mi10",
        "cpu": "qcom",
        "version_code": "314665256",
    },
]


class InstagramCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("instagram")
        self._client: Optional[Client] = None
        self._proxy_pool = get_proxy_pool()

    # ─── 客户端初始化 ──────────────────────────────────────────────────────────

    def _get_client(self) -> Client:
        if self._client is not None:
            return self._client

        if not self.auth.has_credentials():
            raise ValueError("请在 .env 中配置 INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD")

        cl = Client()

        # 注入代理
        proxy = self._proxy_pool.get()
        if proxy:
            cl.set_proxy(proxy)
            console.log(f"[green]Instagram 使用代理: {proxy[:35]}...[/green]")

        # 设备指纹：同一账号始终用同一设备（保持一致性，减少风控触发）
        device_file = SESSION_DIR / f"ig_device_{self.auth.username}.json"
        if device_file.exists():
            device = json.loads(device_file.read_text())
        else:
            device = random.choice(DEVICE_PROFILES)
            device_file.write_text(json.dumps(device, ensure_ascii=False, indent=2))
            console.log(f"[dim]Instagram 设备指纹已生成: {device['manufacturer']} {device['model']}[/dim]")

        cl.set_settings({
            "device_settings": device,
            "user_agent": (
                f"Instagram {device['app_version']} Android "
                f"({device['android_version']}/{device['android_release']}; "
                f"{device['dpi']}; {device['resolution']}; "
                f"{device['manufacturer']}; {device['device']}; "
                f"{device['model']}; {device['cpu']}; en_US; "
                f"{device['version_code']})"
            ),
        })

        cl.delay_range = [2, 5]  # 每次操作随机延迟 2~5 秒

        # 尝试复用 session
        session_file = SESSION_DIR / f"instagram_{self.auth.username}.json"
        if session_file.exists():
            console.log(f"[dim]加载 Instagram session: {session_file.name}[/dim]")
            try:
                cl.load_settings(str(session_file))
                cl.login(self.auth.username, self.auth.password)
                console.log("[green]✓ Instagram session 复用成功[/green]")
                self._client = cl
                return cl
            except (LoginRequired, Exception):
                console.log("[yellow]session 已过期，重新登录...[/yellow]")
                session_file.unlink(missing_ok=True)

        # 全新登录
        self._login(cl, session_file)
        self._client = cl
        return cl

    def _login(self, cl: Client, session_file: Path):
        console.log(f"[cyan]Instagram 登录中 ({self.auth.username})...[/cyan]")
        try:
            cl.login(self.auth.username, self.auth.password)
            cl.dump_settings(str(session_file))
            console.log(f"[green]✓ 登录成功，session 已缓存[/green]")
        except BadPassword:
            raise ValueError("Instagram 密码错误")
        except TwoFactorRequired:
            code = input("Instagram 二步验证码: ").strip()
            cl.login(self.auth.username, self.auth.password, verification_code=code)
            cl.dump_settings(str(session_file))
        except PleaseWaitFewMinutes as e:
            raise ValueError(f"Instagram 触发限流，请稍后再试: {e}")
        except Exception as e:
            raise ValueError(f"Instagram 登录失败: {e}")

    # ─── 公开方法 ──────────────────────────────────────────────────────────────

    def get_profile(self, username: str) -> dict:
        _rate_limiter.wait()
        username = username.lstrip("@")
        cl = self._get_client()

        try:
            user = cl.user_info_by_username(username)
            _rate_limiter.on_success()
        except PleaseWaitFewMinutes:
            _rate_limiter.on_rate_limited()
            return {"username": username, "error": "触发 Instagram 限流，请稍后重试"}
        except Exception as e:
            console.log(f"[red]获取用户失败: {e}[/red]")
            return {"username": username, "error": str(e)}

        recent_posts = []
        try:
            # 单次最多取 12 条，避免触发批量检测
            medias = cl.user_medias(user.pk, amount=12)
            for m in medias:
                recent_posts.append({
                    "caption": (m.caption_text or "")[:200],
                    "likes": str(m.like_count or 0),
                    "comments": str(m.comment_count or 0),
                    "timestamp": m.taken_at.isoformat() if m.taken_at else "",
                    "post_url": f"https://www.instagram.com/p/{m.code}/",
                    "media_type": m.media_type,
                })
        except Exception as e:
            console.log(f"[yellow]获取帖子列表出错: {e}[/yellow]")

        return {
            "username": user.username,
            "full_name": user.full_name or "",
            "bio": user.biography or "",
            "followers_count": str(user.follower_count or 0),
            "following_count": str(user.following_count or 0),
            "posts_count": str(user.media_count or 0),
            "is_verified": user.is_verified,
            "is_private": user.is_private,
            "external_url": str(user.external_url or ""),
            "recent_posts": recent_posts,
            "source": "instagrapi",
            "url": f"https://www.instagram.com/{user.username}/",
        }

    def search(self, query: str, limit: int = 10) -> list[dict]:
        console.log("[yellow]Instagram 不支持关键词搜索，改为话题标签[/yellow]")
        return self.get_hashtag(query.lstrip("#").replace(" ", ""), limit=limit)

    def get_hashtag(self, hashtag: str, limit: int = 10) -> list[dict]:
        _rate_limiter.wait()
        hashtag = hashtag.lstrip("#")
        cl = self._get_client()

        # 每次限制最多 20 条，防止触发批量检测
        fetch_limit = min(limit, 20)

        try:
            medias = cl.hashtag_medias_top(hashtag, amount=fetch_limit)
            _rate_limiter.on_success()
        except PleaseWaitFewMinutes:
            _rate_limiter.on_rate_limited()
            return []
        except Exception as e:
            console.log(f"[yellow]热门帖子失败，尝试最新: {e}[/yellow]")
            try:
                medias = cl.hashtag_medias_recent(hashtag, amount=fetch_limit)
            except Exception as e2:
                console.log(f"[red]获取话题帖子失败: {e2}[/red]")
                return []

        results = []
        for m in medias:
            author = ""
            try:
                author = m.user.username if m.user else ""
            except Exception:
                pass
            results.append({
                "caption": (m.caption_text or "")[:200],
                "likes": str(m.like_count or 0),
                "comments": str(m.comment_count or 0),
                "timestamp": m.taken_at.isoformat() if m.taken_at else "",
                "post_url": f"https://www.instagram.com/p/{m.code}/",
                "author": author,
            })

        return results[:limit]
