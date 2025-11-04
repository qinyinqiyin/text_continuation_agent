import os
import pickle
import numpy as np
from config import logger

# 尝试导入faiss，如果失败则使用numpy替代
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS不可用，将使用numpy进行向量检索")


class FAISSKnowledgeBase:
    def __init__(self, model_name: str = "bert-base-chinese", local_dir: str = None, 
                 use_api: bool = True, api_type: str = "dashscope", api_key: str = None):
        """
        初始化知识库
        :param model_name: 本地模型名称（仅在use_api=False时使用）
        :param local_dir: 本地模型目录
        :param use_api: 是否使用API嵌入服务（推荐，避免加载大型模型）
        :param api_type: API类型，"dashscope", "huggingface", "openai"
        :param api_key: API密钥
        """
        # 优先使用API嵌入模型
        if use_api:
            try:
                from embedding_api import HybridEmbeddingModel
                self.embedding_model = HybridEmbeddingModel(
                    api_type=api_type,
                    api_key=api_key,
                    local_model_name=model_name,
                    local_dir=local_dir
                )
                self.target_dim = self.embedding_model.dimension
                logger.info(f"使用API嵌入模型: {api_type}")
            except Exception as e:
                logger.warning(f"API嵌入模型初始化失败: {str(e)}，尝试使用本地模型")
                use_api = False
        
        # Fallback到本地模型
        if not use_api:
            try:
                from embedding import PyTorchEmbeddingModel
                if local_dir is None:
                    local_dir = os.path.dirname(os.path.abspath(__file__))
                self.embedding_model = PyTorchEmbeddingModel(model_name, local_dir)
                self.target_dim = self.embedding_model.dimension
                logger.info(f"使用本地嵌入模型: {model_name}")
            except Exception as e:
                logger.error(f"本地嵌入模型初始化失败: {str(e)}")
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

    def add_setting(self, setting_type: str, content: str) -> str:
        """添加设定时，明确标记类型（如"文章大纲"）"""
        try:
            embedding = self.embedding_model.encode([content])
            self._align_index_dimension()
            if FAISS_AVAILABLE and self.index is not None:
                self.index.add(np.array(embedding, dtype=np.float32))
            self.documents.append(content)
            # 记录类型元数据（关键：用于后续过滤"文章大纲"）
            self.metadatas.append({"type": setting_type})
            self.save_to_cache()
            return f"设定已添加（类型：{setting_type}，总数：{len(self.documents)}）"
        except Exception as e:
            logger.error(f"添加设定失败: {str(e)}")
            return f"添加失败：{str(e)}"

    def search_relevant_settings(self, query: str, top_n: int = 3) -> list[str]:
        if not self.documents:
            return []
        try:
            query_embedding = self.embedding_model.encode([query])
            self._align_index_dimension()  # 检索前确保维度一致
            
            if FAISS_AVAILABLE and self.index is not None:
                distances, indices = self.index.search(
                    np.array(query_embedding), min(top_n, len(self.documents))
                )
                return [self.documents[i] for i in indices[0] if 0 <= i < len(self.documents)]
            else:
                # 使用numpy进行向量检索（当FAISS不可用时）
                query_vec = query_embedding[0]
                similarities = []
                for i, doc in enumerate(self.documents):
                    doc_embedding = self.embedding_model.encode([doc])
                    doc_vec = doc_embedding[0]
                    # 计算余弦相似度
                    similarity = np.dot(query_vec, doc_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(doc_vec) + 1e-8
                    )
                    similarities.append((similarity, i))
                
                # 排序并返回top_n
                similarities.sort(reverse=True)
                return [self.documents[i] for _, i in similarities[:top_n]]
        except Exception as e:
            logger.error(f"检索设定失败: {str(e)}")
            return []

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
