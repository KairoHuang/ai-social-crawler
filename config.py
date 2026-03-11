import os
from dotenv import load_dotenv

load_dotenv()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "").strip() or None  # 自托管 Firecrawl 用

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None

PLATFORM_CONFIGS = {
    "twitter": {
        "name": "Twitter / X",
        "base_url": "https://twitter.com",
        "alt_url": "https://x.com",
        "profile_template": "https://x.com/{username}",
        "search_template": "https://x.com/search?q={query}&src=typed_query",
        "actions": ["profile", "search", "hashtag"],
        "selectors": {
            "post": "[data-testid='tweet']",
            "username": "[data-testid='User-Name']",
            "content": "[data-testid='tweetText']",
        },
    },
    "instagram": {
        "name": "Instagram",
        "base_url": "https://www.instagram.com",
        "profile_template": "https://www.instagram.com/{username}/",
        "hashtag_template": "https://www.instagram.com/explore/tags/{hashtag}/",
        "actions": ["profile", "hashtag"],
        "selectors": {
            "post": "article",
            "username": "header a",
        },
    },
    "linkedin": {
        "name": "LinkedIn",
        "base_url": "https://www.linkedin.com",
        "profile_template": "https://www.linkedin.com/in/{username}/",
        "search_template": "https://www.linkedin.com/search/results/content/?keywords={query}",
        "actions": ["profile", "search"],
        "selectors": {},
    },
    "reddit": {
        "name": "Reddit",
        "base_url": "https://www.reddit.com",
        "profile_template": "https://www.reddit.com/u/{username}/",
        "subreddit_template": "https://www.reddit.com/r/{subreddit}/",
        "search_template": "https://www.reddit.com/search/?q={query}",
        "actions": ["profile", "subreddit", "search"],
        "selectors": {},
    },
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEFAULT_CRAWL_TIMEOUT = 30
DEFAULT_MAX_PAGES = 5
