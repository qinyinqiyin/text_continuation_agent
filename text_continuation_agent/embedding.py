import torch
import numpy as np
import os
from transformers import BertTokenizer, BertModel

class PyTorchEmbeddingModel:
    def __init__(self, model_name: str = "bert-base-chinese", local_dir: str = "E:\\text_continuation_agent"):
        self.local_model_path = os.path.join(local_dir, model_name)
        self._validate_model()  

        # 从本地加载 Tokenizer 和 Model
        self.tokenizer = BertTokenizer.from_pretrained(self.local_model_path)
        self.model = BertModel.from_pretrained(self.local_model_path)

        # 设置模型为评估模式
        self.model.eval()

        # 获取模型维度
        self.dimension = self.model.config.hidden_size
        print(f"模型固定维度: {self.dimension}")

    def _validate_model(self):
        """验证模型目录和关键文件是否存在"""
        # 检查模型目录是否存在
        if not os.path.exists(self.local_model_path):
            raise FileNotFoundError(f"模型目录不存在: {self.local_model_path}")

        # 检查关键文件是否存在
        required_files = ["vocab.txt", "config.json", "pytorch_model.bin"]
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.local_model_path, f))]
        if missing_files:
            raise FileNotFoundError(f"缺失关键文件: {missing_files}，请确认模型文件完整性")

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        将文本列表编码为向量
        :param texts: 文本列表
        :return: 编码后的向量，形状为 [len(texts), dimension]
        """
        with torch.no_grad():
            # 使用 Tokenizer 对文本进行编码
            inputs = self.tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=self.model.config.max_position_embeddings,
                return_tensors="pt"
            )

            # 使用模型生成嵌入
            outputs = self.model(**inputs)

            # 提取 [CLS] token 的嵌入，作为文本整体表示
            embeddings = outputs.last_hidden_state[:, 0, :].numpy()

            # 强制校验维度
            assert embeddings.shape[1] == self.dimension, \
                f"编码维度异常: 预期 {self.dimension}, 实际 {embeddings.shape[1]}"
            return embeddings

