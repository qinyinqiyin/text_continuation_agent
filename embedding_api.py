"""
基于API的嵌入模型实现
使用外部API服务生成嵌入向量，避免在Vercel上加载大型模型
支持：
1. Hugging Face Inference API
2. DashScope Embedding API（阿里云）
3. OpenAI Embeddings API
"""
import os
import requests
import numpy as np
from typing import List
from config import logger


class APIEmbeddingModel:
    """基于API的嵌入模型，避免本地加载大型模型"""
    
    def __init__(self, api_type: str = "dashscope", api_key: str = None, model_name: str = "text-embedding-v1"):
        """
        初始化API嵌入模型
        :param api_type: API类型，支持 "dashscope", "huggingface", "openai"
        :param api_key: API密钥
        :param model_name: 模型名称
        """
        self.api_type = api_type
        self.api_key = api_key or os.getenv(f"{api_type.upper()}_API_KEY", "")
        self.model_name = model_name
        
        # 根据API类型设置维度
        self.dimension_map = {
            "dashscope": {
                "text-embedding-v1": 1536,
                "text-embedding-v2": 1536
            },
            "huggingface": {
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": 384,
                "sentence-transformers/distiluse-base-multilingual-cased": 512
            },
            "openai": {
                "text-embedding-ada-002": 1536,
                "text-embedding-3-small": 1536,
                "text-embedding-3-large": 3072
            }
        }
        
        self.dimension = self.dimension_map.get(api_type, {}).get(model_name, 1536)
        
        if not self.api_key:
            logger.warning(f"{api_type} API密钥未设置，嵌入功能可能不可用")
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """
        将文本列表编码为向量
        :param texts: 文本列表
        :return: 编码后的向量，形状为 [len(texts), dimension]
        """
        if self.api_type == "dashscope":
            return self._encode_dashscope(texts)
        elif self.api_type == "huggingface":
            return self._encode_huggingface(texts)
        elif self.api_type == "openai":
            return self._encode_openai(texts)
        else:
            raise ValueError(f"不支持的API类型: {self.api_type}")
    
    def _encode_dashscope(self, texts: List[str]) -> np.ndarray:
        """使用DashScope API生成嵌入"""
        import dashscope
        dashscope.api_key = self.api_key
        
        from dashscope import TextEmbedding
        
        embeddings = []
        # DashScope支持批量处理
        try:
            response = TextEmbedding.call(
                model=self.model_name,
                input=texts
            )
            
            if response.status_code == 200:
                for item in response.output['embeddings']:
                    embeddings.append(item['embedding'])
            else:
                raise Exception(f"DashScope API错误: {response.message}")
        except Exception as e:
            logger.error(f"DashScope嵌入失败: {str(e)}")
            # 返回零向量作为fallback
            return np.zeros((len(texts), self.dimension), dtype=np.float32)
        
        return np.array(embeddings, dtype=np.float32)
    
    def _encode_huggingface(self, texts: List[str]) -> np.ndarray:
        """使用Hugging Face Inference API生成嵌入"""
        api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_name}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        embeddings = []
        try:
            # Hugging Face API可能需要逐个处理
            for text in texts:
                response = requests.post(
                    api_url,
                    headers=headers,
                    json={"inputs": text},
                    timeout=30
                )
                if response.status_code == 200:
                    embeddings.append(response.json())
                else:
                    logger.warning(f"Hugging Face API错误: {response.text}")
                    embeddings.append([0.0] * self.dimension)
        except Exception as e:
            logger.error(f"Hugging Face嵌入失败: {str(e)}")
            return np.zeros((len(texts), self.dimension), dtype=np.float32)
        
        return np.array(embeddings, dtype=np.float32)
    
    def _encode_openai(self, texts: List[str]) -> np.ndarray:
        """使用OpenAI API生成嵌入"""
        try:
            import openai
            openai.api_key = self.api_key
            
            response = openai.embeddings.create(
                model=self.model_name,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            return np.array(embeddings, dtype=np.float32)
        except Exception as e:
            logger.error(f"OpenAI嵌入失败: {str(e)}")
            return np.zeros((len(texts), self.dimension), dtype=np.float32)


class HybridEmbeddingModel:
    """混合嵌入模型：优先使用API，fallback到本地模型"""
    
    def __init__(self, api_type: str = "dashscope", api_key: str = None, 
                 local_model_name: str = "bert-base-chinese", local_dir: str = None):
        self.api_model = None
        self.local_model = None
        
        # 尝试初始化API模型
        try:
            self.api_model = APIEmbeddingModel(api_type, api_key)
            if self.api_model.api_key:
                self.dimension = self.api_model.dimension
                logger.info(f"使用API嵌入模型: {api_type}")
                return
        except Exception as e:
            logger.warning(f"API嵌入模型初始化失败: {str(e)}")
        
        # Fallback到本地模型
        try:
            from embedding import PyTorchEmbeddingModel
            self.local_model = PyTorchEmbeddingModel(local_model_name, local_dir)
            self.dimension = self.local_model.dimension
            logger.info(f"使用本地嵌入模型: {local_model_name}")
        except Exception as e:
            logger.error(f"本地嵌入模型初始化失败: {str(e)}")
            raise
    
    def encode(self, texts: List[str]) -> np.ndarray:
        """编码文本，优先使用API"""
        if self.api_model and self.api_model.api_key:
            try:
                return self.api_model.encode(texts)
            except Exception as e:
                logger.warning(f"API编码失败，使用本地模型: {str(e)}")
        
        if self.local_model:
            return self.local_model.encode(texts)
        
        raise RuntimeError("没有可用的嵌入模型")

