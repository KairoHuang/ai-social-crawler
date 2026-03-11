from rich.console import Console

from .base import BaseCrawler

console = Console()

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "username": {"type": "string"},
        "karma": {"type": "string"},
        "cake_day": {"type": "string"},
        "bio": {"type": "string"},
        "recent_posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "score": {"type": "string"},
                    "comments": {"type": "string"},
                    "timestamp": {"type": "string"},
                },
            },
        },
    },
}

SUBREDDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "members_count": {"type": "string"},
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "score": {"type": "string"},
                    "comments_count": {"type": "string"},
                    "url": {"type": "string"},
                    "flair": {"type": "string"},
                },
            },
        },
    },
}

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "subreddit": {"type": "string"},
                    "score": {"type": "string"},
                    "comments_count": {"type": "string"},
                    "url": {"type": "string"},
                    "snippet": {"type": "string"},
                },
            },
        }
    },
}


class RedditCrawler(BaseCrawler):
    def __init__(self):
        super().__init__("reddit")

    def get_profile(self, username: str) -> dict:
        """获取 Reddit 用户资料（公开内容无需登录）"""
        username = username.lstrip("u/")
        url = f"https://www.reddit.com/u/{username}/"

        result = self.auto_login_and_scrape(
            url,
            schema=PROFILE_SCHEMA,
            prompt=(
                f"提取 Reddit 用户 u/{username} 的资料，"
                "包括 karma 值、注册时间、个人简介，以及最近的帖子列表。"
            ),
        )

        extract = result.get("extract", {})
        if not extract:
            raw = self.scrape_url(url, formats=["markdown"])
            return {"username": username, "raw_markdown": raw.get("markdown", ""), "url": url}

        return {"username": username, "url": url, **extract}

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """全站搜索"""
        import urllib.parse

        encoded = urllib.parse.quote(query)
        url = f"https://www.reddit.com/search/?q={encoded}&sort=relevance"

        result = self.auto_login_and_scrape(
            url,
            schema=SEARCH_SCHEMA,
            prompt=(
                f"提取 Reddit 搜索 '{query}' 的结果列表，"
                f"包含每个帖子的标题、作者、所在版块、得分、评论数和链接。"
                f"尽量提取 {limit} 条。"
            ),
        )

        results = result.get("extract", {}).get("results", [])
        return results[:limit]

    def get_subreddit(self, subreddit: str, limit: int = 10) -> dict:
        """获取版块热帖"""
        subreddit = subreddit.lstrip("r/")
        url = f"https://www.reddit.com/r/{subreddit}/"

        result = self.auto_login_and_scrape(
            url,
            schema=SUBREDDIT_SCHEMA,
            prompt=(
                f"提取 Reddit r/{subreddit} 版块的信息，"
                f"包括版块描述、成员数量，以及当前热门帖子列表（含标题、作者、得分、评论数）。"
                f"尽量提取 {limit} 条帖子。"
            ),
        )

        extract = result.get("extract", {})
        if "posts" in extract:
            extract["posts"] = extract["posts"][:limit]
        return {"subreddit": subreddit, "url": url, **extract}
