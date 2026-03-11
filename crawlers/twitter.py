"""
Twitter/X 爬虫 — 基于 twscrape
twscrape 调用的是 Twitter 网页版同款内部 GraphQL API，完全免费，不依赖付费官方 API。

反风控策略：
  1. 账号池 — 多个账号轮换使用，单号请求量降低
  2. 代理 IP — 每个账号绑定不同代理，规避 IP 关联
  3. 速率限制 — 随机延迟，遇到限流自动退避
  4. Cookie 复用 — 用现有 auth_token/ct0，不触发登录行为

账号池配置（.env）：
  # 单账号（Cookie 方式）
  TWITTER_COOKIES=auth_token=xxx; ct0=xxx
  # 多账号（JSON 数组，每个账号可绑定不同代理）
  TWITTER_ACCOUNTS=[
    {"username":"acc1","password":"p1","email":"e1@x.com","proxy":"http://proxy1:port"},
    {"username":"acc2","cookies":"auth_token=yyy; ct0=yyy","proxy":"socks5://proxy2:port"}
  ]
"""

import asyncio
import json
import os
import re
from typing import Optional

from twscrape import API
from rich.console import Console

from .base import BaseCrawler
from utils.proxy import get_proxy_pool, RateLimiter

console = Console()

_rate_limiter = RateLimiter(min_delay=2.0, max_delay=5.0)


def _extract_email(text: str) -> str:
    """从 bio 文本中提取邮箱地址"""
    m = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return m.group(0) if m else ""


def _parse_cookie(cookie_str: str, key: str) -> str:
    cookie_str = cookie_str.strip().strip("'\"")
    m = re.search(rf'(?:^|;\s*){re.escape(key)}=([^;]+)', cookie_str)
    return m.group(1).strip() if m else ""


class TwitterCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("twitter")
        self._api: Optional[API] = None
        self._proxy_pool = get_proxy_pool()

    # ─── twscrape 初始化：支持单账号 Cookie 和多账号池 ────────────────────────

    async def _get_api(self) -> API:
        if self._api is not None:
            return self._api

        api = API()

        # 方式1：多账号 JSON 池
        accounts_raw = os.getenv("TWITTER_ACCOUNTS", "").strip()
        if accounts_raw:
            try:
                accounts = json.loads(accounts_raw)
                for acc in accounts:
                    proxy = acc.get("proxy") or self._proxy_pool.get()
                    cookies = acc.get("cookies", "")
                    if cookies:
                        auth_token = _parse_cookie(cookies, "auth_token")
                        ct0 = _parse_cookie(cookies, "ct0")
                        cookie_str = f"auth_token={auth_token}; ct0={ct0}"
                    else:
                        cookie_str = None
                    await api.pool.add_account(
                        username=acc["username"],
                        password=acc.get("password", "__placeholder__"),
                        email=acc.get("email", "placeholder@example.com"),
                        email_password=acc.get("email_password", "placeholder"),
                        cookies=cookie_str,
                        proxy=proxy,
                    )
                console.log(f"[green]twscrape 账号池: 已加载 {len(accounts)} 个账号[/green]")
            except Exception as e:
                console.log(f"[red]解析 TWITTER_ACCOUNTS 失败: {e}[/red]")

        # 方式2：单账号 Cookie（最常用）
        elif self.auth.cookies:
            auth_token = _parse_cookie(self.auth.cookies, "auth_token")
            ct0 = _parse_cookie(self.auth.cookies, "ct0")
            if auth_token and ct0:
                proxy = self._proxy_pool.get()
                await api.pool.add_account(
                    username=self.auth.username or "cookie_user",
                    password=self.auth.password or "__placeholder__",
                    email="placeholder@example.com",
                    email_password="placeholder",
                    cookies=f"auth_token={auth_token}; ct0={ct0}",
                    proxy=proxy,
                )
                proxy_info = f", 代理: {proxy[:25]}..." if proxy else ", 无代理"
                console.log(f"[green]twscrape: Cookie 已注入 (auth_token: {auth_token[:8]}...{proxy_info})[/green]")
            else:
                console.log("[red]Cookie 缺少 auth_token 或 ct0[/red]")

        # 方式3：账号密码登录
        elif self.auth.has_credentials():
            proxy = self._proxy_pool.get()
            await api.pool.add_account(
                username=self.auth.username,
                password=self.auth.password,
                email=os.getenv("TWITTER_EMAIL", ""),
                email_password=os.getenv("TWITTER_EMAIL_PASSWORD", ""),
                proxy=proxy,
            )
            console.log("[cyan]twscrape: 账号密码登录中...[/cyan]")
            await api.pool.login_all()

        else:
            console.log("[yellow]未配置 Twitter 认证，将使用游客模式（内容有限）[/yellow]")

        self._api = api
        return api

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, coro).result()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    # ─── 公开方法 ──────────────────────────────────────────────────────────────

    def get_profile(self, username: str) -> dict:
        _rate_limiter.wait()
        return self._run(self._get_profile_async(username.lstrip("@")))

    def search(self, query: str, limit: int = 10) -> list[dict]:
        _rate_limiter.wait()
        return self._run(self._search_async(query, limit))

    def get_hashtag(self, hashtag: str, limit: int = 10) -> list[dict]:
        _rate_limiter.wait()
        return self._run(self._search_async(f"#{hashtag.lstrip('#')}", limit))

    def get_followers(self, username: str, limit: int = 100) -> list[dict]:
        """获取指定用户的粉丝列表"""
        _rate_limiter.wait()
        return self._run(self._get_user_relations_async(username, "followers", limit))

    def get_following(self, username: str, limit: int = 100) -> list[dict]:
        """获取指定用户正在关注的列表"""
        _rate_limiter.wait()
        return self._run(self._get_user_relations_async(username, "following", limit))

    # ─── 异步实现 ──────────────────────────────────────────────────────────────

    async def _get_profile_async(self, username: str) -> dict:
        api = await self._get_api()
        try:
            user = await api.user_by_login(username)
        except Exception as e:
            err = str(e)
            if "rate limit" in err.lower() or "429" in err:
                _rate_limiter.on_rate_limited()
            else:
                console.log(f"[red]获取用户失败: {e}[/red]")
            return {"username": username, "error": err}

        if not user:
            return {"username": username, "error": "用户不存在"}

        _rate_limiter.on_success()
        tweets = []
        try:
            async for tweet in api.user_tweets(user.id, limit=10):
                tweets.append({
                    "text": tweet.rawContent or "",
                    "likes": str(tweet.likeCount or 0),
                    "retweets": str(tweet.retweetCount or 0),
                    "replies": str(tweet.replyCount or 0),
                    "timestamp": tweet.date.isoformat() if tweet.date else "",
                    "url": f"https://x.com/{username}/status/{tweet.id}",
                })
        except Exception as e:
            console.log(f"[yellow]获取推文列表出错: {e}[/yellow]")

        return {
            "username": user.username,
            "display_name": user.displayname or "",
            "bio": user.rawDescription or "",
            "email": _extract_email(user.rawDescription or ""),
            "phone": "",
            "followers_count": str(user.followersCount or 0),
            "following_count": str(user.friendsCount or 0),
            "tweet_count": str(user.statusesCount or 0),
            "location": user.location or "",
            "website": str(user.profileUrl or ""),
            "joined_date": user.created.isoformat() if user.created else "",
            "verified": bool(user.verified or getattr(user, "isBlueVerified", False)),
            "recent_tweets": tweets,
            "source": "twscrape",
            "url": f"https://x.com/{user.username}",
        }

    async def _get_user_relations_async(self, username: str, relation: str, limit: int) -> list[dict]:
        """relation: 'followers' 或 'following'"""
        api = await self._get_api()

        # 先拿 user_id
        try:
            user = await api.user_by_login(username.lstrip("@"))
        except Exception as e:
            console.log(f"[red]获取用户失败: {e}[/red]")
            return []
        if not user:
            return []

        _rate_limiter.on_success()
        results = []
        iter_fn = api.followers if relation == "followers" else api.following
        try:
            async for u in iter_fn(user.id, limit=limit):
                _rate_limiter.wait()
                results.append({
                    "username": u.username,
                    "display_name": u.displayname or "",
                    "bio": u.rawDescription or "",
                    "email": _extract_email(u.rawDescription or ""),
                    "followers_count": str(u.followersCount or 0),
                    "following_count": str(u.friendsCount or 0),
                    "location": u.location or "",
                    "website": str(u.profileUrl or ""),
                    "verified": bool(u.verified or getattr(u, "isBlueVerified", False)),
                    "url": f"https://x.com/{u.username}",
                })
                _rate_limiter.on_success()
        except Exception as e:
            err = str(e)
            if "rate limit" in err.lower() or "429" in err:
                _rate_limiter.on_rate_limited()
            else:
                console.log(f"[red]获取 {relation} 失败: {e}[/red]")

        return results

    async def _search_async(self, query: str, limit: int) -> list[dict]:
        api = await self._get_api()
        results = []
        try:
            async for tweet in api.search(query, limit=limit):
                results.append({
                    "author": tweet.user.displayname if tweet.user else "",
                    "author_handle": tweet.user.username if tweet.user else "",
                    "text": tweet.rawContent or "",
                    "likes": str(tweet.likeCount or 0),
                    "retweets": str(tweet.retweetCount or 0),
                    "replies": str(tweet.replyCount or 0),
                    "timestamp": tweet.date.isoformat() if tweet.date else "",
                    "url": (
                        f"https://x.com/{tweet.user.username}/status/{tweet.id}"
                        if tweet.user else ""
                    ),
                })
                _rate_limiter.on_success()
        except Exception as e:
            err = str(e)
            if "rate limit" in err.lower() or "429" in err:
                _rate_limiter.on_rate_limited()
            else:
                console.log(f"[red]搜索失败: {e}[/red]")

        return results
