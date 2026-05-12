import logging
import os

# 项目根（本文件所在目录）
_ROOT = os.path.dirname(os.path.abspath(__file__))

# 从环境变量或 .env 加载配置（需 python-dotenv）
try:
    from dotenv import load_dotenv
    env_path = os.path.join(_ROOT, ".env")
    loaded = load_dotenv(env_path)
    if not loaded and not os.environ.get("DASHSCOPE_API_KEY"):
        load_dotenv()  # 回退：从当前工作目录加载
except ImportError:
    pass

# DashScope API Key（StoryWriter 各阶段 LLM + 通义 Embedding 共用），去除首尾空格
DASHSCOPE_API_KEY = (os.environ.get("DASHSCOPE_API_KEY", "") or "").strip()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TextContinuationAgent")

# 章节 / 参考模板 Markdown 根目录：默认均为项目下 markdown/（与 existing articles.md、reference template.md 等同级）
# 可用 STORY_ARTICLE_MD_DIR、STORY_TEMPLATE_MD_DIR 分别覆盖（绝对路径或相对项目根）
_MARKDOWN_DIR_DEFAULT = os.path.join(_ROOT, "markdown")
ARTICLE_MARKDOWN_ROOT = (os.environ.get("STORY_ARTICLE_MD_DIR") or _MARKDOWN_DIR_DEFAULT).strip()
REFERENCE_TEMPLATE_MARKDOWN_ROOT = (
    os.environ.get("STORY_TEMPLATE_MD_DIR") or _MARKDOWN_DIR_DEFAULT
).strip()

# 整部「已有文章」合并 Markdown（按文中「第N章」切分）；可用 EXISTING_ARTICLES_MD_PATH 覆盖为绝对路径
_EXISTING_ARTICLES_MD_DEFAULT = os.path.join(_MARKDOWN_DIR_DEFAULT, "existing articles.md")
EXISTING_ARTICLES_MD_PATH = (
    os.environ.get("EXISTING_ARTICLES_MD_PATH") or _EXISTING_ARTICLES_MD_DEFAULT
).strip()

# 确保默认目录存在，避免首次运行工具报「目录不存在」
for _md_root in (ARTICLE_MARKDOWN_ROOT, REFERENCE_TEMPLATE_MARKDOWN_ROOT):
    try:
        os.makedirs(_md_root, exist_ok=True)
    except OSError:
        pass
