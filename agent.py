from base_classes import BaseModel, BaseStrategy
from knowledge_base import FAISSKnowledgeBase
from config import logger
from tools import (
    PlotConflictDetectorTool, HistoryRetrievalTool
)
from mcp_tools import MCPToolRegistry, create_mcp_registry

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
    def __init__(self, model: BaseModel, strategy: BaseStrategy, knowledge_base):
        super().__init__(model, strategy)
        self.kb = knowledge_base
        self.tools = {
            "PlotConflictDetector": PlotConflictDetectorTool(knowledge_base),
            "HistoryRetrieval": HistoryRetrievalTool(knowledge_base),
            # 移除PlotOutliner工具
            # 移除LongContextProcessorTool以提升速度（避免加载大型NLP模型）
        }
        # 同步历史记录
        self.tools["HistoryRetrieval"].set_history(self.history_memory)
        
        # 初始化MCP工具注册表
        self.mcp_registry = create_mcp_registry()

    def _get_tool_prompts(self, input_data: dict) -> str:
        """调用所有工具，生成prompt片段"""
        tool_fragments = []

        # 只调用冲突检测工具
        if "PlotConflictDetector" in self.tools:
            params = {"content": input_data["前文"]}
            fragment = self.tools["PlotConflictDetector"].generate_prompt_fragment(**params)
            if fragment.strip():  # 只添加非空片段
                tool_fragments.append(fragment)
        
        return "\n".join(tool_fragments) if tool_fragments else ""

    def run_with_rag(self, input_data: dict, **kwargs) -> str:
        # 1. 生成工具辅助提示
        tool_prompts = self._get_tool_prompts(input_data)

        # 2. 构建完整prompt（优化：如果工具提示为空，则不添加）
        original_prompt = self.strategy.format_prompt(input_data)
        
        if tool_prompts.strip():
            final_prompt = f"""{original_prompt}

【工具辅助提示】
{tool_prompts}

要求：严格参考工具提示，续写内容需融入大纲/避免冲突/与前文保持连贯
"""
        else:
            final_prompt = original_prompt

        # 3. AI生成
        output = self.model.generate(final_prompt, **kwargs)
        processed_output = self.strategy.post_process(output)
        self.add_memory(input_data, processed_output)
        return processed_output
    
    def call_mcp_tool(self, tool_name: str, params: dict) -> dict:
        """调用MCP工具"""
        return self.mcp_registry.execute_tool(tool_name, params)
    
    def analyze_text_quality(self, text: str, reference_text: str = "", style: str = None) -> dict:
        """使用MCP文本分析工具分析文本质量"""
        results = {}
        
        # 质量评分
        quality_result = self.call_mcp_tool("text_analysis", {
            "action": "quality_score",
            "text": text
        })
        if quality_result.get("success"):
            results["quality"] = quality_result["result"]
        
        # 风格检测
        if style:
            style_result = self.call_mcp_tool("text_analysis", {
                "action": "style_detection",
                "text": text,
                "style": style
            })
            if style_result.get("success"):
                results["style"] = style_result["result"]
        
        # 连贯性检查（如果有参考文本）
        if reference_text:
            coherence_result = self.call_mcp_tool("text_analysis", {
                "action": "coherence_check",
                "text": text,
                "reference_text": reference_text
            })
            if coherence_result.get("success"):
                results["coherence"] = coherence_result["result"]
            
            # 重复检测
            duplicate_result = self.call_mcp_tool("text_analysis", {
                "action": "duplicate_detection",
                "text": text,
                "reference_text": reference_text
            })
            if duplicate_result.get("success"):
                results["duplicate"] = duplicate_result["result"]
        
        return results