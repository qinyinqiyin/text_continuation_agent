from typing import List, Dict
import json
from config import logger


class BaseTool:
    def get_description(self) -> str:
        """返回工具功能描述（供模型理解如何使用）"""
        raise NotImplementedError("子类必须实现get_description方法")

    def run(self, **kwargs) -> str:
        """工具执行逻辑（返回处理结果）"""
        raise NotImplementedError("子类必须实现run方法")


class BaseToolForPrompt(BaseTool):
    """工具基类：专为生成AI参考提示设计"""

    def generate_prompt_fragment(self, **kwargs) -> str:
        """返回可直接注入prompt的文本片段"""
        raise NotImplementedError

    # 兼容原有run方法（可选）
    def run(self, **kwargs) -> str:
        return self.generate_prompt_fragment(**kwargs)


# 文章脉络工具：生成大纲式提示
class PlotOutlinerTool(BaseToolForPrompt):
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def generate_prompt_fragment(self, context: str, depth: int = 3) -> str:
        try:
            relevant_settings = self.kb.search_relevant_settings(context)
            setting_prompt = "\n设定参考：\n" + "\n".join(relevant_settings) if relevant_settings else ""

            # 直接生成给AI的提示片段
            return f"""
            请基于以下前文和设定，生成{depth}层文章脉络（用于续写参考）：
            前文：{context}
            {setting_prompt}
            要求：包含冲突、伏笔、角色成长，用有序列表呈现
            """
        except Exception as e:
            return f"【大纲工具异常】：{str(e)}"


# 冲突检测工具：生成风险提示
class PlotConflictDetectorTool(BaseToolForPrompt):
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def generate_prompt_fragment(self, content: str) -> str:
        try:
            conflicts = []
            for doc, meta in self.kb.get_all_settings():
                if "不能" in doc and "能" in content:
                    conflicts.append(f"可能冲突：{meta['type']} - {doc}")
            if conflicts:
                return "\n".join([
                    "【冲突检查】发现潜在设定矛盾，请调整续写内容：",
                    *conflicts
                ])
            return "【冲突检查】未发现设定矛盾，可安全续写"
        except Exception as e:
            return f"【冲突检测异常】：{str(e)}"


# 历史回溯工具：生成上下文提示
class HistoryRetrievalTool(BaseToolForPrompt):
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.history = []

    def set_history(self, history: List[Dict]):
        self.history = history

    def generate_prompt_fragment(self, query: str, limit: int = 3) -> str:
        try:
            matched = [
                f"历史输入：{h['input']['前文'][:30]}...\n历史输出：{h['output'][:50]}..."
                for h in self.history
                if query in h["input"].get("前文", "")
            ]
            if matched:
                return f"""
                【历史参考】过往续写记录（供保持连贯）：
                {''.join(matched[:limit])}
                要求：续写风格和设定需与历史一致
                """
            return "【历史参考】无匹配记录，可自由发挥"
        except Exception as e:
            return f"【历史回溯异常】：{str(e)}"