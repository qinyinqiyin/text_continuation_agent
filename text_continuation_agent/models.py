import json
import os
import dashscope  # 提前导入dashscope
from config import logger
from base_classes import BaseModel


class APIModel(BaseModel):
    def __init__(self, api_key: str, model_name: str = "qwen-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        self.dashscope_missing = False

        try:
            # 显式设置API密钥
            dashscope.api_key = self.api_key  # 关键：确保密钥被正确设置

            # 验证密钥是否生效（可选，用于调试）
            if not dashscope.api_key:
                raise ValueError("API密钥未正确设置，请检查输入")

            logger.info(f"初始化API模型：{model_name}，密钥已配置")
        except ImportError:
            with open("app_error.log", "a") as f:
                f.write("未找到dashscope库，请安装：pip install dashscope==1.19.3\n")
            self.dashscope_missing = True
        except Exception as e:
            logger.error(f"API密钥配置失败：{str(e)}")
            self.dashscope_missing = True

    def generate(self, prompt: str, **kwargs) -> str:
        if self.dashscope_missing:
            raise ImportError("请安装dashscope库：pip install dashscope==1.19.3")

        # 再次检查密钥（防止意外覆盖）
        if not dashscope.api_key:
            raise ValueError("API密钥为空，请重新输入")

        from dashscope import Generation

        parameters = {
            "max_tokens": kwargs.get("max_new_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
            "timeout": 30
        }

        try:
            response = Generation.call(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                parameters=parameters
            )
            if response.status_code != 200:
                raise Exception(f"API调用失败：{response.message}")

            # 优先读取text字段，兼容不同响应格式
            if hasattr(response.output, 'text') and response.output.text:
                return response.output.text.strip()
            elif hasattr(response.output, 'choices') and response.output.choices:
                return response.output.choices[0].message.content.strip()
            else:
                raise Exception("API响应无有效内容")

        except Exception as e:
            logger.error(f"生成错误: {str(e)}")
            raise