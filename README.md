# AI Social Crawler

使用 **Firecrawl** 驱动的社交媒体 AI 爬虫，支持 Twitter/X、Instagram、Reddit 等平台。

## 支持的平台

| 平台 | 功能 |
|------|------|
| Twitter / X | 用户资料、关键词搜索、话题标签 |
| Instagram | 用户资料、话题标签 |
| Reddit | 用户资料、全站搜索、版块热帖 |

## 快速开始

### 1. 安装依赖

```bash
cd ai-social-crawler
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入你的 Firecrawl API Key
# 从 https://firecrawl.dev 获取免费 Key
```

### 3. 运行

```bash
# 交互式模式（推荐新手）
python main.py interactive

# 获取用户资料
python main.py profile twitter elonmusk
python main.py profile instagram natgeo
python main.py profile reddit spez

# 搜索内容
python main.py search twitter "AI agents" --limit 20
python main.py search reddit "machine learning" -n 15

# 话题标签
python main.py hashtag twitter AI
python main.py hashtag instagram travel --limit 20

# Reddit 版块
python main.py subreddit MachineLearning --limit 20

# 输出 JSON 格式
python main.py profile twitter elonmusk --json

# 保存结果到文件（存放在 output/ 目录）
python main.py search twitter "ChatGPT" --save
```

## 项目结构

```
ai-social-crawler/
├── main.py              # CLI 入口
├── config.py            # 配置和平台参数
├── requirements.txt
├── .env.example
├── crawlers/
│   ├── base.py          # 基础爬虫类（封装 Firecrawl）
│   ├── twitter.py       # Twitter/X 爬虫
│   ├── instagram.py     # Instagram 爬虫
│   └── reddit.py        # Reddit 爬虫
├── utils/
│   └── display.py       # 终端美化输出
└── output/              # 保存的 JSON 结果
```

## 注意事项

- Instagram、Twitter 对爬虫有反爬措施，Firecrawl 会自动处理大部分情况
- Instagram 私密账号无法获取详细内容
- 建议控制请求频率，避免被封
