"""
知识库：LangChain DashScopeEmbeddings（通义）+ Chroma 持久化。
写入与查询均走 LangChain 的 embed_documents / embed_query；检索优先用向量库自带的 as_retriever。
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from chromadb.config import Settings
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from config import DASHSCOPE_API_KEY, logger

# Chroma 数据目录（可用环境变量覆盖）
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_kb_store")
COLLECTION_NAME = "story_kb"
# 与通义单条长度限制对齐的保守截断（略小于 embedding 侧约定）
MAX_DOC_CHARS = 2000

# 此类条目不再参与向量检索（正文请放 Markdown 并由工具读取；历史数据可被过滤）
_EXCLUDED_FROM_RAG_TYPES = frozenset({"已有文章"})

class ChromaKnowledgeBase:
    """通义向量 + Chroma 持久化。"""

    def __init__(self, dashscope_api_key: Optional[str] = None):
        key = dashscope_api_key or DASHSCOPE_API_KEY
        self._lc_embeddings = DashScopeEmbeddings(
            model="text-embedding-v2",
            dashscope_api_key=key,
        )
        self._persist_dir = CHROMA_PERSIST_DIR
        self._collection_name = COLLECTION_NAME
        self._client_settings = Settings(anonymized_telemetry=False)
        self._vs = self._open_vectorstore()

        logger.info(f"Chroma 知识库已就绪，目录={self._persist_dir}，集合={self._collection_name}")

    def _open_vectorstore(self) -> Chroma:
        return Chroma(
            collection_name=self._collection_name,
            embedding_function=self._lc_embeddings,
            persist_directory=self._persist_dir,
            client_settings=self._client_settings,
            collection_metadata={"hnsw:space": "l2"},
        )

    # ---------- 有序列表（仅用于列表展示与按序号删除）----------

    def _rows_sorted(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        data = self._vs.get(include=["metadatas", "documents"])
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        rows: List[Tuple[str, str, Dict[str, Any]]] = []
        for i, cid in enumerate(ids):
            md = dict(metas[i] or {})
            rows.append((cid, docs[i] if i < len(docs) else "", md))
        rows.sort(key=lambda r: int(r[2].get("list_index", 0)))
        return rows

    def _next_list_index(self) -> int:
        rows = self._rows_sorted()
        if not rows:
            return 0
        return int(rows[-1][2].get("list_index", len(rows) - 1)) + 1

    # ---------- 对外 API（供 main 路由使用）----------

    @property
    def documents(self) -> List[str]:
        return [doc for _, doc, _ in self._rows_sorted()]

    @property
    def metadatas(self) -> List[Dict[str, Any]]:
        return [dict(md) for _, _, md in self._rows_sorted()]

    def document_count(self) -> int:
        return len(self._vs)

    def type_counts_snapshot(self) -> Dict[str, int]:
        tc: Dict[str, int] = {}
        for _, _, md in self._rows_sorted():
            t = md.get("type", "未知") if md else "未知"
            tc[str(t)] = tc.get(str(t), 0) + 1
        return tc

    def add_setting(
        self,
        setting_type: str,
        content: str,
        enable_segmentation: bool = True,
    ) -> Tuple[bool, str]:
        # enable_segmentation 保留参数以兼容路由，简化实现：整段一条，不再自动分段
        _ = enable_segmentation
        try:
            text = (content or "").strip()
            if not text:
                return False, "内容为空"
            if (setting_type or "").strip() == "已有文章":
                return False, "「已有文章」不再写入向量库；请放入项目 markdown/（或 STORY_ARTICLE_MD_DIR）并用 query_article_chapter_markdown 读取"
            if len(text) > MAX_DOC_CHARS:
                text = text[:MAX_DOC_CHARS]

            idx = self._next_list_index()
            meta = {"type": setting_type, "list_index": idx}
            self._vs.add_texts(
                [text],
                metadatas=[meta],
                ids=[str(uuid.uuid4())],
            )
            total = len(self._vs)
            return True, f"设定已添加（类型：{setting_type}，片段数：1，总数：{total}）"
        except Exception as e:
            logger.error(f"添加设定失败: {e}", exc_info=True)
            return False, str(e)

    def search_relevant_settings(self, query: str, top_n: int = 3) -> List[str]:
        if len(self._vs) == 0:
            return []
        k = max(1, min(top_n, len(self._vs)))
        cap = max(1, min(k * 4, len(self._vs)))
        docs = self._vs.similarity_search(query, k=cap)
        texts: List[str] = []
        for d in docs:
            md = d.metadata or {}
            if md.get("type") in _EXCLUDED_FROM_RAG_TYPES:
                continue
            texts.append(d.page_content)
            if len(texts) >= k:
                break
        return texts

    def search_relevant_documents(self, query: str, top_n: int = 15) -> List[Document]:
        if len(self._vs) == 0:
            return []
        n = len(self._vs)
        fetch_k = min(n, max(top_n * 5, top_n + 15))
        raw = self._vs.similarity_search(query, k=fetch_k)
        out: List[Document] = []
        for d in raw:
            md = dict(d.metadata or {})
            if md.get("type") in _EXCLUDED_FROM_RAG_TYPES:
                continue
            md.pop("list_index", None)
            out.append(Document(page_content=d.page_content, metadata=md))
            if len(out) >= top_n:
                break
        return out

    def as_langchain_retriever(self, top_k: int = 15):
        """返回 LangChain VectorStoreRetriever，内部用 embed_query + 向量检索。"""
        n = len(self._vs)
        kk = max(1, min(top_k, n)) if n else 1
        return self._vs.as_retriever(search_kwargs={"k": kk})

    def clear_all_settings(self) -> str:
        try:
            self._vs.delete_collection()
            self._vs = self._open_vectorstore()
            legacy = os.environ.get("FAISS_KB_CACHE_LEGACY", "faiss_kb_cache.pkl")
            if os.path.isfile(legacy):
                try:
                    os.remove(legacy)
                except OSError:
                    pass
            return "已清空所有设定"
        except Exception as e:
            logger.error(f"清空设定失败: {e}")
            return f"清空失败：{e}"

    def delete_setting(self, index: int) -> bool:
        rows = self._rows_sorted()
        if not (0 <= index < len(rows)):
            return False
        try:
            self._vs.delete(ids=[rows[index][0]])
            return True
        except Exception as e:
            logger.error(f"删除设定失败: {e}")
            return False

    def get_all_settings(self) -> List[Tuple[str, Dict[str, Any]]]:
        return [(doc, md) for _, doc, md in self._rows_sorted()]



