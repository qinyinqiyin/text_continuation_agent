import os
import pickle
import numpy as np
import faiss
from embedding import PyTorchEmbeddingModel
from config import logger
import torch
from transformers import BertTokenizer, BertModel


class FAISSKnowledgeBase:
    def __init__(self, model_name: str = "bert-base-chinese", local_dir: str = "E:\\text_continuation_agent"):
        self.embedding_model = PyTorchEmbeddingModel(model_name, local_dir)
        # 动态获取模型维度
        self.target_dim = self.embedding_model.dimension

        # 初始化 FAISS 索引（维度与模型一致）
        self.index = faiss.IndexFlatL2(self.target_dim)
        self.documents = []
        self.metadatas = []
        self.load_from_cache()

    def _align_index_dimension(self):
        """确保索引维度与模型维度一致（防止模型更换）"""
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
                    if "index_bytes" in data:
                        self.index = faiss.deserialize_index(data["index_bytes"])
                        self._align_index_dimension()  # 关键：动态对齐维度
                    else:
                        self.index = faiss.IndexFlatL2(self.target_dim)
        except Exception as e:
            logger.warning(f"加载缓存失败: {str(e)}")
            self.index = faiss.IndexFlatL2(self.target_dim)
            self.documents = []
            self.metadatas = []

    def add_setting(self, setting_type: str, content: str) -> str:
        try:
            # 生成嵌入（维度由模型保证）
            embedding = self.embedding_model.encode([content])

            # 再次校验索引维度（防止中途模型被替换）
            self._align_index_dimension()

            # 添加到索引
            self.index.add(np.array(embedding, dtype=np.float32))
            self.documents.append(content)
            self.metadatas.append({"type": setting_type})
            self.save_to_cache()
            return f"设定已添加（维度: {self.target_dim}，总数: {len(self.documents)}）"
        except Exception as e:
            logger.error(f"添加设定失败: {str(e)}")
            return f"添加失败：{str(e)}"

    def search_relevant_settings(self, query: str, top_n: int = 3) -> list[str]:
        if not self.documents:
            return []
        try:
            query_embedding = self.embedding_model.encode([query])
            self._align_index_dimension()  # 检索前确保维度一致
            distances, indices = self.index.search(
                np.array(query_embedding), min(top_n, len(self.documents))
            )
            return [self.documents[i] for i in indices[0] if 0 <= i < len(self.documents)]
        except Exception as e:
            logger.error(f"检索设定失败: {str(e)}")
            return []

    # 其他方法（save_to_cache/clear_all_settings/delete_setting等）保持不变
    def save_to_cache(self, cache_file: str = "faiss_kb_cache.pkl"):
        try:
            index_bytes = faiss.serialize_index(self.index)
            with open(cache_file, "wb") as f:
                pickle.dump({
                    "documents": self.documents,
                    "metadatas": self.metadatas,
                    "index_bytes": index_bytes,
                    "model_dimension": self.target_dim  # 缓存中记录维度
                }, f)
        except Exception as e:
            logger.warning(f"保存缓存失败: {str(e)}")

    def clear_all_settings(self):
        try:
            self.documents = []
            self.metadatas = []
            self.index = faiss.IndexFlatL2(self.target_dim)  # 用当前维度重建空索引

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
                self.index = faiss.IndexFlatL2(self.target_dim)  # 用当前维度重建索引
                if self.documents:
                    embeddings = self.embedding_model.encode(self.documents)
                    self.index.add(np.array(embeddings, dtype=np.float32))
                self.save_to_cache()
                return True
            except Exception as e:
                logger.error(f"删除设定失败: {str(e)}")
                return False
        return False

    def get_all_settings(self):
        return list(zip(self.documents, self.metadatas))
