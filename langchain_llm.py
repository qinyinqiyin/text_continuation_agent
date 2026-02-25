"""
LangChain Tongyi (通义千问) LLM 适配器
兼容 BaseModel 接口，底层使用 LangChain
"""
from config import logger
from base_classes import BaseModel


class LangChainTongyi(BaseModel):
    """使用 LangChain 的 Tongyi 封装，兼容 BaseModel"""

    def __init__(self, api_key: str, model_name: str = "qwen-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        try:
            import dashscope
            from langchain_community.llms import Tongyi

            dashscope.api_key = self.api_key
            self.llm = Tongyi(
                model_name=self.model_name,
                dashscope_api_key=self.api_key,
                model_kwargs={"temperature": 0.7, "max_tokens": 1000},
            )
            logger.info(f"LangChain Tongyi 已初始化: {self.model_name}")
        except ImportError as e:
            logger.error(f"LangChain 依赖缺失: {e}")
            raise ImportError("请安装: pip install langchain langchain-community")
        except Exception as e:
            logger.error(f"Tongyi 初始化失败: {e}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        if not self.llm:
            raise RuntimeError("LangChain Tongyi 未正确初始化")

        max_tokens = kwargs.get("max_new_tokens", 1000)
        temperature = kwargs.get("temperature", 0.7)

        try:
            # 使用 bind 传入本次调用的参数
            llm = self.llm.bind(
                max_tokens=max_tokens,
                temperature=temperature,
            )
            result = llm.invoke(prompt)
            return (result or "").strip()
        except Exception as e:
            logger.error(f"LangChain 生成错误: {e}")
            raise
