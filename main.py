#!/usr/bin/env python3
"""
AI Social Crawler - Terminal Edition
使用 Firecrawl 爬取社交媒体内容
"""

import sys
import click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.status import Status

from config import FIRECRAWL_API_KEY, PLATFORM_CONFIGS
from utils.display import print_banner, print_profile, print_results, print_json
from utils.auth import load_auth, print_cookie_guide

console = Console()


def get_crawler(platform: str, use_browser: bool = False):
    """根据平台名称返回对应爬虫实例"""
    if use_browser:
        from crawlers.browser_agent import BrowserTwitterCrawler, BrowserInstagramCrawler
        browser_crawlers = {
            "twitter": BrowserTwitterCrawler,
            "instagram": BrowserInstagramCrawler,
        }
        if platform not in browser_crawlers:
            console.print(f"[yellow]Browser 模式暂不支持 {platform}，切换回普通模式[/yellow]")
        else:
            console.print(f"[cyan]使用 Browser-Use AI 模式 ({platform})[/cyan]")
            return browser_crawlers[platform]()

    from crawlers.twitter import TwitterCrawler
    from crawlers.instagram import InstagramCrawler
    from crawlers.reddit import RedditCrawler

    crawlers = {
        "twitter": TwitterCrawler,
        "instagram": InstagramCrawler,
        "reddit": RedditCrawler,
    }

    if platform not in crawlers:
        console.print(f"[red]不支持的平台: {platform}[/red]")
        console.print(f"支持的平台: {', '.join(crawlers.keys())}")
        sys.exit(1)

    return crawlers[platform]()


# ─── CLI 命令组 ────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("1.0.0")
def cli():
    """AI Social Crawler — 使用 Firecrawl 爬取社交媒体"""
    pass


@cli.command("profile")
@click.argument("platform", type=click.Choice(["twitter", "instagram", "reddit"]))
@click.argument("username")
@click.option("--json", "output_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--save", is_flag=True, help="保存结果到文件")
@click.option("--browser", is_flag=True, help="使用 Browser-Use AI 模式（真实浏览器，绕过风控）")
def cmd_profile(platform: str, username: str, output_json: bool, save: bool, browser: bool):
    """获取用户资料

    示例:
      main.py profile twitter elonmusk
      main.py profile instagram natgeo
      main.py profile reddit spez
    """
    if not FIRECRAWL_API_KEY:
        console.print("[red]错误: FIRECRAWL_API_KEY 未配置，请复制 .env.example 为 .env 并填写[/red]")
        sys.exit(1)

    crawler = get_crawler(platform, use_browser=browser)

    with Status(f"[cyan]正在获取 {platform} 用户 @{username} 的资料...[/cyan]", spinner="dots"):
        data = crawler.get_profile(username)

    if output_json:
        print_json(data)
    else:
        print_profile(data, platform)

    if save:
        filepath = crawler.save_result(data)
        console.print(f"[green]已保存到: {filepath}[/green]")


@cli.command("search")
@click.argument("platform", type=click.Choice(["twitter", "instagram", "reddit"]))
@click.argument("query")
@click.option("--limit", "-n", default=10, show_default=True, help="最大结果数量")
@click.option("--json", "output_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--save", is_flag=True, help="保存结果到文件")
@click.option("--browser", is_flag=True, help="使用 Browser-Use AI 模式")
def cmd_search(platform: str, query: str, limit: int, output_json: bool, save: bool, browser: bool):
    """搜索内容

    示例:
      main.py search twitter "AI agents" --limit 20
      main.py search reddit "machine learning" -n 15
      main.py search instagram python
    """
    if not FIRECRAWL_API_KEY:
        console.print("[red]错误: FIRECRAWL_API_KEY 未配置[/red]")
        sys.exit(1)

    crawler = get_crawler(platform, use_browser=browser)

    with Status(f"[cyan]正在搜索 {platform}: {query}...[/cyan]", spinner="dots"):
        results = crawler.search(query, limit=limit)

    if output_json:
        print_json(results)
    else:
        print_results(results, platform, query)

    if save:
        filepath = crawler.save_result(results)
        console.print(f"[green]已保存到: {filepath}[/green]")


@cli.command("hashtag")
@click.argument("platform", type=click.Choice(["twitter", "instagram"]))
@click.argument("tag")
@click.option("--limit", "-n", default=10, show_default=True, help="最大结果数量")
@click.option("--json", "output_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--save", is_flag=True, help="保存结果到文件")
def cmd_hashtag(platform: str, tag: str, limit: int, output_json: bool, save: bool):
    """获取话题标签内容

    示例:
      main.py hashtag twitter AI
      main.py hashtag instagram travel --limit 20
    """
    if not FIRECRAWL_API_KEY:
        console.print("[red]错误: FIRECRAWL_API_KEY 未配置[/red]")
        sys.exit(1)

    crawler = get_crawler(platform)
    tag = tag.lstrip("#")

    with Status(f"[cyan]正在获取 #{tag} 话题内容...[/cyan]", spinner="dots"):
        results = crawler.get_hashtag(tag, limit=limit)

    if output_json:
        print_json(results)
    else:
        print_results(results, platform, f"#{tag}")

    if save:
        filepath = crawler.save_result(results)
        console.print(f"[green]已保存到: {filepath}[/green]")


@cli.command("subreddit")
@click.argument("name")
@click.option("--limit", "-n", default=10, show_default=True, help="最大结果数量")
@click.option("--json", "output_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--save", is_flag=True, help="保存结果到文件")
def cmd_subreddit(name: str, limit: int, output_json: bool, save: bool):
    """获取 Reddit 版块热帖

    示例:
      main.py subreddit MachineLearning
      main.py subreddit python --limit 20
    """
    if not FIRECRAWL_API_KEY:
        console.print("[red]错误: FIRECRAWL_API_KEY 未配置[/red]")
        sys.exit(1)

    from crawlers.reddit import RedditCrawler
    crawler = RedditCrawler()
    name = name.lstrip("r/")

    with Status(f"[cyan]正在获取 r/{name} 版块内容...[/cyan]", spinner="dots"):
        data = crawler.get_subreddit(name, limit=limit)

    if output_json:
        print_json(data)
    else:
        posts = data.pop("posts", [])
        print_profile(data, "reddit")
        if posts:
            print_results(posts, "reddit", f"r/{name}")

    if save:
        from crawlers.reddit import RedditCrawler as RC
        filepath = RC().save_result(data)
        console.print(f"[green]已保存到: {filepath}[/green]")


@cli.command("followers")
@click.argument("username")
@click.option("--limit", "-n", default=100, show_default=True, help="最多获取数量")
@click.option("--following", "get_following", is_flag=True, help="改为获取「正在关注」列表")
@click.option("--json", "output_json", is_flag=True, help="以 JSON 格式输出")
@click.option("--save", is_flag=True, help="保存结果到文件")
@click.option("--browser", is_flag=True, help="使用 Browser-Use AI 模式")
def cmd_followers(username: str, limit: int, get_following: bool, output_json: bool, save: bool, browser: bool):
    """获取 Twitter 用户的粉丝 / 关注列表

    示例:
      main.py followers mogic_app
      main.py followers mogic_app --following
      main.py followers mogic_app --limit 500 --save
      main.py followers mogic_app --browser
    """
    if not FIRECRAWL_API_KEY and not browser:
        pass  # twscrape 不需要 Firecrawl key

    crawler = get_crawler("twitter", use_browser=browser)
    relation = "following" if get_following else "followers"
    label = "关注列表" if get_following else "粉丝列表"

    with Status(f"[cyan]正在获取 @{username} 的{label} (最多 {limit} 条)...[/cyan]", spinner="dots"):
        if get_following:
            results = crawler.get_following(username, limit=limit)
        else:
            results = crawler.get_followers(username, limit=limit)

    if output_json:
        print_json(results)
    else:
        console.print(f"\n[bold green]@{username} 的{label}：共 {len(results)} 条[/bold green]\n")
        for i, u in enumerate(results, 1):
            name = u.get("display_name") or u.get("username", "")
            handle = u.get("username", "")
            bio = (u.get("bio") or "")[:80]
            email = u.get("email", "")
            fans = u.get("followers_count", "0")
            console.print(f"  [bold]{i}.[/bold] {name} [dim]@{handle}[/dim]  ·  粉丝 {fans}")
            if email:
                console.print(f"      [cyan]📧 {email}[/cyan]")
            if bio:
                console.print(f"      [dim]{bio}[/dim]")
        console.print()

    if save:
        from crawlers.twitter import TwitterCrawler
        tc = TwitterCrawler()
        filepath = tc.save_result(results, f"twitter_{relation}_{username}.json")
        console.print(f"[green]已保存到: {filepath}[/green]")


@cli.command("deep-crawl")
@click.argument("username")
@click.option("--limit", "-n", default=50, show_default=True, help="最多获取粉丝数量")
@click.option("--concurrency", "-c", default=3, show_default=True, help="并发获取粉丝资料的数量")
@click.option("--save", is_flag=True, help="保存结果到文件")
@click.option("--browser", is_flag=True, default=True, show_default=True, help="使用 Browser-Use AI 模式（默认开启）")
def cmd_deep_crawl(username: str, limit: int, concurrency: int, save: bool, browser: bool):
    """深度爬取：获取用户资料 + 粉丝列表 + 每个粉丝的资料（不递归）

    示例:
      main.py deep-crawl mogic_app
      main.py deep-crawl mogic_app --limit 20 --save
    """
    import json
    import time
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    crawler = get_crawler("twitter", use_browser=browser)

    # ── Step 1: 获取目标用户资料 ──────────────────────────────
    console.print(f"\n[bold cyan]Step 1/3  获取 @{username} 的资料...[/bold cyan]")
    with Status("", spinner="dots"):
        root_profile = crawler.get_profile(username)
    console.print(f"  [green]✓[/green]  {root_profile.get('display_name', username)}  "
                  f"[dim]@{root_profile.get('username', username)}[/dim]  "
                  f"粉丝 {root_profile.get('followers_count', '?')}  "
                  f"关注 {root_profile.get('following_count', '?')}")
    if root_profile.get("email"):
        console.print(f"  [cyan]📧 {root_profile['email']}[/cyan]")

    # ── Step 2: 获取粉丝列表 ──────────────────────────────────
    console.print(f"\n[bold cyan]Step 2/3  获取 @{username} 的粉丝列表（最多 {limit} 条）...[/bold cyan]")
    with Status("", spinner="dots"):
        followers = crawler.get_followers(username, limit=limit)
    console.print(f"  [green]✓[/green]  获取到 {len(followers)} 位粉丝")

    # ── Step 3: 依次获取每个粉丝的资料 ───────────────────────
    console.print(f"\n[bold cyan]Step 3/3  获取 {len(followers)} 位粉丝的详细资料...[/bold cyan]\n")

    follower_profiles: list[dict] = []
    failed: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("获取粉丝资料", total=len(followers))
        for follower in followers:
            handle = follower.get("username", "")
            if not handle:
                progress.advance(task)
                continue
            try:
                profile = crawler.get_profile(handle)
                # 把 followers 列表中已有的 bio/email 合并进去（作为补充）
                for k in ("bio", "email"):
                    if not profile.get(k) and follower.get(k):
                        profile[k] = follower[k]
                follower_profiles.append(profile)
                progress.update(task, description=f"[dim]@{handle}[/dim]", advance=1)
            except Exception as e:
                failed.append(handle)
                progress.update(task, description=f"[red]@{handle} 失败[/red]", advance=1)
            time.sleep(1)  # 避免请求过快

    # ── 汇总展示 ──────────────────────────────────────────────
    console.print(f"\n[bold green]完成！共获取 {len(follower_profiles)} 位粉丝资料"
                  f"{f'，{len(failed)} 位失败' if failed else ''}[/bold green]\n")

    table = Table(title=f"@{username} 的粉丝详情", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("用户名", style="cyan", no_wrap=True)
    table.add_column("显示名称", no_wrap=True)
    table.add_column("邮箱", style="green")
    table.add_column("粉丝数", justify="right")
    table.add_column("Bio", max_width=40)

    for i, p in enumerate(follower_profiles, 1):
        table.add_row(
            str(i),
            f"@{p.get('username', '')}",
            p.get("display_name", ""),
            p.get("email", ""),
            str(p.get("followers_count", "")),
            (p.get("bio") or p.get("description") or "")[:60],
        )
    console.print(table)

    if save:
        result_data = {
            "root": root_profile,
            "followers": follower_profiles,
            "failed": failed,
        }
        from crawlers.twitter import TwitterCrawler
        tc = TwitterCrawler()
        filepath = tc.save_result(result_data, f"twitter_deep_{username}.json")
        console.print(f"\n[green]已保存到: {filepath}[/green]")


@cli.command("auth-status")
def cmd_auth_status():
    """检查各平台登录凭证状态"""
    platforms = ["twitter", "instagram", "reddit"]
    console.print("\n[bold]认证状态检查[/bold]\n")

    for platform in platforms:
        auth = load_auth(platform)
        name = PLATFORM_CONFIGS.get(platform, {}).get("name", platform)

        if auth.has_cookies():
            console.print(f"  [green]✓[/green]  {name:15} Cookie 已配置")
        elif auth.has_credentials():
            console.print(f"  [yellow]~[/yellow]  {name:15} 账号密码已配置（自动登录）")
        else:
            console.print(f"  [red]✗[/red]  {name:15} 未配置登录凭证")

    console.print()
    console.print("[dim]提示: 在 .env 文件中配置 TWITTER_COOKIES / INSTAGRAM_COOKIES 等字段[/dim]")
    console.print("[dim]运行 'python main.py cookie-guide twitter' 查看如何获取 Cookie[/dim]\n")


@cli.command("cookie-guide")
@click.argument("platform", type=click.Choice(["twitter", "instagram", "reddit"]))
def cmd_cookie_guide(platform: str):
    """查看如何获取各平台的 Cookie

    示例:
      main.py cookie-guide twitter
      main.py cookie-guide instagram
    """
    print_cookie_guide(platform)


@cli.command("interactive")
def cmd_interactive():
    """交互式模式 — 逐步引导操作"""
    print_banner()

    if not FIRECRAWL_API_KEY:
        console.print("[red]错误: 请先配置 FIRECRAWL_API_KEY[/red]")
        console.print("[dim]复制 .env.example 为 .env 然后填入你的 API Key[/dim]")
        sys.exit(1)

    platforms = list(PLATFORM_CONFIGS.keys())
    console.print("[bold]支持的平台:[/bold]")
    for i, p in enumerate(platforms, 1):
        console.print(f"  {i}. {PLATFORM_CONFIGS[p]['name']}")

    platform = Prompt.ask(
        "\n选择平台",
        choices=platforms,
        default="twitter",
    )

    actions = PLATFORM_CONFIGS[platform]["actions"]
    console.print(f"\n[bold]可用操作:[/bold] {', '.join(actions)}")
    action = Prompt.ask("选择操作", choices=actions, default=actions[0])

    crawler = get_crawler(platform)

    if action == "profile":
        username = Prompt.ask("输入用户名 (不带 @)")
        with Status("[cyan]获取中...[/cyan]", spinner="dots"):
            data = crawler.get_profile(username)
        print_profile(data, platform)

    elif action == "search":
        query = Prompt.ask("输入搜索关键词")
        limit = int(Prompt.ask("最多返回几条", default="10"))
        with Status("[cyan]搜索中...[/cyan]", spinner="dots"):
            results = crawler.search(query, limit=limit)
        print_results(results, platform, query)

    elif action == "hashtag":
        tag = Prompt.ask("输入话题标签 (不带 #)")
        limit = int(Prompt.ask("最多返回几条", default="10"))
        with Status("[cyan]获取中...[/cyan]", spinner="dots"):
            results = crawler.get_hashtag(tag, limit=limit)
        print_results(results, platform, f"#{tag}")

    elif action == "subreddit":
        sub = Prompt.ask("输入版块名称 (不带 r/)")
        limit = int(Prompt.ask("最多返回几条", default="10"))
        from crawlers.reddit import RedditCrawler
        rc = RedditCrawler()
        with Status("[cyan]获取中...[/cyan]", spinner="dots"):
            data = rc.get_subreddit(sub, limit=limit)
        posts = data.pop("posts", [])
        print_profile(data, "reddit")
        if posts:
            print_results(posts, "reddit", f"r/{sub}")

    if Confirm.ask("\n保存结果到文件?", default=False):
        filepath = crawler.save_result(data if action == "profile" else results)
        console.print(f"[green]已保存到: {filepath}[/green]")


if __name__ == "__main__":
    print_banner()
    cli()
