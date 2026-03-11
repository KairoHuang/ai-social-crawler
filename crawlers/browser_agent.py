"""
Browser-Use AI 爬虫
用真实 Chromium 浏览器 + LLM Agent 浏览社交媒体，完全绕过 API 限制和反爬机制。

优势：
  - 真实浏览器，平台无法区分人机
  - AI 自动处理登录、弹窗、验证码提示
  - 一套代码搞定 Twitter/Instagram/任意网站
  - 支持 Cookie 注入维持登录态，无需每次重新登录

适用场景：
  - twscrape / instagrapi 被封时的兜底方案
  - 需要截图/可视化验证的场景
  - 爬取结构比较复杂的页面

配置：
  OPENAI_API_KEY 或 ANTHROPIC_API_KEY（用于驱动 Agent）
  BROWSER_HEADLESS=false  可以设为 false 看实时操作过程（调试用）
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel
from rich.console import Console

console = Console()

SESSION_DIR = Path(__file__).parent.parent / "output" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() != "false"


def _get_llm():
    """
    使用 browser-use 自带的 LLM 封装（非 langchain）。
    支持自定义 Base URL，可接中转服务、本地模型（Ollama/LM Studio）等。

    .env 配置示例：
      OPENAI_API_KEY=sk-xxx
      OPENAI_BASE_URL=https://中转地址/v1   # 可选，留空用官方
      BROWSER_LLM_MODEL=gpt-4o-mini        # 可选，默认 gpt-4o-mini

      # 或 Anthropic
      ANTHROPIC_API_KEY=sk-ant-xxx
      ANTHROPIC_BASE_URL=https://中转地址   # 可选
      BROWSER_LLM_MODEL=claude-3-5-haiku-20241022

      # 本地 Ollama
      OPENAI_BASE_URL=http://localhost:11434/v1
      OPENAI_API_KEY=ollama
      BROWSER_LLM_MODEL=qwen2.5:7b
    """
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_base = os.getenv("OPENAI_BASE_URL", "").strip() or None

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None

    model = os.getenv("BROWSER_LLM_MODEL", "")

    if openai_key and not openai_key.startswith("sk-xxx"):
        from browser_use.llm.openai.chat import ChatOpenAI as BUChatOpenAI
        chosen_model = model or "gpt-4o-mini"
        kwargs: dict = {"model": chosen_model, "api_key": openai_key}
        if openai_base:
            kwargs["base_url"] = openai_base
        endpoint = openai_base or "https://api.openai.com/v1"
        console.log(f"[dim]Browser Agent LLM: {chosen_model}  →  {endpoint}[/dim]")
        return BUChatOpenAI(**kwargs)

    if anthropic_key and not anthropic_key.startswith("sk-ant-xxx"):
        from browser_use.llm.anthropic.chat import ChatAnthropic as BUChatAnthropic
        chosen_model = model or "claude-3-5-haiku-20241022"
        kwargs = {"model": chosen_model, "api_key": anthropic_key}
        if anthropic_base:
            kwargs["base_url"] = anthropic_base
        endpoint = anthropic_base or "https://api.anthropic.com"
        console.log(f"[dim]Browser Agent LLM: {chosen_model}  →  {endpoint}[/dim]")
        return BUChatAnthropic(**kwargs)

    raise ValueError(
        "Browser Agent 需要 OPENAI_API_KEY 或 ANTHROPIC_API_KEY，请在 .env 中配置。\n"
        "如果使用中转服务，同时设置 OPENAI_BASE_URL=https://你的地址/v1"
    )


def _cookie_str_to_storage_state(cookie_str: str, domain: str) -> dict:
    """
    将浏览器复制的 Cookie 字符串转换为 Playwright storage_state 格式。
    这样 browser-use 启动时已经是登录状态，不需要重新登录。
    """
    cookies = []
    cookie_str = cookie_str.strip().strip("'\"")
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
                "httpOnly": False,
                "sameSite": "Lax",
            })
    return {"cookies": cookies, "origins": []}


# ─── 结构化输出模型 ────────────────────────────────────────────────────────────

class TweetItem(BaseModel):
    text: str = ""
    author: str = ""
    author_handle: str = ""
    likes: str = "0"
    retweets: str = "0"
    timestamp: str = ""

class TwitterProfileResult(BaseModel):
    """
    只含标量字段，避免 list[nested] 导致 OpenAI strict mode 报 schema 错误。
    推文列表通过 twscrape 单独获取，或用 search 命令。
    """
    username: str = ""
    display_name: str = ""
    bio: str = ""
    email: str = ""
    phone: str = ""
    followers_count: str = ""
    following_count: str = ""
    tweet_count: str = ""
    location: str = ""
    website: str = ""
    joined_date: str = ""
    verified: bool = False

class SearchResult(BaseModel):
    tweet_1: str = ""
    tweet_1_author: str = ""
    tweet_1_likes: str = ""
    tweet_2: str = ""
    tweet_2_author: str = ""
    tweet_2_likes: str = ""
    tweet_3: str = ""
    tweet_3_author: str = ""
    tweet_3_likes: str = ""
    tweet_4: str = ""
    tweet_4_author: str = ""
    tweet_4_likes: str = ""
    tweet_5: str = ""
    tweet_5_author: str = ""
    tweet_5_likes: str = ""

class FollowersResult(BaseModel):
    """粉丝列表用纯文本，每行一条 "username|display_name|bio|email|followers"，解析后再拆"""
    followers_text: str = ""  # 换行分隔，每行格式: username|display_name|bio_excerpt|email|followers_count

class InstagramPost(BaseModel):
    caption: str = ""
    likes: str = "0"
    comments: str = "0"
    author: str = ""
    post_url: str = ""

class InstagramProfileResult(BaseModel):
    """只含标量，避免 OpenAI strict mode $defs 错误"""
    username: str = ""
    full_name: str = ""
    bio: str = ""
    followers_count: str = ""
    following_count: str = ""
    posts_count: str = ""
    is_verified: bool = False
    is_private: bool = False
    recent_posts_text: str = ""  # 换行分隔，每行: caption_excerpt|likes|comments|author


# ─── 核心执行器 ───────────────────────────────────────────────────────────────

class BrowserAgentRunner:
    """封装 browser-use Agent 的同步接口"""

    def __init__(self):
        self.llm = _get_llm()
        self._proxy = os.getenv("PROXY_URL") or None

    async def _run_task(
        self,
        task: str,
        start_url: str,
        output_model: type[BaseModel],
        sensitive_data: dict | None = None,
        storage_state: dict | None = None,
        storage_state_file: Path | None = None,
        allow_login: bool = False,
        max_steps: int = 15,
    ) -> dict:
        from browser_use import Agent
        from browser_use.browser.profile import BrowserProfile
        from browser_use.browser.session import BrowserSession

        # 确定 storage_state 路径（优先已有 session 文件）
        state_path: str | None = None
        tmp_file: Path | None = None

        if storage_state_file and storage_state_file.exists():
            state_path = str(storage_state_file)
            console.log(f"[dim]Browser: 加载 session: {storage_state_file.name}[/dim]")
        elif storage_state:
            tmp_file = SESSION_DIR / f"_tmp_state_{id(storage_state)}.json"
            tmp_file.write_text(json.dumps(storage_state, ensure_ascii=False))
            state_path = str(tmp_file)
            console.log(f"[dim]Browser: 注入 Cookie storage_state[/dim]")

        profile_kwargs: dict[str, Any] = {"headless": HEADLESS}
        if self._proxy:
            profile_kwargs["proxy"] = {"server": self._proxy}
        if state_path:
            profile_kwargs["storage_state"] = state_path
            # 必须显式传 user_data_dir=None，否则 browser-use 会自动创建临时目录
            # 导致 "passed both storage_state AND user_data_dir" 警告
            profile_kwargs["user_data_dir"] = None

        profile = BrowserProfile(**profile_kwargs)
        browser_session = BrowserSession(browser_profile=profile)

        # 有登录态时，系统级别禁止 Agent 自行登录
        no_login_instruction = "" if allow_login else (
            "\n\n重要规则：浏览器已通过 Cookie 完成身份验证，绝对不要尝试输入账号密码或点击登录按钮。"
            "如果看到登录页面，说明 Cookie 已过期，此时直接返回空结果即可，不要执行任何登录操作。"
        )

        agent = Agent(
            task=task,
            llm=self.llm,
            browser_session=browser_session,
            output_model_schema=output_model,
            sensitive_data=sensitive_data or {},
            extend_system_message=no_login_instruction,
            # 用 initial_actions 导航到目标 URL，不依赖 task 文本解析
            initial_actions=[{"navigate": {"url": start_url}}],
            directly_open_url=False,
            max_failures=3,
            max_steps=max_steps,
            use_vision=True,
        )

        try:
            result = await agent.run(max_steps=max_steps)

            # 保存更新后的 session（保持登录态持久化）
            if storage_state_file:
                try:
                    ctx = browser_session.context
                    if ctx:
                        await ctx.storage_state(path=str(storage_state_file))
                        console.log(f"[dim]Browser: session 已更新 → {storage_state_file.name}[/dim]")
                except Exception:
                    pass

            # 清理临时文件
            if tmp_file and tmp_file.exists():
                tmp_file.unlink(missing_ok=True)

            final = result.final_result()
            if final and isinstance(final, BaseModel):
                return final.model_dump()
            if isinstance(final, str):
                try:
                    return json.loads(final)
                except Exception:
                    return {"raw": final}
            return {}
        finally:
            try:
                await browser_session.stop()
            except Exception:
                pass

    def run(self, *args, **kwargs) -> dict:
        return asyncio.run(self._run_task(*args, **kwargs))

    async def _extract_by_js_loop(
        self,
        url: str,
        js_code: str,
        limit: int,
        storage_state: dict | None = None,
        storage_state_file: Path | None = None,
        scroll_pause: float = 2.0,
        max_stale_rounds: int = 3,
    ) -> list[str]:
        """
        直接用 Playwright（绕过 browser-use 包装层）做 JS + 滚动循环提取，不经过 LLM Agent。
        js_code 每次返回换行分隔的文本行，去重后累积直到 limit 或无新内容。
        """
        from playwright.async_api import async_playwright

        # 读取 session 状态
        state_path: str | None = None
        tmp_file: Path | None = None
        if storage_state_file and storage_state_file.exists():
            state_path = str(storage_state_file)
        elif storage_state:
            tmp_file = SESSION_DIR / f"_tmp_js_{id(storage_state)}.json"
            tmp_file.write_text(json.dumps(storage_state, ensure_ascii=False))
            state_path = str(tmp_file)

        async with async_playwright() as p:
            launch_kwargs: dict[str, Any] = {"headless": HEADLESS}
            if self._proxy:
                launch_kwargs["proxy"] = {"server": self._proxy}

            browser = await p.chromium.launch(**launch_kwargs)
            ctx_kwargs: dict[str, Any] = {}
            if state_path:
                ctx_kwargs["storage_state"] = state_path
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()

            try:
                await page.goto(url)
                await asyncio.sleep(3)

                seen: set[str] = set()
                lines: list[str] = []
                stale = 0

                while len(lines) < limit and stale < max_stale_rounds:
                    raw = await page.evaluate(js_code)
                    before = len(lines)
                    if raw:
                        for line in str(raw).strip().splitlines():
                            line = line.strip()
                            key = line.split("|")[0].strip()
                            if line and key and key not in seen:
                                seen.add(key)
                                lines.append(line)
                                if len(lines) >= limit:
                                    break
                    if len(lines) == before:
                        stale += 1
                    else:
                        stale = 0
                    if len(lines) >= limit:
                        break
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 2.5)")
                    await asyncio.sleep(scroll_pause)

                return lines[:limit]
            finally:
                await context.close()
                await browser.close()
                if tmp_file and tmp_file.exists():
                    tmp_file.unlink(missing_ok=True)

    def run_js_loop(self, *args, **kwargs) -> list[str]:
        return asyncio.run(self._extract_by_js_loop(*args, **kwargs))


# ─── 平台爬虫封装 ─────────────────────────────────────────────────────────────

class BrowserTwitterCrawler:
    """browser-use 版 Twitter 爬虫"""

    def __init__(self):
        self.runner = BrowserAgentRunner()
        self._session_file = SESSION_DIR / "browser_twitter.json"
        cookie_str = os.getenv("TWITTER_COOKIES", "")
        self._storage_state = (
            _cookie_str_to_storage_state(cookie_str, ".x.com")
            if cookie_str else None
        )
        self._username = os.getenv("TWITTER_USERNAME", "")
        self._password = os.getenv("TWITTER_PASSWORD", "")

    def _base_task_prefix(self) -> tuple[str, dict, bool]:
        """返回 (任务前缀, sensitive_data, allow_login)"""
        if self._storage_state or self._session_file.exists():
            # 有 Cookie/session，禁止登录
            return "", {}, False
        if self._username and self._password:
            return (
                "先登录 Twitter：用户名是 <twitter_username>，密码是 <twitter_password>。登录成功后再执行后续任务。",
                {"twitter_username": self._username, "twitter_password": self._password},
                True,
            )
        return "", {}, False

    def get_profile(self, username: str) -> dict:
        username = username.lstrip("@")
        prefix, sensitive, allow_login = self._base_task_prefix()
        task = (
            f"{prefix + ' ' if prefix else ''}"
            f"在当前已打开的 Twitter 用户页面中，提取该用户的账户信息（不需要推文）：\n"
            f"- username（@handle）\n"
            f"- display_name（显示名称）\n"
            f"- bio（个人简介全文）\n"
            f"- email（bio 中出现的邮箱，格式 xxx@xxx.com，没有则留空）\n"
            f"- phone（bio 中出现的手机号，没有则留空）\n"
            f"- followers_count（粉丝数）\n"
            f"- following_count（关注数）\n"
            f"- tweet_count（推文数）\n"
            f"- location（位置，没有则留空）\n"
            f"- website（网站链接，没有则留空）\n"
            f"- joined_date（加入日期）\n"
            f"- verified（是否有认证标志）\n"
            f"以上信息全部在用户主页首屏可见，提取完毕后立即返回结果，不要滚动或查找推文。"
        )
        console.log(f"[cyan]Browser Agent 启动 — 获取 @{username} 资料...[/cyan]")
        result = self.runner.run(
            task=task,
            start_url=f"https://x.com/{username}",
            output_model=TwitterProfileResult,
            sensitive_data=sensitive,
            storage_state=self._storage_state,
            storage_state_file=self._session_file,
            allow_login=allow_login,
            max_steps=5,
        )
        return {"source": "browser-use", **result}

    def search(self, query: str, limit: int = 10) -> list[dict]:
        import urllib.parse
        prefix, sensitive, allow_login = self._base_task_prefix()
        encoded = urllib.parse.quote(query)
        url = f"https://x.com/search?q={encoded}&f=live"
        task = (
            f"{prefix + ' ' if prefix else ''}"
            f"在当前已打开的 Twitter 搜索结果页面中，"
            f"提取 {limit} 条推文，每条包含：作者姓名、用户名、推文内容、点赞数、转发数、发布时间。"
        )
        console.log(f"[cyan]Browser Agent 启动 — 搜索: {query}...[/cyan]")
        result = self.runner.run(
            task=task,
            start_url=url,
            output_model=SearchResult,
            sensitive_data=sensitive,
            storage_state=self._storage_state,
            storage_state_file=self._session_file,
            allow_login=allow_login,
            max_steps=10,  # 搜索结果首屏即可，最多滚动 1-2 次
        )
        # 将 flat 字段还原为 list[dict]
        items = []
        for i in range(1, 6):
            text = result.get(f"tweet_{i}", "")
            if text:
                items.append({
                    "text": text,
                    "author": result.get(f"tweet_{i}_author", ""),
                    "likes": result.get(f"tweet_{i}_likes", ""),
                })
        return items[:limit]

    def get_hashtag(self, hashtag: str, limit: int = 10) -> list[dict]:
        return self.search(f"#{hashtag.lstrip('#')}", limit=limit)

    def get_followers(self, username: str, limit: int = 100) -> list[dict]:
        """获取用户粉丝列表（browser-use 翻页爬取）"""
        return self._get_user_relations(username, "followers", limit)

    def get_following(self, username: str, limit: int = 100) -> list[dict]:
        """获取用户正在关注的列表"""
        return self._get_user_relations(username, "following", limit)

    # JavaScript 代码：先定位 aria-label="Timeline: Followers/Following" 容器，
    # 再在其中找 data-testid="cellInnerDiv" 用户块，从 data-testid="UserCell" 提取数据
    _EXTRACT_USERCELL_JS = """
(function() {
  // 优先在 Followers/Following Timeline 容器内查找，避免误抓页面其他区域
  var timeline = document.querySelector('[aria-label="Timeline: Followers"]')
              || document.querySelector('[aria-label="Timeline: Following"]')
              || document.querySelector('[aria-label^="Timeline:"]')
              || document.body;

  var blocks = timeline.querySelectorAll('[data-testid="cellInnerDiv"]');
  var results = [];

  blocks.forEach(function(block) {
    try {
      // 每个 cellInnerDiv 内可能有一个 UserCell button
      var cell = block.querySelector('[data-testid="UserCell"]');
      if (!cell) return;

      // 提取用户名：找 href="/xxx"（单层路径，无斜杠）
      var username = '';
      var links = cell.querySelectorAll('a[href^="/"]');
      for (var i = 0; i < links.length; i++) {
        var h = links[i].getAttribute('href');
        if (h && h.length > 1 && h.indexOf('/', 1) === -1) {
          username = h.slice(1);
          break;
        }
      }
      if (!username) return;

      // 显示名称：[dir="ltr"] 内第一个 span>span
      var nameEl = cell.querySelector('[dir="ltr"] span span');
      var displayName = nameEl ? nameEl.textContent.trim() : '';

      // 提取所有文本节点（bio 区域），排除已提取的 displayName
      var allText = cell.innerText || cell.textContent || '';
      // 简单取 cell 全文后半段作为 bio（去掉前两行用户名/handle）
      var bioEl = cell.querySelector('[dir="auto"]');
      var bio = bioEl ? bioEl.textContent.replace(/\\s+/g, ' ').trim() : '';

      // 从整个 cell 文本中提取邮箱
      var emailMatch = allText.match(/[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}/);
      var email = emailMatch ? emailMatch[0] : '';

      results.push(username + '|' + displayName + '|' + bio.slice(0, 120) + '|' + email);
    } catch(e) {}
  });

  return results.join('\\n');
})()
"""

    def _get_user_relations(self, username: str, relation: str, limit: int) -> list[dict]:
        """
        直接用 Python 控制 BrowserSession 做 JS + 滚动循环，完全绕过 LLM Agent。
        LLM 不擅长跨步骤累积数据，这里纯 Python 循环更可靠，且只需 O(limit/10) 次滚动。
        """
        username = username.lstrip("@")
        url = f"https://x.com/{username}/{relation}"
        label = "粉丝" if relation == "followers" else "正在关注的用户"
        console.log(f"[cyan]JS直接提取 — 获取 @{username} 的{label}列表 (最多 {limit} 条)...[/cyan]")

        raw_lines = self.runner.run_js_loop(
            url=url,
            js_code=self._EXTRACT_USERCELL_JS,
            limit=limit,
            storage_state=self._storage_state,
            storage_state_file=self._session_file,
        )

        items = []
        for line in raw_lines:
            parts = line.split("|")
            item = {
                "username": parts[0].strip() if len(parts) > 0 else "",
                "display_name": parts[1].strip() if len(parts) > 1 else "",
                "bio": parts[2].strip() if len(parts) > 2 else "",
                "email": parts[3].strip() if len(parts) > 3 else "",
            }
            if item["username"]:
                items.append(item)
        return items[:limit]


class BrowserInstagramCrawler:
    """browser-use 版 Instagram 爬虫"""

    def __init__(self):
        self.runner = BrowserAgentRunner()
        self._username = os.getenv("INSTAGRAM_USERNAME", "")
        self._password = os.getenv("INSTAGRAM_PASSWORD", "")
        self._session_file = SESSION_DIR / f"browser_instagram_{self._username}.json"
        cookie_str = os.getenv("INSTAGRAM_COOKIES", "")
        self._storage_state = (
            _cookie_str_to_storage_state(cookie_str, ".instagram.com")
            if cookie_str else None
        )

    def _base_task_prefix(self) -> tuple[str, dict, bool]:
        if self._storage_state or self._session_file.exists():
            return "", {}, False
        if self._username and self._password:
            return (
                "先登录 Instagram：账号是 <ig_username>，密码是 <ig_password>。"
                "如果出现保存登录信息的弹窗，点击「以后再说」。登录成功后再执行后续任务。",
                {"ig_username": self._username, "ig_password": self._password},
                True,
            )
        return "", {}, False

    def get_profile(self, username: str) -> dict:
        username = username.lstrip("@")
        prefix, sensitive, allow_login = self._base_task_prefix()
        task = (
            f"{prefix + ' ' if prefix else ''}"
            f"在当前已打开的 Instagram 用户页面中，"
            f"提取：用户名、全名、简介、粉丝数、关注数、帖子数、是否认证、是否私密，"
            f"以及最近帖子的列表（描述摘要、点赞数、评论数）。"
        )
        console.log(f"[cyan]Browser Agent 启动 — 获取 IG @{username} 资料...[/cyan]")
        result = self.runner.run(
            task=task,
            start_url=f"https://www.instagram.com/{username}/",
            output_model=InstagramProfileResult,
            sensitive_data=sensitive,
            storage_state=self._storage_state,
            storage_state_file=self._session_file,
            allow_login=allow_login,
        )
        return {"source": "browser-use", **result}

    def get_hashtag(self, hashtag: str, limit: int = 10) -> list[dict]:
        hashtag = hashtag.lstrip("#")
        prefix, sensitive, allow_login = self._base_task_prefix()
        url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        task = (
            f"{prefix + ' ' if prefix else ''}"
            f"在当前已打开的 Instagram 话题页面中，"
            f"提取 #{hashtag} 下的 {limit} 条热门帖子，"
            f"每条包含：描述摘要、点赞数、评论数、作者用户名。"
        )
        console.log(f"[cyan]Browser Agent 启动 — IG 话题 #{hashtag}...[/cyan]")

        class HashtagResult(BaseModel):
            """用 flat 文本避免 $defs，每行: caption|likes|comments|author"""
            posts_text: str = ""

        result = self.runner.run(
            task=task,
            start_url=url,
            output_model=HashtagResult,
            sensitive_data=sensitive,
            storage_state=self._storage_state,
            storage_state_file=self._session_file,
            allow_login=allow_login,
        )
        items = []
        for line in result.get("posts_text", "").strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 1 and parts[0].strip():
                items.append({
                    "caption": parts[0].strip(),
                    "likes": parts[1].strip() if len(parts) > 1 else "",
                    "comments": parts[2].strip() if len(parts) > 2 else "",
                    "author": parts[3].strip() if len(parts) > 3 else "",
                })
        return items[:limit]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        return self.get_hashtag(query.lstrip("#").replace(" ", ""), limit=limit)
