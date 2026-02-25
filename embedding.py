import os
import numpy as np


def get_embedding_model(backend: str = "dashscope", **kwargs):
    """
    获取嵌入模型（通义 embedding）
    :param backend: 仅支持 "dashscope"
    """
    kw = {k: v for k, v in kwargs.items() if k in ("model", "api_key", "dimension")}
    if backend == "dashscope":
        return DashScopeEmbeddingModel(**kw)
    raise ValueError(f"仅支持 backend=dashscope")


class DashScopeEmbeddingModel:
    """阿里云通义 embedding（DashScope text-embedding-v2）"""

    MODEL = "text-embedding-v2"
    DIMENSION = 1536
    MAX_TOKENS = 2048  # 单条文本上限（token），按字符估算时用 ~2000 字符
    MAX_CHARS = 2000   # 保守截断长度（约 1000–2000 token）

    def __init__(self, model: str = None, api_key: str = None, dimension: int = None):
        self.model = model or self.MODEL
        self.model_id = self.model  # 供 evaluate 等使用
        self.dimension = dimension or self.DIMENSION
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        self.tokenizer = None

    def _truncate_text(self, text: str) -> str:
        """截断超长文本，满足 [1, 2048] token 限制；空文本用占位符"""
        if not text or not text.strip():
            return " "  # 最少 1 字符，避免 0 长度
        s = text.strip()
        if len(s) > self.MAX_CHARS:
            return s[: self.MAX_CHARS]
        return s

    def encode(self, texts: list[str]) -> np.ndarray:
        """将文本列表编码为向量"""
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)
        try:
            import dashscope
            from dashscope import TextEmbedding

            dashscope.api_key = self.api_key
            if not self.api_key:
                raise ValueError("请在 config 中配置 DASHSCOPE_API_KEY")

            # 截断/过滤，满足 [1, 2048] token 限制
            prepared = [self._truncate_text(t) for t in texts]

            batch_size = 25
            all_embeddings = []
            for i in range(0, len(prepared), batch_size):
                batch = prepared[i : i + batch_size]
                rsp = TextEmbedding.call(
                    model=self.model,
                    input=batch,
                    text_type="document",
                    api_key=self.api_key,
                )
                if rsp.status_code != 200:
                    raise RuntimeError(f"TextEmbedding 调用失败: {rsp.message}")
                for rec in rsp.output["embeddings"]:
                    vec = np.array(rec["embedding"], dtype=np.float32)
                    if len(vec) != self.dimension:
                        vec = vec[:self.dimension] if len(vec) > self.dimension else np.pad(vec, (0, self.dimension - len(vec)))
                    all_embeddings.append(vec)
            return np.stack(all_embeddings)
        except ImportError:
            raise ImportError("通义 embedding 需要: pip install dashscope")

