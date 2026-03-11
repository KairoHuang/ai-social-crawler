import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def print_banner():
    banner = Text()
    banner.append("  AI Social Crawler  ", style="bold white on blue")
    console.print(Panel(banner, subtitle="Powered by Firecrawl", border_style="blue"))
    console.print()


def print_profile(data: dict, platform: str):
    """美观地打印用户资料"""
    title = f"[bold cyan]{platform.upper()} 用户资料[/bold cyan]"

    # 基础信息表格
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("字段", style="dim", width=16)
    table.add_column("值")

    skip_keys = {"recent_tweets", "recent_posts", "top_posts", "raw_markdown", "url"}

    for key, value in data.items():
        if key in skip_keys or value is None or value == "":
            continue
        label = key.replace("_", " ").title()
        table.add_row(label, str(value))

    console.print(Panel(table, title=title, border_style="cyan"))

    # 打印最近帖子/推文
    posts_key = next(
        (k for k in ["recent_tweets", "recent_posts"] if k in data and data[k]),
        None,
    )
    if posts_key:
        posts = data[posts_key]
        console.print(f"\n[bold]最近 {len(posts)} 条内容：[/bold]")
        for i, post in enumerate(posts[:5], 1):
            text = post.get("text") or post.get("caption") or post.get("title", "")
            stats = _format_stats(post)
            console.print(f"  [dim]{i}.[/dim] {text[:120]}{'...' if len(text) > 120 else ''}")
            if stats:
                console.print(f"      [dim]{stats}[/dim]")
        console.print()


def print_results(results: list[dict], platform: str, query: str):
    """打印搜索/爬取结果列表"""
    if not results:
        console.print("[yellow]没有找到结果[/yellow]")
        return

    console.print(f"\n[bold green]找到 {len(results)} 条结果  ·  查询: {query}[/bold green]\n")

    for i, item in enumerate(results, 1):
        title = (
            item.get("text")
            or item.get("title")
            or item.get("caption")
            or ""
        )
        author = (
            item.get("author")
            or item.get("author_handle")
            or item.get("username")
            or ""
        )
        stats = _format_stats(item)

        console.print(f"[bold]{i}.[/bold] {title[:140]}{'...' if len(title) > 140 else ''}")
        info_parts = []
        if author:
            info_parts.append(f"@{author.lstrip('@')}")
        if stats:
            info_parts.append(stats)
        if item.get("subreddit"):
            info_parts.append(f"r/{item['subreddit']}")
        if info_parts:
            console.print(f"   [dim]{' · '.join(info_parts)}[/dim]")
        console.print()


def _format_stats(item: dict) -> str:
    parts = []
    for key, label in [
        ("likes", "❤️"),
        ("retweets", "🔁"),
        ("replies", "💬"),
        ("comments", "💬"),
        ("comments_count", "💬"),
        ("score", "⬆️"),
    ]:
        if item.get(key):
            parts.append(f"{label} {item[key]}")
    return "  ".join(parts)


def print_json(data: dict | list):
    """打印格式化的 JSON"""
    console.print_json(json.dumps(data, ensure_ascii=False))
