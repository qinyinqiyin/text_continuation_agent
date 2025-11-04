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

        # 从本地加载 Tokenizer 和 Model（如果本地不存在会自动从Hugging Face下载）
        # 优先使用本地路径，如果失败则从Hugging Face下载
        try:
            self.tokenizer = BertTokenizer.from_pretrained(self.local_model_path)
            self.model = BertModel.from_pretrained(self.local_model_path)
        except Exception as e:
            # 如果本地加载失败，尝试直接从Hugging Face加载
            print(f"本地模型加载失败: {str(e)}，尝试从Hugging Face直接加载...")
            self.tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
            self.model = BertModel.from_pretrained("bert-base-chinese")
            # 保存到本地以便下次使用
            try:
                self.tokenizer.save_pretrained(self.local_model_path)
                self.model.save_pretrained(self.local_model_path)
                print("✅ 已保存模型到本地目录")
            except Exception as save_error:
                print(f"⚠️ 保存模型到本地失败（不影响使用）: {str(save_error)}")

        # 设置模型为评估模式
        self.model.eval()

        # 获取模型维度
        self.dimension = self.model.config.hidden_size
        print(f"模型固定维度: {self.dimension}")

    def _validate_model(self):
        """验证模型目录和关键文件是否存在，如果不存在则自动下载"""
        # 检查模型目录是否存在
        if not os.path.exists(self.local_model_path):
            os.makedirs(self.local_model_path, exist_ok=True)
            print(f"创建模型目录: {self.local_model_path}")

        # 检查关键文件是否存在
        required_files = ["vocab.txt", "config.json", "pytorch_model.bin"]
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.local_model_path, f))]
        
        # 如果缺少关键文件，尝试从Hugging Face下载
        if missing_files:
            print(f"检测到缺失文件: {missing_files}")
            print("正在从Hugging Face下载模型文件...")
            try:
                from transformers import BertTokenizer, BertModel, BertConfig
                
                # 下载并保存模型
                print("下载tokenizer...")
                tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
                tokenizer.save_pretrained(self.local_model_path)
                
                print("下载模型配置...")
                config = BertConfig.from_pretrained("bert-base-chinese")
                config.save_pretrained(self.local_model_path)
                
                print("下载模型权重（这可能需要几分钟，约400MB）...")
                model = BertModel.from_pretrained("bert-base-chinese")
                model.save_pretrained(self.local_model_path)
                
                print("✅ 模型下载完成！")
                
                # 重新检查
                missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.local_model_path, f))]
                
            except Exception as e:
                print(f"⚠️ 自动下载失败: {str(e)}")
                print("提示：如果网络问题，可以手动下载模型文件")
                raise FileNotFoundError(f"无法获取模型文件: {str(e)}")
        
        # 如果还有缺失文件，抛出错误
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
