import torch
import numpy as np
import os
from transformers import BertTokenizer, BertModel

class PyTorchEmbeddingModel:
    def __init__(self, model_name: str = "bert-base-chinese", local_dir: str = None):
        # 如果没有指定目录，使用当前脚本所在目录
        if local_dir is None:
            local_dir = os.path.dirname(os.path.abspath(__file__))
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
        
        # 如果缺少 config.json，尝试从 transformers 库获取
        if "config.json" in missing_files:
            try:
                from transformers import BertConfig
                print(f"检测到缺少 config.json，正在从 transformers 库获取默认配置...")
                config = BertConfig.from_pretrained("bert-base-chinese")
                
                # 验证并调整词汇表大小以匹配本地的 vocab.txt
                vocab_file = os.path.join(self.local_model_path, "vocab.txt")
                if os.path.exists(vocab_file):
                    with open(vocab_file, 'r', encoding='utf-8') as f:
                        actual_vocab_size = len(f.readlines())
                    if config.vocab_size != actual_vocab_size:
                        print(f"调整词汇表大小: {config.vocab_size} -> {actual_vocab_size}")
                        config.vocab_size = actual_vocab_size
                
                config.save_pretrained(self.local_model_path)
                config_path = os.path.join(self.local_model_path, "config.json")
                print(f"已保存 config.json 到 {config_path}")
                missing_files.remove("config.json")
            except Exception as e:
                print(f"无法自动获取 config.json: {str(e)}")
        
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
