"""
通义千问重排序模块
使用 DashScope GTE-Rerank 对 RAG 检索结果进行 Rerank
"""
import os
from typing import List, Optional
from config import logger

# 文档内容类型：str 或 LangChain Document
DOC_TYPE = "Document"


def rerank_documents(
    query: str,
    documents: List,
    top_n: int = 5,
    api_key: Optional[str] = None,
) -> List:
    """
    使用通义 gte-rerank 模型对检索结果重排序
    
    :param query: 查询文本
    :param documents: 文档列表，元素为 str 或 LangChain Document
    :param top_n: 返回前 top_n 个
    :param api_key: DashScope API Key，默认从环境变量读取
    :return: 重排序后的文档列表，类型与输入一致
    """
    if not documents:
        return []
    
    api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
    if not api_key:
        logger.warning("未配置 DASHSCOPE_API_KEY，跳过 Rerank")
        return documents[:top_n]
    
    # 提取文本
    contents = []
    for d in documents:
        if hasattr(d, "page_content"):
            contents.append(d.page_content)
        else:
            contents.append(str(d))
    
    if not contents:
        return []
    
    try:
        import dashscope
        from dashscope import TextReRank
        
        dashscope.api_key = api_key
        
        model = TextReRank.Models.gte_rerank
        resp = TextReRank.call(
            model=model,
            query=query,
            documents=contents,
            top_n=min(top_n, len(contents)),
            return_documents=False,
            api_key=api_key,
        )
        
        from http import HTTPStatus
        if resp.status_code != HTTPStatus.OK:
            logger.error(f"Rerank 失败: {resp.message}")
            return documents[:top_n]
        
        # ReRankOutput.results 已按 relevance_score 降序
        output_obj = getattr(resp, "output", None)
        reranked = getattr(output_obj, "results", []) if output_obj else []
        if not reranked:
            return documents[:top_n]
        
        # 按 index 映射回原始文档（results 已排序）
        output = []
        for item in reranked[:top_n]:
            idx = getattr(item, "index", item.get("index", -1))
            if 0 <= idx < len(documents):
                output.append(documents[idx])
        
        return output if output else documents[:top_n]
        
    except ImportError as e:
        logger.warning(f"DashScope Rerank 需要 dashscope: {e}")
        return documents[:top_n]
    except Exception as e:
        logger.error(f"Rerank 异常: {e}", exc_info=True)
        return documents[:top_n]
