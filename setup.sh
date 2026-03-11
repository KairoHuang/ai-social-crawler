#!/usr/bin/env bash
# =============================================================================
#  AI Social Crawler — 一键环境搭建脚本
#  支持 macOS / Linux，Python 3.10+
# =============================================================================

set -e  # 任何命令失败立即退出

# ── 颜色输出 ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }
step()    { echo -e "\n${BOLD}── $* ──${RESET}"; }

echo -e "${BOLD}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      AI Social Crawler — Setup           ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Step 1: 检查 Python 版本 ──────────────────────────────────────────────────
step "Step 1/5  检查 Python 环境"

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON="$cmd"
            success "找到 Python $VER  ($cmd)"
            break
        fi
    fi
done

[ -z "$PYTHON" ] && error "需要 Python 3.10+，请先安装：https://www.python.org/downloads/"

# ── Step 2: 创建虚拟环境 ──────────────────────────────────────────────────────
step "Step 2/5  创建虚拟环境 (.venv)"

if [ -d ".venv" ]; then
    warn ".venv 已存在，跳过创建（删除 .venv 目录可重新创建）"
else
    "$PYTHON" -m venv .venv
    success "虚拟环境已创建"
fi

# 激活虚拟环境
source .venv/bin/activate
success "虚拟环境已激活：$(which python)"

# ── Step 3: 安装 Python 依赖 ──────────────────────────────────────────────────
step "Step 3/5  安装 Python 依赖"

pip install --upgrade pip -q
pip install -r requirements.txt
success "Python 依赖安装完成"

# ── Step 4: 安装 Playwright 浏览器 ───────────────────────────────────────────
step "Step 4/5  安装 Playwright Chromium 浏览器"

if playwright install chromium 2>/dev/null; then
    success "Playwright Chromium 安装完成"
else
    # fallback：用 python -m playwright
    python -m playwright install chromium
    success "Playwright Chromium 安装完成"
fi

# ── Step 5: 初始化配置文件和目录 ──────────────────────────────────────────────
step "Step 5/5  初始化配置文件和目录"

# 创建必要目录
mkdir -p output/sessions
success "目录 output/sessions 已就绪"

# 复制 .env（如果不存在）
if [ ! -f ".env" ]; then
    cp .env.example .env
    warn ".env 文件已从模板创建，请填写你的 API Key 和账号信息："
    warn "  → 用编辑器打开 .env 文件，填入 OPENAI_API_KEY、TWITTER_COOKIES 等"
else
    success ".env 文件已存在，跳过"
fi

# ── 完成 ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✅  环境搭建完成！${RESET}"
echo ""
echo -e "  下一步："
echo -e "  ${CYAN}1.${RESET}  编辑 ${BOLD}.env${RESET} 文件，填入你的 API Key 和账号 Cookie"
echo -e "  ${CYAN}2.${RESET}  激活环境：${BOLD}source .venv/bin/activate${RESET}"
echo -e "  ${CYAN}3.${RESET}  运行示例："
echo -e "       ${BOLD}python main.py profile mogic_app --browser${RESET}"
echo -e "       ${BOLD}python main.py followers mogic_app --browser${RESET}"
echo -e "       ${BOLD}python main.py deep-crawl mogic_app --limit 20 --save${RESET}"
echo ""
echo -e "  查看所有命令：${BOLD}python main.py --help${RESET}"
echo ""
