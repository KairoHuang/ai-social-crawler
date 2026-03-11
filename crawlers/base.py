import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from firecrawl import Firecrawl
from firecrawl.v2.types import (
    JsonFormat,
    WaitAction,
    ClickAction,
    WriteAction,
    ScreenshotAction,
    ExecuteJavascriptAction,
)
from rich.console import Console

from config import FIRECRAWL_API_KEY, FIRECRAWL_BASE_URL, OUTPUT_DIR
from utils.auth import PlatformAuth, load_auth, get_login_actions

console = Console()


class BaseCrawler(ABC):
    def __init__(self, platform_name: str):
        if not FIRECRAWL_API_KEY:
            raise ValueError("FIRECRAWL_API_KEY 未设置，请在 .env 文件中配置")
        fc_kwargs: dict = {"api_key": FIRECRAWL_API_KEY}
        if FIRECRAWL_BASE_URL:
            fc_kwargs["api_url"] = FIRECRAWL_BASE_URL
        self.app = Firecrawl(**fc_kwargs)
        self.platform_name = platform_name
        self.auth: PlatformAuth = load_auth(platform_name)
        self._report_auth_status()

    def _report_auth_status(self):
        if self.auth.has_cookies():
            console.log(f"[green]✓ {self.platform_name} — 已加载 Cookie 认证[/green]")
        elif self.auth.has_credentials():
            console.log(f"[yellow]⚠ {self.platform_name} — 已加载账号密码，将使用自动登录[/yellow]")
        else:
            console.log(f"[dim]○ {self.platform_name} — 未配置登录凭证（仅可访问公开内容）[/dim]")

    # ─── 核心抓取方法 ──────────────────────────────────────────────────────────

    def scrape_url(self, url: str, formats: list[str] | None = None) -> dict:
        """抓取单个 URL 返回原始内容（markdown 等）"""
        if formats is None:
            formats = ["markdown"]

        console.log(f"[dim]抓取: {url}[/dim]")
        kwargs: dict[str, Any] = {"formats": formats}
        if self.auth.has_cookies():
            kwargs["headers"] = self.auth.to_headers()

        try:
            doc = self.app.scrape(url, **kwargs)
            return _doc_to_dict(doc)
        except Exception as e:
            console.log(f"[red]抓取失败 {url}: {e}[/red]")
            return {}

    def scrape_with_extract(self, url: str, schema: dict, prompt: str) -> dict:
        """使用 AI JSON 格式提取结构化数据（带 Cookie）"""
        console.log(f"[dim]AI 提取: {url}[/dim]")

        json_format = JsonFormat(type="json", schema=schema, prompt=prompt)
        kwargs: dict[str, Any] = {"formats": [json_format]}
        if self.auth.has_cookies():
            kwargs["headers"] = self.auth.to_headers()

        try:
            doc = self.app.scrape(url, **kwargs)
            return _doc_to_dict(doc)
        except Exception as e:
            console.log(f"[red]AI 提取失败 {url}: {e}[/red]")
            return {}

    def auto_login_and_scrape(self, target_url: str, schema: dict, prompt: str) -> dict:
        """
        完整认证抓取：
          - 有 Cookie → 直接注入 Header
          - 有账密 → Actions 自动登录后跳转到目标页
          - 都没有 → 游客模式
        """
        # 优先 Cookie
        if self.auth.has_cookies():
            return self.scrape_with_extract(target_url, schema, prompt)

        # 账密自动登录
        if self.auth.has_credentials():
            login_url = self._get_login_url()
            if login_url:
                return self._login_then_extract(login_url, target_url, schema, prompt)

        # 游客模式
        console.log("[dim]游客模式（未配置登录凭证）[/dim]")
        return self.scrape_with_extract(target_url, schema, prompt)

    def _login_then_extract(
        self, login_url: str, target_url: str, schema: dict, prompt: str
    ) -> dict:
        """执行登录 Actions，跳转目标页后提取"""
        console.log(f"[cyan]自动登录 ({self.platform_name})...[/cyan]")

        typed_actions = get_login_actions(
            self.platform_name,
            self.auth.username,
            self.auth.password,
        ) + [
            # 登录成功后跳转目标页
            ExecuteJavascriptAction(
                script=f"window.location.href = '{target_url}'"
            ),
            WaitAction(milliseconds=2500),
        ]

        json_format = JsonFormat(type="json", schema=schema, prompt=prompt)
        try:
            doc = self.app.scrape(
                login_url,
                formats=[json_format],
                actions=typed_actions,
            )
            return _doc_to_dict(doc)
        except Exception as e:
            console.log(f"[red]自动登录抓取失败: {e}[/red]")
            return {}

    def crawl_urls(self, url: str, limit: int = 5) -> list[dict]:
        """深度爬取多个页面"""
        console.log(f"[dim]深度爬取 (最多 {limit} 页): {url}[/dim]")
        try:
            result = self.app.crawl(url, limit=limit)
            if hasattr(result, "data"):
                return [_doc_to_dict(d) for d in result.data]
            return []
        except Exception as e:
            console.log(f"[red]深度爬取失败 {url}: {e}[/red]")
            return []

    def save_result(self, data: dict | list, filename: str | None = None) -> str:
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.platform_name}_{ts}.json"

        filepath = f"{OUTPUT_DIR}/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    def _get_login_url(self) -> Optional[str]:
        return {
            "twitter": "https://x.com/i/flow/login",
            "instagram": "https://www.instagram.com/accounts/login/",
            "reddit": "https://www.reddit.com/login/",
        }.get(self.platform_name)

    @abstractmethod
    def get_profile(self, username: str) -> dict:
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[dict]:
        pass


def _doc_to_dict(doc) -> dict:
    """将 Firecrawl v4 Document 对象转换为字典"""
    if doc is None:
        return {}
    if isinstance(doc, dict):
        return doc
    result: dict[str, Any] = {}
    if getattr(doc, "markdown", None):
        result["markdown"] = doc.markdown
    if getattr(doc, "html", None):
        result["html"] = doc.html
    # v4 的 AI 提取结果存在 doc.json
    if getattr(doc, "json", None) is not None:
        result["extract"] = doc.json
    if getattr(doc, "metadata", None):
        meta = doc.metadata
        result["metadata"] = meta.model_dump(exclude_none=True) if hasattr(meta, "model_dump") else meta
    return result
