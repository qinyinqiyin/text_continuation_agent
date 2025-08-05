from base_classes import BaseModel, BaseStrategy
from knowledge_base import FAISSKnowledgeBase
from config import logger
from modelscope.preprocessors.templates.tools_prompt import tools_prompt
from tools import (
    PlotConflictDetectorTool, HistoryRetrievalTool, PlotOutlinerTool
)

class TextContinuationAgent:
    def __init__(self, model: BaseModel, strategy: BaseStrategy):
        self.model = model
        self.strategy = strategy
        self.history_memory = []

    def add_memory(self, input_data: dict, output: str):
        self.history_memory.append({"input": input_data, "output": output})

    def run(self, input_data: dict, **kwargs) -> str:
        prompt = self.strategy.format_prompt(input_data)
        logger.info(f"生成prompt：{prompt[:100]}...")
        output = self.model.generate(prompt,** kwargs)
        processed_output = self.strategy.post_process(output)
        self.add_memory(input_data, processed_output)
        return processed_output


class RAGTextContinuationAgent(TextContinuationAgent):
    def __init__(self, model: BaseModel, strategy: BaseStrategy, knowledge_base: FAISSKnowledgeBase):
        super().__init__(model, strategy)
        self.kb = knowledge_base
        self.tools = {
            "PlotOutliner": PlotOutlinerTool(knowledge_base),
            "PlotConflictDetector": PlotConflictDetectorTool(knowledge_base),
            "HistoryRetrieval": HistoryRetrievalTool(knowledge_base),
        }
        # 同步历史记录
        self.tools["HistoryRetrieval"].set_history(self.history_memory)

    def _get_tool_prompts(self, input_data: dict) -> str:
        """调用所有工具，生成prompt片段"""
        tool_fragments = []
        # 按需调用工具（可配置工具列表）
        for tool_name in ["PlotOutliner", "PlotConflictDetector"]:
            if tool_name in self.tools:
                # 动态传参（从input_data提取）
                params = {
                    "context": input_data["前文"],
                    "depth": 3  # 可配置
                } if tool_name == "PlotOutliner" else {
                    "content": input_data["前文"]
                }
                fragment = self.tools[tool_name].generate_prompt_fragment(**params)
                tool_fragments.append(fragment)
        return "\n".join(tool_fragments)

    def run_with_rag(self, input_data: dict, **kwargs) -> str:
        # 1. 生成工具辅助提示
        tool_prompts = self._get_tool_prompts(input_data)

        # 2. 构建完整prompt
        original_prompt = self.strategy.format_prompt(input_data)
        final_prompt = f"""
        {original_prompt}

        【工具辅助提示】
        {tool_prompts}

        要求：严格参考工具提示，续写内容需融入大纲/避免冲突/保持连贯
        """

        # 3. AI生成
        output = self.model.generate(final_prompt, **kwargs)
        processed_output = self.strategy.post_process(output)
        self.add_memory(input_data, processed_output)
        return processed_output