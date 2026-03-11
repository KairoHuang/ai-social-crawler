"""
认证模块：支持两种方式
  1. Cookie 注入 — 最稳定，浏览器手动登录后复制 Cookie 字符串
  2. Actions 自动登录 — 用账号密码让 Firecrawl 自动完成登录流程
"""

import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from firecrawl.v2.types import (
    WaitAction,
    ClickAction,
    WriteAction,
    ScreenshotAction,
)
from rich.console import Console

load_dotenv()
console = Console()


@dataclass
class PlatformAuth:
    platform: str
    username: str = ""
    password: str = ""
    cookies: str = ""
    logged_in: bool = False
    headers: dict = field(default_factory=dict)

    def has_cookies(self) -> bool:
        return bool(self.cookies.strip())

    def has_credentials(self) -> bool:
        return bool(self.username.strip() and self.password.strip())

    def to_headers(self) -> dict:
        if self.cookies:
            return {"Cookie": self.cookies}
        return {}


def load_auth(platform: str) -> PlatformAuth:
    """从环境变量加载平台认证信息"""
    p = platform.upper()
    auth = PlatformAuth(
        platform=platform,
        username=os.getenv(f"{p}_USERNAME", ""),
        password=os.getenv(f"{p}_PASSWORD", ""),
        cookies=os.getenv(f"{p}_COOKIES", ""),
    )
    if auth.has_cookies():
        auth.logged_in = True
        auth.headers = auth.to_headers()
    return auth


# ─── 各平台登录 Actions（返回 v4 typed 对象列表）────────────────────────────

def twitter_login_actions(username: str, password: str) -> list[Any]:
    return [
        WaitAction(milliseconds=2000),
        ClickAction(selector="input[autocomplete='username']"),
        WaitAction(milliseconds=500),
        WriteAction(text=username),
        WaitAction(milliseconds=500),
        # "下一步" 按钮
        ClickAction(selector="button[data-testid='ocfEnterTextNextButton'], div[role='button']:nth-child(6)"),
        WaitAction(milliseconds=1500),
        ClickAction(selector="input[name='password']"),
        WaitAction(milliseconds=300),
        WriteAction(text=password),
        WaitAction(milliseconds=500),
        ClickAction(selector="button[data-testid='LoginForm_Login_Button']"),
        WaitAction(milliseconds=3500),
        ScreenshotAction(),
    ]


def instagram_login_actions(username: str, password: str) -> list[Any]:
    return [
        WaitAction(milliseconds=2000),
        ClickAction(selector="input[name='username']"),
        WaitAction(milliseconds=300),
        WriteAction(text=username),
        ClickAction(selector="input[name='password']"),
        WaitAction(milliseconds=300),
        WriteAction(text=password),
        ClickAction(selector="button[type='submit']"),
        WaitAction(milliseconds=4000),
        ScreenshotAction(),
    ]


def reddit_login_actions(username: str, password: str) -> list[Any]:
    return [
        WaitAction(milliseconds=2000),
        ClickAction(selector="input[id='loginUsername']"),
        WriteAction(text=username),
        ClickAction(selector="input[id='loginPassword']"),
        WriteAction(text=password),
        ClickAction(selector="button[type='submit']"),
        WaitAction(milliseconds=3000),
        ScreenshotAction(),
    ]


_LOGIN_ACTIONS_MAP = {
    "twitter": twitter_login_actions,
    "instagram": instagram_login_actions,
    "reddit": reddit_login_actions,
}


def get_login_actions(platform: str, username: str, password: str) -> list[Any]:
    fn = _LOGIN_ACTIONS_MAP.get(platform)
    if not fn:
        raise ValueError(f"不支持的平台: {platform}")
    return fn(username, password)


def print_cookie_guide(platform: str):
    guides = {
        "twitter": """
[bold cyan]如何获取 Twitter Cookie:[/bold cyan]
  1. 浏览器打开 https://x.com 并登录
  2. 按 F12 打开开发者工具 → Network 标签
  3. 刷新页面，点击任意请求
  4. 找到 Request Headers → Cookie 字段
  5. 复制整行 Cookie 值（很长，包含 auth_token、ct0 等）
  6. 粘贴到 .env 的 TWITTER_COOKIES=<这里>

[dim]关键 Cookie 字段: auth_token, ct0, twid[/dim]
""",
        "instagram": """
[bold cyan]如何获取 Instagram Cookie:[/bold cyan]
  1. 浏览器打开 https://www.instagram.com 并登录
  2. 按 F12 → Network → 刷新 → 点击任意请求
  3. Request Headers → Cookie 字段，复制整行
  4. 粘贴到 .env 的 INSTAGRAM_COOKIES=<这里>

[dim]关键 Cookie 字段: sessionid, csrftoken, ds_user_id[/dim]

[yellow]推荐使用浏览器插件 "Cookie-Editor" 一键导出[/yellow]
""",
        "reddit": """
[bold cyan]如何获取 Reddit Cookie:[/bold cyan]
  1. 浏览器打开 https://www.reddit.com 并登录
  2. F12 → Network → 刷新 → 复制 Cookie 字段
  3. 粘贴到 .env 的 REDDIT_COOKIES=<这里>

[dim]关键 Cookie 字段: reddit_session, token_v2[/dim]
""",
    }
    console.print(guides.get(platform, f"暂无 {platform} 的 Cookie 获取指南"))
