"""
LangChain Tongyi (通义千问) LLM 适配器
"""
from config import logger


class LangChainTongyi:
    """使用 LangChain 的 Tongyi 封装"""

    def __init__(self, api_key: str, model_name: str = "qwen-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = None
        self.chat_llm = None
        self._init_llm()

    def _init_llm(self):
        try:
            import dashscope
            from langchain_community.llms import Tongyi
            from langchain_community.chat_models import ChatTongyi

            dashscope.api_key = self.api_key
            self.llm = Tongyi(
                model_name=self.model_name,
                dashscope_api_key=self.api_key,
                model_kwargs={"temperature": 0.7, "max_tokens": 1000},
            )
            # Chat 封装：供 tool-calling Agent 绑定工具（Completes 接口不支持 bind_tools）
            try:
                self.chat_llm = ChatTongyi(
                    dashscope_api_key=self.api_key,
                    model=self.model_name,
                    model_kwargs={"temperature": 0.7},
                )
                logger.info("ChatTongyi 已就绪（可作为带工具 Agent 的对话模型）")
            except TypeError:
                self.chat_llm = ChatTongyi(
                    dashscope_api_key=self.api_key,
                    model_name=self.model_name,
                    model_kwargs={"temperature": 0.7},
                )
                logger.info("ChatTongyi 已就绪（model_name 形参初始化）")
            except Exception as e_chat:
                self.chat_llm = None
                logger.warning("ChatTongyi 初始化失败，将回退无工具链路：%s", e_chat)
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
