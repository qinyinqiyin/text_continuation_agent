"""
FastAPI + LangChain 文本续写助手
最简实现，保留全部功能
"""
import os
import re
import pickle
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import logger, DASHSCOPE_API_KEY
from knowledge_base import FAISSKnowledgeBase
from tools import StoryTools
from function_call import create_function_registry
from langchain_llm import LangChainTongyi
from strategies import (
    FantasyStrategy, AncientStyleStrategy, SciFiStrategy,
    EasternFantasyStyleStrategy, SuspenseStrategy,
)

# ==================== 全局单例 ====================
_kb: Optional[FAISSKnowledgeBase] = None
_story_tools: Optional[StoryTools] = None
_tool_registry = None
_agent_cache: dict = {}
_kb_lock = threading.Lock()

STYLE_MAP = {
    "fantasy": FantasyStrategy,
    "ancient": AncientStyleStrategy,
    "sci-fi": SciFiStrategy,
    "EasternFantasy": EasternFantasyStyleStrategy,
    "Suspense": SuspenseStrategy,
}


def get_kb() -> FAISSKnowledgeBase:
    global _kb
    with _kb_lock:
        if _kb is None:
            _kb = FAISSKnowledgeBase()
            logger.info("✅ 知识库已初始化")
    return _kb


def get_story_tools() -> StoryTools:
    global _story_tools
    if _story_tools is None:
        _story_tools = StoryTools(get_kb())
    return _story_tools


def get_tool_registry():
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = create_function_registry(story_state_manager=get_story_tools())
    return _tool_registry


def get_agent(style: str):
    """获取或创建 Agent"""
    key = (DASHSCOPE_API_KEY or "")[:10]
    cache_key = f"{key}_{style}"
    if cache_key not in _agent_cache:
        if not DASHSCOPE_API_KEY:
            raise ValueError("请配置 DASHSCOPE_API_KEY")
        model = LangChainTongyi(api_key=DASHSCOPE_API_KEY, model_name="qwen-turbo")
        strategy = STYLE_MAP.get(style, FantasyStrategy)()
        agent = RAGAgent(model, strategy, get_kb(), get_story_tools())
        _agent_cache[cache_key] = agent
    return _agent_cache[cache_key]


# ==================== RAG Agent（极简） ====================
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda


class RAGAgent:
    """RAG 续写 Agent：检索 → LLM → 后处理"""

    def __init__(self, model, strategy, kb: FAISSKnowledgeBase, story_tools: StoryTools):
        self.model = model
        self.strategy = strategy
        self.kb = kb
        self.story_tools = story_tools
        self.tool_registry = create_function_registry(story_state_manager=story_tools)

    def run(self, 前文: str, 要求: str = "", max_new_tokens: int = 300, temperature: float = 0.6) -> str:
        """RAG 续写：create_retrieval_chain"""
        llm = self.model.llm.bind(max_tokens=max_new_tokens, temperature=temperature)

        def retrieve(x: dict) -> list:
            query = x.get("input", "")
            docs = self.kb.search_relevant_documents(query, top_n=15)
            fragment = self.story_tools.generate_prompt_fragment(query)
            if fragment:
                docs = [Document(page_content=fragment, metadata={"type": "conflict"})] + docs
            # 通义 Rerank：对检索结果重排序（排除 conflict 片段）
            if docs and (not fragment or len(docs) > 1):
                to_rerank = docs[1:] if fragment else docs
                if to_rerank:
                    from rerank import rerank_documents
                    reranked = rerank_documents(query, to_rerank, top_n=10)
                    docs = ([docs[0]] + reranked) if fragment else reranked
            return docs

        prompt = ChatPromptTemplate.from_messages([
            ("system", "根据知识库续写。\n【知识库】\n{context}\n\n【用户】\n{formatted_prompt}\n\n直接输出续写正文："),
        ])
        chain = create_retrieval_chain(
            RunnableLambda(retrieve),
            create_stuff_documents_chain(llm, prompt, document_variable_name="context"),
        )
        formatted = self.strategy.format_prompt({"前文": 前文, "要求": 要求})
        out = chain.invoke({"input": 前文, "formatted_prompt": formatted})
        return self.strategy.post_process(out.get("answer", "") or "")

    def analyze_text_quality(self, text: str, reference_text: str = "", style: str = None) -> dict:
        results = {}
        r = self.tool_registry.execute_tool("text_analysis", {"action": "quality_score", "text": text})
        if r.get("success"):
            results["quality"] = r["result"]
        if style:
            r = self.tool_registry.execute_tool("text_analysis", {"action": "style_detection", "text": text, "style": style})
            if r.get("success"):
                results["style"] = r["result"]
        if reference_text:
            for act in ["coherence_check", "duplicate_detection"]:
                r = self.tool_registry.execute_tool("text_analysis", {"action": act, "text": text, "reference_text": reference_text})
                if r.get("success"):
                    results[act] = r["result"]
        return results


# ==================== Pydantic Models ====================
class ContinuationRequest(BaseModel):
    style: str = "fantasy"
    context: str
    requirements: str = ""
    max_length: int = 300
    temperature: float = 0.6


class AddSettingRequest(BaseModel):
    type: str
    content: str


# ==================== 生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_kb()
        logger.info("✅ 知识库预加载完成")
    except Exception as e:
        logger.warning(f"知识库预加载: {e}")
    yield


# ==================== FastAPI App ====================
app = FastAPI(title="文本续写助手", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


# ==================== API 路由 ====================
@app.get("/api/config/check")
def config_check():
    return {
        "api_key_configured": bool(DASHSCOPE_API_KEY),
        "api_key_prefix": (DASHSCOPE_API_KEY[:8] + "...") if DASHSCOPE_API_KEY else None,
        "env_file_exists": os.path.exists(os.path.join(os.path.dirname(__file__), ".env")),
    }


@app.post("/api/continuation")
def continuation(req: ContinuationRequest):
    if not req.context.strip():
        raise HTTPException(400, "前文不能为空")
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    agent = get_agent(req.style)
    result = agent.run(
        req.context, req.requirements,
        max_new_tokens=req.max_length, temperature=req.temperature,
    )
    return {"success": True, "result": result}


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
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    ok, msg = get_kb().add_setting(req.type, req.content, enable_segmentation=True)
    if not ok:
        raise HTTPException(400, msg)
    return {"success": True, "message": msg}


@app.delete("/api/knowledge-base/settings/{idx}")
def delete_setting(idx: int):
    if not get_kb().delete_setting(idx):
        raise HTTPException(400, "删除失败")
    _agent_cache.clear()
    return {"success": True, "message": "删除成功"}


@app.post("/api/knowledge-base/clear")
def clear_settings():
    msg = get_kb().clear_all_settings()
    _agent_cache.clear()
    return {"success": True, "message": msg}


def _kb_stats():
    try:
        if os.path.exists("faiss_kb_cache.pkl") and os.path.getsize("faiss_kb_cache.pkl") >= 10:
            with open("faiss_kb_cache.pkl", "rb") as f:
                data = pickle.load(f)
            docs, metas = data.get("documents", []), data.get("metadatas", [])
            tc = {}
            for m in metas:
                t = m.get("type", "未知")
                tc[t] = tc.get(t, 0) + 1
            return {"total_count": len(docs), "type_counts": tc}
    except Exception:
        pass
    return {"total_count": 0, "type_counts": {}}


@app.get("/api/knowledge-base/stats")
def kb_stats():
    return {"success": True, **_kb_stats()}


@app.post("/api/knowledge-base/upload")
async def upload(file: UploadFile = File(...), setting_type: str = Form("已有文章")):
    if not file.filename:
        raise HTTPException(400, "文件名为空")
    valid = ["已有文章", "文章大纲", "角色设定", "世界观设定", "修炼体系", "其他设定"]
    if setting_type not in valid:
        setting_type = "已有文章"
    raw = await file.read()
    try:
        content = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        content = raw.decode("gbk").strip()
    if not content:
        raise HTTPException(400, "文件内容为空")
    if not DASHSCOPE_API_KEY:
        raise HTTPException(400, "请配置 DASHSCOPE_API_KEY")
    ok, msg = get_kb().add_setting(setting_type, content, enable_segmentation=True)
    if not ok:
        raise HTTPException(400, msg)
    seg = int(re.search(r"片段数：(\d+)", msg).group(1)) if re.search(r"片段数：(\d+)", msg) else 1
    return {"success": True, "message": f"已添加。{msg}", "setting_type": setting_type, "segments_count": seg}


@app.post("/api/tools/analyze")
def analyze(req: dict):
    text = req.get("text")
    if not text:
        raise HTTPException(400, "文本不能为空")
    ref, style = req.get("reference_text", ""), req.get("style")
    if DASHSCOPE_API_KEY and style:
        agent = get_agent(style)
        results = agent.analyze_text_quality(text, ref, style)
    else:
        reg = get_tool_registry()
        results = {}
        r = reg.execute_tool("text_analysis", {"action": "quality_score", "text": text})
        if r.get("success"):
            results["quality"] = r["result"]
        if style:
            r = reg.execute_tool("text_analysis", {"action": "style_detection", "text": text, "style": style})
            if r.get("success"):
                results["style"] = r["result"]
        if ref:
            for act in ["coherence_check", "duplicate_detection"]:
                r = reg.execute_tool("text_analysis", {"action": act, "text": text, "reference_text": ref})
                if r.get("success"):
                    results[act] = r["result"]
    return {"success": True, "results": results}


@app.get("/api/tools")
def list_tools():
    return {"success": True, "tools": get_tool_registry().list_tools()}


@app.post("/api/tools/{name}")
def execute_tool(name: str, params: dict = Body(default={})):
    return get_tool_registry().execute_tool(name, params)


@app.post("/api/story-tools")
def story_tools(req: dict):
    name = req.get("tool_name")
    params = req.get("params", {})
    if not name:
        raise HTTPException(400, "缺少 tool_name")
    st = get_story_tools()
    if name == "get_story_state":
        return st.get_story_state()
    if name == "update_story_state":
        return st.update_story_state(params)
    if name == "check_consistency":
        return st.check_consistency(params.get("draft", ""), params.get("settings"))
    if name == "search_lore":
        return st.search_lore(params.get("query", ""), params.get("top_k", 5))
    if name == "search_character":
        return st.search_character(params.get("name", ""))
    raise HTTPException(400, f"未知工具: {name}")


@app.get("/api/health")
@app.get("/health")
def health():
    return {"status": "ok", "message": "服务运行正常"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
