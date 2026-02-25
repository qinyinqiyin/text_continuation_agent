import os
import pickle
import numpy as np
import re
from config import logger

# 尝试导入faiss，如果失败则使用numpy替代
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS不可用，将使用numpy进行向量检索")


class FAISSKnowledgeBase:
    def __init__(self, dashscope_api_key: str = None):
        """
        初始化知识库（通义 embedding）
        :param dashscope_api_key: 通义 API 密钥（可选，优先用 config.DASHSCOPE_API_KEY）
        """
        try:
            from embedding import get_embedding_model
            from config import DASHSCOPE_API_KEY
            kw = {"api_key": dashscope_api_key or DASHSCOPE_API_KEY}
            self.embedding_model = get_embedding_model(backend="dashscope", **kw)
            self.target_dim = self.embedding_model.dimension
            self._use_bert_split = getattr(self.embedding_model, "tokenizer", None) is not None
            logger.info(f"✅ 嵌入模型: dashscope，维度={self.target_dim}")
        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {str(e)}")
            raise
        
        # 初始化索引
        if FAISS_AVAILABLE:
            self.index = faiss.IndexFlatL2(self.target_dim)
        else:
            self.index = None  # 使用numpy实现

        self.documents = []
        self.metadatas = []

        self.load_from_cache()

    def _align_index_dimension(self):
        """确保索引维度与模型维度一致（防止模型更换）"""
        if FAISS_AVAILABLE and self.index is not None:
            if self.index.d != self.target_dim:
                print(f"重建索引（旧维度: {self.index.d} → 新维度: {self.target_dim}）")
                self.index = faiss.IndexFlatL2(self.target_dim)
                # 重新添加所有文档的嵌入
                if self.documents:
                    embeddings = self.embedding_model.encode(self.documents)
                    self.index.add(np.array(embeddings, dtype=np.float32))
    
    def _split_text_with_bert(self, text: str, max_tokens: int = 400, overlap_tokens: int = 100) -> list[str]:
        """
        使用BERT tokenizer对文本进行智能分段，带重叠机制
        :param text: 待分段的文本
        :param max_tokens: 每个片段的最大token数（BERT max_length=512，推荐400以包含更多上下文）
        :param overlap_tokens: 片段之间的重叠token数（推荐100，约20-25%重叠）
        :return: 分段后的文本列表
        """
        try:
            tokenizer = self.embedding_model.tokenizer
            
            # 首先按段落分割（双换行）
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            if not paragraphs:
                # 如果没有段落，按单换行分割
                paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
            if not paragraphs:
                # 如果还是没有，使用整个文本
                paragraphs = [text]
            
            segments = []
            current_segment = ""
            last_segment_end = ""  # 用于存储上一个片段的结尾部分（用于重叠）
            
            for para in paragraphs:
                # 使用BERT tokenizer计算当前段落的token数
                para_tokens = tokenizer.tokenize(para)
                para_token_count = len(para_tokens)
                
                # 如果单个段落就超过max_tokens，需要进一步切分
                if para_token_count > max_tokens:
                    # 先保存当前累积的片段（带重叠）
                    if current_segment.strip():
                        segments.append(current_segment.strip())
                        # 保存当前片段的结尾部分作为下一个片段的开头（重叠）
                        last_segment_tokens = tokenizer.tokenize(current_segment)
                        if len(last_segment_tokens) > overlap_tokens:
                            # 取最后overlap_tokens个token作为重叠部分
                            overlap_text = self._extract_overlap_text(current_segment, tokenizer, overlap_tokens)
                            last_segment_end = overlap_text
                        else:
                            last_segment_end = current_segment
                        current_segment = ""
                    
                    # 按句子切分超长段落
                    sentences = re.split(r'[。！？\n]', para)
                    temp_segment = last_segment_end if last_segment_end else ""
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        
                        sent_tokens = tokenizer.tokenize(sent)
                        sent_token_count = len(sent_tokens)
                        
                        # 检查添加这个句子是否会超过限制
                        if temp_segment:
                            temp_tokens = tokenizer.tokenize(temp_segment + "。" + sent)
                        else:
                            temp_tokens = sent_tokens
                        
                        if len(temp_tokens) > max_tokens and temp_segment:
                            # 保存当前片段，开始新片段（带重叠）
                            segments.append(temp_segment.strip())
                            # 保存重叠部分
                            temp_segment_tokens = tokenizer.tokenize(temp_segment)
                            if len(temp_segment_tokens) > overlap_tokens:
                                overlap_text = self._extract_overlap_text(temp_segment, tokenizer, overlap_tokens)
                                temp_segment = overlap_text + "。" + sent
                            else:
                                temp_segment = temp_segment + "。" + sent
                        else:
                            # 添加到当前片段
                            if temp_segment:
                                temp_segment += "。" + sent
                            else:
                                temp_segment = sent
                    
                    # 保存最后一个片段
                    if temp_segment.strip():
                        current_segment = temp_segment.strip()
                    last_segment_end = ""
                else:
                    # 检查添加这个段落是否会超过限制
                    # 如果有重叠，先添加重叠部分
                    segment_to_check = last_segment_end + "\n\n" + current_segment if last_segment_end and current_segment else (last_segment_end if last_segment_end else current_segment)
                    if segment_to_check:
                        combined_tokens = tokenizer.tokenize(segment_to_check + "\n\n" + para)
                    else:
                        combined_tokens = para_tokens
                    
                    if len(combined_tokens) > max_tokens and current_segment:
                        # 保存当前片段，开始新片段（带重叠）
                        full_segment = (last_segment_end + "\n\n" + current_segment).strip() if last_segment_end else current_segment.strip()
                        segments.append(full_segment)
                        # 保存重叠部分
                        segment_tokens = tokenizer.tokenize(full_segment)
                        if len(segment_tokens) > overlap_tokens:
                            overlap_text = self._extract_overlap_text(full_segment, tokenizer, overlap_tokens)
                            current_segment = overlap_text + "\n\n" + para
                        else:
                            current_segment = full_segment + "\n\n" + para
                        last_segment_end = ""
                    else:
                        # 添加到当前片段
                        if last_segment_end:
                            current_segment = last_segment_end + "\n\n" + current_segment if current_segment else last_segment_end
                            last_segment_end = ""
                        if current_segment:
                            current_segment += "\n\n" + para
                        else:
                            current_segment = para
            
            # 保存最后一个片段
            if current_segment.strip():
                # 如果有重叠，合并重叠部分
                if last_segment_end and current_segment and last_segment_end not in current_segment:
                    segments.append((last_segment_end + "\n\n" + current_segment).strip())
                else:
                    segments.append(current_segment.strip())
            
            # 确保至少返回一个片段
            if not segments:
                segments = [text]
            
            logger.info(f"文本已分段：原始长度={len(text)}字符，分段数={len(segments)}，重叠={overlap_tokens}tokens")
            return segments
            
        except Exception as e:
            logger.error(f"BERT分词分段失败: {str(e)}，使用简单分段")
            # 降级到简单分段
            return self._simple_split_text(text, overlap_chars=int(overlap_tokens * 2))  # 粗略估算：1token≈2字符
    
    def _extract_overlap_text(self, text: str, tokenizer, overlap_tokens: int) -> str:
        """
        从文本末尾提取指定token数的文本（用于重叠）
        :param text: 原始文本
        :param tokenizer: BERT tokenizer
        :param overlap_tokens: 需要提取的token数
        :return: 重叠文本
        """
        try:
            tokens = tokenizer.tokenize(text)
            if len(tokens) <= overlap_tokens:
                return text
            
            # 取最后overlap_tokens个token
            overlap_tokens_list = tokens[-overlap_tokens:]
            # 转换为文本（需要处理特殊token）
            overlap_text = tokenizer.convert_tokens_to_string(overlap_tokens_list)
            return overlap_text.strip()
        except Exception as e:
            logger.warning(f"提取重叠文本失败: {str(e)}")
            # 降级方案：简单取最后N个字符
            return text[-overlap_tokens * 2:] if len(text) > overlap_tokens * 2 else text
    
    def _split_long_paragraph(self, para: str, chunk_size: int, overlap_chars: int) -> list[str]:
        """将超长段落按字符数切分为多段（带重叠）"""
        if len(para) <= chunk_size:
            return [para] if para.strip() else []
        out = []
        start = 0
        while start < len(para):
            end = min(start + chunk_size, len(para))
            out.append(para[start:end])
            start = end - overlap_chars if end < len(para) else len(para)
        return [s for s in out if s.strip()]

    def _simple_split_text(self, text: str, chunk_size: int = 500, overlap_chars: int = 100) -> list[str]:
        """
        文本分段：优先按段落，超长段落强制按字符切分（几万字不会变成一段）
        :param text: 待分段的文本
        :param chunk_size: 每个片段的最大字符数
        :param overlap_chars: 片段间重叠字符数
        :return: 分段后的文本列表
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()] if text.strip() else []

        segments = []
        current_chunk = ""
        last_chunk_end = ""

        for para in paragraphs:
            if len(para) > chunk_size:
                if current_chunk.strip():
                    segments.append(current_chunk.strip())
                    current_chunk = ""
                    last_chunk_end = ""
                sub_segs = self._split_long_paragraph(para, chunk_size, overlap_chars)
                segments.extend(sub_segs)
                continue

            chunk_to_check = (last_chunk_end + "\n\n" + current_chunk) if last_chunk_end and current_chunk else (last_chunk_end if last_chunk_end else current_chunk)

            if chunk_to_check and len(chunk_to_check) + len(para) + 2 > chunk_size:
                segments.append(chunk_to_check.strip())
                if len(chunk_to_check) > overlap_chars:
                    last_chunk_end = chunk_to_check[-overlap_chars:]
                else:
                    last_chunk_end = chunk_to_check
                current_chunk = para
            else:
                if last_chunk_end:
                    current_chunk = (last_chunk_end + "\n\n" + current_chunk) if current_chunk else last_chunk_end
                    last_chunk_end = ""
                current_chunk = (current_chunk + "\n\n" + para) if current_chunk else para

        if current_chunk.strip():
            segments.append(current_chunk.strip())

        return segments if segments else [text]

    def load_from_cache(self, cache_file: str = "faiss_kb_cache.pkl"):
        try:
            if os.path.exists(cache_file) and os.path.getsize(cache_file) >= 10:
                with open(cache_file, "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.metadatas = data.get("metadatas", [])

                    # 加载索引后校验维度
                    if FAISS_AVAILABLE and "index_bytes" in data:
                        self.index = faiss.deserialize_index(data["index_bytes"])
                        self._align_index_dimension()  # 关键：动态对齐维度
                    else:
                        if FAISS_AVAILABLE:
                            self.index = faiss.IndexFlatL2(self.target_dim)
                        else:
                            self.index = None
        except Exception as e:
            logger.warning(f"加载缓存失败: {str(e)}")
            if FAISS_AVAILABLE:
                self.index = faiss.IndexFlatL2(self.target_dim)
            else:
                self.index = None
            self.documents = []
            self.metadatas = []

    def add_setting(self, setting_type: str, content: str, enable_segmentation: bool = True) -> tuple[bool, str]:
        """
        添加设定时，使用BERT tokenizer进行分词分段，然后为每个片段生成嵌入并存入知识库
        :param setting_type: 设定类型（如"文章大纲"、"角色设定"等）
        :param content: 设定内容
        :param enable_segmentation: 是否启用分段（默认True）
        :return: (success, message) 成功为 True，失败为 False 及错误信息
        """
        try:
            segments_added = 0
            
            if enable_segmentation:
                if self._use_bert_split:
                    segments = self._split_text_with_bert(content, max_tokens=400, overlap_tokens=100)
                    logger.info(f"设定内容已分段为{len(segments)}个片段（BERT分词，每片段最大400 tokens，重叠100 tokens）")
                else:
                    # 通义 embedding 单条上限 2048 token，chunk_size 500 字符安全
                    segments = self._simple_split_text(content, chunk_size=500, overlap_chars=100)
                    logger.info(f"设定内容已分段为{len(segments)}个片段（字符分段，chunk_size=500）")
                
                # 为每个片段生成嵌入并存入知识库
                if len(segments) > 1:
                    # 多个片段：分别添加
                    segment_embeddings = []
                    for i, segment in enumerate(segments):
                        if segment.strip():  # 只添加非空片段
                            try:
                                embedding = self.embedding_model.encode([segment])
                                segment_embeddings.append((segment, embedding))
                                segments_added += 1
                            except Exception as e:
                                logger.warning(f"片段{i+1}嵌入生成失败: {str(e)}")
                    
                    # 批量添加到索引
                    if segment_embeddings:
                        self._align_index_dimension()
                        embeddings_list = [emb for _, emb in segment_embeddings]
                        segments_list = [seg for seg, _ in segment_embeddings]
                        
                        # 合并所有嵌入
                        all_embeddings = np.concatenate(embeddings_list, axis=0)
                        
                        if FAISS_AVAILABLE and self.index is not None:
                            self.index.add(np.array(all_embeddings, dtype=np.float32))
                        
                        # 添加到文档列表
                        for segment in segments_list:
                            self.documents.append(segment)
                            # 记录类型元数据，并标记为片段
                            self.metadatas.append({
                                "type": setting_type,
                                "is_segment": True,
                                "original_length": len(content)
                            })
                    
                    # 同时保存完整内容作为主文档（便于检索完整设定）
                    if segments_added > 0:
                        full_embedding = self.embedding_model.encode([content])
                        self._align_index_dimension()
                        if FAISS_AVAILABLE and self.index is not None:
                            self.index.add(np.array(full_embedding, dtype=np.float32))
                        self.documents.append(content)
                        self.metadatas.append({
                            "type": setting_type,
                            "is_segment": False,
                            "segment_count": segments_added
                        })
                        segments_added += 1  # 完整文档也算一个
                else:
                    # 只有一个片段，直接添加
                    embedding = self.embedding_model.encode([content])
                    self._align_index_dimension()
                    if FAISS_AVAILABLE and self.index is not None:
                        self.index.add(np.array(embedding, dtype=np.float32))
                    self.documents.append(content)
                    self.metadatas.append({"type": setting_type, "is_segment": False})
                    segments_added = 1
            else:
                # 不启用分段，直接添加完整内容
                embedding = self.embedding_model.encode([content])
                self._align_index_dimension()
                if FAISS_AVAILABLE and self.index is not None:
                    self.index.add(np.array(embedding, dtype=np.float32))
                self.documents.append(content)
                self.metadatas.append({"type": setting_type, "is_segment": False})
                segments_added = 1
            
            self.save_to_cache()
            return True, f"设定已添加（类型：{setting_type}，片段数：{segments_added}，总数：{len(self.documents)}）"
        except Exception as e:
            logger.error(f"添加设定失败: {str(e)}", exc_info=True)
            return False, str(e)

    def search_relevant_settings(self, query: str, top_n: int = 3) -> list[str]:
        """检索相关设定"""
        if not self.documents:
            return []
        try:
            query_embedding = self.embedding_model.encode([query])
            self._align_index_dimension()

            if FAISS_AVAILABLE and self.index is not None:
                distances, indices = self.index.search(
                    np.array(query_embedding), min(top_n, len(self.documents))
                )
                return [self.documents[i] for i in indices[0] if 0 <= i < len(self.documents)]
            else:
                query_vec = query_embedding[0]
                similarities = []
                for i, doc in enumerate(self.documents):
                    doc_vec = self.embedding_model.encode([doc])[0]
                    sim = np.dot(query_vec, doc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-8)
                    similarities.append((sim, i))
                similarities.sort(reverse=True, key=lambda x: x[0])
                return [self.documents[i] for _, i in similarities[:top_n]]
        except Exception as e:
            logger.error(f"检索设定失败: {str(e)}")
            return []

    def search_relevant_documents(self, query: str, top_n: int = 15):
        """检索相关设定，返回 LangChain Document 列表（供 create_retrieval_chain 使用）"""
        from langchain_core.documents import Document
        if not self.documents:
            return []
        try:
            query_embedding = self.embedding_model.encode([query])
            self._align_index_dimension()
            if FAISS_AVAILABLE and self.index is not None:
                _, indices = self.index.search(
                    np.array(query_embedding), min(top_n, len(self.documents))
                )
                return [
                    Document(
                        page_content=self.documents[i],
                        metadata=self.metadatas[i] if i < len(self.metadatas) else {}
                    )
                    for i in indices[0] if 0 <= i < len(self.documents)
                ]
            else:
                query_vec = query_embedding[0]
                similarities = []
                for i, doc in enumerate(self.documents):
                    doc_vec = self.embedding_model.encode([doc])[0]
                    sim = np.dot(query_vec, doc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-8)
                    similarities.append((sim, i))
                similarities.sort(reverse=True, key=lambda x: x[0])
                return [
                    Document(
                        page_content=self.documents[i],
                        metadata=self.metadatas[i] if i < len(self.metadatas) else {}
                    )
                    for _, i in similarities[:top_n]
                ]
        except Exception as e:
            logger.error(f"检索 Document 失败: {str(e)}")
            return []

    def as_langchain_retriever(self, top_k: int = 15):
        """返回 LangChain BaseRetriever，供 create_retrieval_chain 使用"""
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.callbacks import CallbackManagerForRetrieverRun
        from langchain_core.documents import Document

        kb, k = self, top_k

        class KBRetriever(BaseRetriever):
            top_k: int = 15

            def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None) -> list[Document]:
                return kb.search_relevant_documents(query, top_n=self.top_k)

        return KBRetriever(top_k=k)

    def save_to_cache(self, cache_file: str = "faiss_kb_cache.pkl"):
        try:
            data = {
                "documents": self.documents,
                "metadatas": self.metadatas,
                "model_dimension": self.target_dim  # 缓存中记录维度
            }
            if FAISS_AVAILABLE and self.index is not None:
                index_bytes = faiss.serialize_index(self.index)
                data["index_bytes"] = index_bytes
            
            with open(cache_file, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            logger.warning(f"保存缓存失败: {str(e)}")

    def clear_all_settings(self):
        try:
            self.documents = []
            self.metadatas = []
            if FAISS_AVAILABLE:
                self.index = faiss.IndexFlatL2(self.target_dim)  # 用当前维度重建空索引
            else:
                self.index = None

            cache_file = "faiss_kb_cache.pkl"
            if os.path.exists(cache_file):
                os.remove(cache_file)
            self.save_to_cache()
            return "已清空所有设定"
        except Exception as e:
            logger.error(f"清空设定失败: {str(e)}")
            return f"清空失败：{str(e)}"

    def delete_setting(self, index: int) -> bool:
        if 0 <= index < len(self.documents):
            try:
                del self.documents[index]
                del self.metadatas[index]
                if FAISS_AVAILABLE:
                    self.index = faiss.IndexFlatL2(self.target_dim)  # 用当前维度重建索引
                    if self.documents:
                        embeddings = self.embedding_model.encode(self.documents)
                        self.index.add(np.array(embeddings, dtype=np.float32))
                else:
                    self.index = None
                self.save_to_cache()
                return True
            except Exception as e:
                logger.error(f"删除设定失败: {str(e)}")
                return False
        return False

    def get_all_settings(self):
        return list(zip(self.documents, self.metadatas))

    def evaluate_embedding_model(
        self,
        top_k_list: list = None,
        query_len: int = 300,
        max_samples: int = 50,
        query_mode: str = "prefix",
    ) -> dict:
        """
        嵌入模型综合评估（自检索法）
        指标：Recall@k、Precision@k、NDCG@k、Hit@1、MRR、AP、Mean Rank

        :param query_mode: 查询模式
            - "prefix": 用文档前 N 字作查询（与存储重叠大，较容易）
            - "suffix": 用文档后 N 字作查询（无重叠，更严格）
            - "middle": 用文档中间 N 字作查询（无重叠，更严格）
        """
        top_k_list = top_k_list or [1, 3, 5, 8, 10]
        k_max = max(top_k_list)

        def _make_query(doc: str, mode: str, n: int) -> str:
            if len(doc) <= n:
                return doc
            if mode == "prefix":
                return doc[:n]
            if mode == "suffix":
                return doc[-n:]
            if mode == "middle":
                start = (len(doc) - n) // 2
                return doc[start : start + n]
            return doc[:n]

        logic_map = {
            "prefix": "自检索-前缀：用文档前N字作查询（与存储重叠较大，较易）",
            "suffix": "自检索-后缀：用文档后N字作查询（无重叠，更严格）",
            "middle": "自检索-中间：用文档中间N字作查询（无重叠，更严格）",
        }
        logic = logic_map.get(query_mode, logic_map["prefix"])

        empty_metrics = {
            "recall_at_k": {str(k): 0.0 for k in top_k_list},
            "recalled_at_k": {str(k): 0 for k in top_k_list},
            "precision_at_k": {str(k): 0.0 for k in top_k_list},
            "ndcg_at_k": {str(k): 0.0 for k in top_k_list},
            "hit_at_1": 0.0,
            "mrr": 0.0,
            "map": 0.0,
            "mean_rank": None,
        }
        if not self.documents:
            return {
                "model": getattr(self.embedding_model, "model_id", None) or getattr(self.embedding_model, "model", "text-embedding-v2"),
                "dimension": self.target_dim,
                "total": 0,
                "query_len": query_len,
                "query_mode": query_mode,
                **empty_metrics,
                "logic": logic,
            }

        total = min(len(self.documents), max_samples)
        indices = list(range(total)) if total == len(self.documents) else np.random.RandomState(42).choice(len(self.documents), total, replace=False).tolist()

        recalled_at_k = {str(k): 0 for k in top_k_list}
        precision_sum_at_k = {str(k): 0.0 for k in top_k_list}
        ndcg_sum_at_k = {str(k): 0.0 for k in top_k_list}
        hit_at_1_count = 0
        reciprocal_ranks = []
        ap_list = []
        ranks_found = []

        for i in indices:
            doc = self.documents[i]
            query = _make_query(doc, query_mode, query_len)
            if not query.strip():
                continue
            results = self.search_relevant_settings(query, top_n=k_max)
            try:
                rank = results.index(doc) + 1
            except ValueError:
                rank = None

            for k in top_k_list:
                if rank is not None and rank <= k:
                    recalled_at_k[str(k)] += 1
                    precision_sum_at_k[str(k)] += 1.0 / k
                    ndcg_sum_at_k[str(k)] += 1.0 / (np.log2(rank + 1))
            if rank == 1:
                hit_at_1_count += 1
            if rank is not None:
                reciprocal_ranks.append(1.0 / rank)
                ap_list.append(1.0 / rank)
                ranks_found.append(rank)

        n = len([i for i in indices if self.documents[i].strip()])
        n = max(n, 1)
        recall_at_k = {k: round(recalled_at_k[str(k)] / n, 4) for k in top_k_list}
        precision_at_k = {k: round(precision_sum_at_k[str(k)] / n, 4) for k in top_k_list}
        ndcg_at_k = {k: round(ndcg_sum_at_k[str(k)] / n, 4) for k in top_k_list}
        hit_at_1 = round(hit_at_1_count / n, 4)
        mrr = round(sum(reciprocal_ranks) / n, 4) if reciprocal_ranks else 0.0
        map_score = round(sum(ap_list) / n, 4) if ap_list else 0.0
        mean_rank = round(sum(ranks_found) / len(ranks_found), 2) if ranks_found else None

        model_name = getattr(self.embedding_model, "model_id", None) or getattr(self.embedding_model, "model", "text-embedding-v2")

        return {
            "model": str(model_name),
            "dimension": self.target_dim,
            "total": total,
            "query_len": query_len,
            "query_mode": query_mode,
            "recall_at_k": recall_at_k,
            "recalled_at_k": {k: recalled_at_k[str(k)] for k in top_k_list},
            "precision_at_k": precision_at_k,
            "ndcg_at_k": ndcg_at_k,
            "hit_at_1": hit_at_1,
            "mrr": mrr,
            "map": map_score,
            "mean_rank": mean_rank,
            "logic": logic,
        }
