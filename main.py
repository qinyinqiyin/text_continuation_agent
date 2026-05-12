"""
FastAPI 入口：StoryWriter 多智能体长篇小说接写（Outline→Planning→Writing + RAG）。
业务逻辑见 deps.py、rag_agent.py、storywriter_agents.py。
"""
import os
import re

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    ARTICLE_MARKDOWN_ROOT,
    DASHSCOPE_API_KEY,
    EXISTING_ARTICLES_MD_PATH,
    REFERENCE_TEMPLATE_MARKDOWN_ROOT,
)
from deps import app_lifespan, clear_agent_cache, get_agent, get_kb
from existing_articles_io import append_continuation_as_next_chapter, get_existing_articles_meta


class ContinuationRequest(BaseModel):
    """接写请求：context 为故事前文末尾，requirements 为本轮情节意图或约束"""

    context: str
    requirements: str = ""
    max_length: int = 300
    temperature: float = 0.6


class AddSettingRequest(BaseModel):
    """添加知识库条目的请求体"""

    type: str
    content: str


class AppendChapterBody(BaseModel):
    """写入合并稿的正文片段（服务端自动加「第n章」行）"""

    content: str


# 上传知识库条目时允许的「设定类型」（正文走本地 Markdown + 工具，不写入向量库）
_SETTING_TYPES = frozenset(
    {"文章大纲", "角色设定", "世界观设定", "修炼体系", "其他设定"}
)

app = FastAPI(title="StoryWriter 长篇助手", lifespan=app_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")


@app.get("/health", include_in_schema=False)
@app.get("/api/health")
def health():
    return {"status": "ok", "message": "服务运行正常"}


@app.post("/api/continuation")
def continuation(req: ContinuationRequest):
    if not req.context.strip():
        raise HTTPException(400, "前文不能为空，请粘贴故事正文（接写起点）")
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    agent = get_agent()
    out = agent.run(
        req.context,
        req.requirements,
        max_new_tokens=req.max_length,
        temperature=req.temperature,
    )
    return {
        "success": True,
        "result": out["result"],
        "outline": out.get("outline") or "",
        "planning": out.get("planning") or "",
    }


@app.get("/api/markdown/existing-articles")
def get_existing_articles():
    """供前端自动填充「前文」：读取 EXISTING_ARTICLES_MD_PATH 全文。"""
    meta = get_existing_articles_meta()
    return {"success": True, **meta}


@app.post("/api/markdown/existing-articles/append-chapter")
def append_chapter_to_existing_articles(body: AppendChapterBody):
    """将本轮续写以「第n章」形式追加写入合并稿。"""
    try:
        chapter_n, msg = append_continuation_as_next_chapter(body.content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except OSError as e:
        raise HTTPException(500, f"写入 Markdown 失败：{e}") from e
    return {"success": True, "chapter": chapter_n, "message": msg}


@app.get("/api/knowledge-base/settings")
def get_settings():
    kb = get_kb()
    return {
        "success": True,
        "settings": [
            {"id": i, "type": m.get("type", "未知"), "content": d}
            for i, (d, m) in enumerate(kb.get_all_settings())
        ],
    }


@app.post("/api/knowledge-base/settings")
def add_setting(req: AddSettingRequest):
    if not req.type or not req.content:
        raise HTTPException(400, "类型和内容不能为空")
    if req.type.strip() == "已有文章":
        raise HTTPException(
            400,
            "已有文章不再写入向量库；请将正文放在项目 markdown/ 目录（或环境变量 STORY_ARTICLE_MD_DIR），用工具 query_article_chapter_markdown 按文件名主干读取。",
        )
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    ok, msg = get_kb().add_setting(req.type, req.content)
    if not ok:
        raise HTTPException(400, msg)
    return {"success": True, "message": msg}


@app.delete("/api/knowledge-base/settings/{idx}")
def delete_setting(idx: int):
    if not get_kb().delete_setting(idx):
        raise HTTPException(400, "删除失败")
    clear_agent_cache()
    return {"success": True, "message": "删除成功"}


@app.post("/api/knowledge-base/clear")
def clear_settings():
    msg = get_kb().clear_all_settings()
    clear_agent_cache()
    return {"success": True, "message": msg}


@app.get("/api/knowledge-base/stats")
def kb_stats():
    try:
        kb = get_kb()
        extra = {"total_count": kb.document_count(), "type_counts": kb.type_counts_snapshot()}
    except Exception:
        extra = {"total_count": 0, "type_counts": {}}
    return {"success": True, **extra}


@app.post("/api/knowledge-base/upload")
async def upload(file: UploadFile = File(...), setting_type: str = Form("其他设定")):
    if not file.filename:
        raise HTTPException(400, "文件名为空")
    if setting_type not in _SETTING_TYPES:
        setting_type = "其他设定"
    raw = await file.read()
    try:
        content = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        content = raw.decode("gbk").strip()
    if not content:
        raise HTTPException(400, "文件内容为空")
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    ok, msg = get_kb().add_setting(setting_type, content)
    if not ok:
        raise HTTPException(400, msg)
    m = re.search(r"片段数：(\d+)", msg)
    seg = int(m.group(1)) if m else 1
    return {"success": True, "message": f"已添加。{msg}", "setting_type": setting_type, "segments_count": seg}


@app.get("/api/config/check")
def config_check():
    return {
        "api_key_configured": bool(DASHSCOPE_API_KEY),
        "api_key_prefix": (DASHSCOPE_API_KEY[:8] + "...") if DASHSCOPE_API_KEY else None,
        "env_file_exists": os.path.exists(os.path.join(os.path.dirname(__file__), ".env")),
        "story_article_md_dir": ARTICLE_MARKDOWN_ROOT,
        "story_template_md_dir": REFERENCE_TEMPLATE_MARKDOWN_ROOT,
        "existing_articles_merged_md": EXISTING_ARTICLES_MD_PATH,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
