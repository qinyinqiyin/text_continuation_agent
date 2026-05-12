"""应用级单例：知识库、StoryWriter（多智能体）Agent 缓存"""
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from config import DASHSCOPE_API_KEY, logger
from knowledge_base import ChromaKnowledgeBase
from langchain_llm import LangChainTongyi

from rag_agent import RAGAgent

_kb: Optional[ChromaKnowledgeBase] = None
_agent_cache: dict = {}
_kb_lock = threading.Lock()


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    try:
        get_kb()
        logger.info("知识库预加载完成")
    except Exception as e:
        logger.warning("知识库预加载: %s", e)
    yield


def get_kb() -> ChromaKnowledgeBase:
    global _kb
    with _kb_lock:
        if _kb is None:
            _kb = ChromaKnowledgeBase()
            logger.info("Chroma 知识库已初始化")
    return _kb


def get_agent() -> RAGAgent:
    cache_key = (DASHSCOPE_API_KEY or "")[:10]
    if cache_key not in _agent_cache:
        if not DASHSCOPE_API_KEY:
            raise ValueError("请配置 DASHSCOPE_API_KEY")
        model = LangChainTongyi(api_key=DASHSCOPE_API_KEY, model_name="qwen-turbo")
        _agent_cache[cache_key] = RAGAgent(model, get_kb())
    return _agent_cache[cache_key]


def clear_agent_cache() -> None:
    _agent_cache.clear()
