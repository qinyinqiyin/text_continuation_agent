import json
from config import logger
from transformers import pipeline, AutoTokenizer
import numpy as np
from typing import Dict, List, Optional


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

    def generate_prompt_fragment(self, context: str, current_text: str, depth: int = 3) -> str:
        try:
            relevant_settings = self.kb.search_relevant_settings(context)
            outline_settings = [
                s for s, meta in zip(relevant_settings, self.kb.metadatas)
                if meta.get("type") == "文章大纲"
            ]

            if not outline_settings:
                # 无大纲时正常生成脉络
                setting_prompt = "\n设定参考：\n" + "\n".join(relevant_settings) if relevant_settings else ""
                return f"""
                请基于以下前文和设定，生成{depth}层文章脉络并续写：
                前文：{context}
                {setting_prompt}
                要求：包含冲突、伏笔、角色成长
                """
            else:
                # 有大纲时，合并阶段判断与续写提示
                outline_prompt = "\n文章大纲：\n" + "\n".join(outline_settings)
                return f"""
                请基于以下信息完成续写：
                1. 先自动判断当前文本处于文章大纲的哪个阶段（无需单独说明，直接体现在续写中）；
                2. 严格按照大纲的阶段内容续写，处于哪个阶段就按照这个阶段的背景写，不要涉及其他阶段，确保情节连贯。
                3. 你的目标是写长故事，生成的文本需要多描写，多刻画，多伏笔
                文章大纲：{outline_prompt}
                当前文本：{current_text}
                前文参考：{context}

                要求：
                - 续写内容自然融入阶段判断结果（无需显式标注阶段）；
                - 包含冲突、伏笔或角色成长，风格与前文一致。
                """
        except Exception as e:
            return f"【大纲工具异常】：{str(e)}"

# 冲突检测工具：生成风险提示
class PlotConflictDetectorTool(BaseToolForPrompt):
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def generate_prompt_fragment(self, content: str) -> str:
        try:
            # 优化：快速检查，只检查情节限制类型
            conflicts = []
            for doc, meta in self.kb.get_all_settings():
                if meta.get("type") == "情节限制" and "不能" in doc:
                    # 简化检测：检查限制内容的关键词是否在前文中出现
                    restriction = doc.split("不能")[-1].strip()[:20]  # 取限制内容的前20字符
                    if restriction and any(keyword in content for keyword in restriction.split()[:3]):
                        conflicts.append(f"⚠️ 可能违反限制：{doc[:60]}...")
                        if len(conflicts) >= 2:  # 最多2个冲突提示
                            break
            if conflicts:
                return "【冲突检查】\n" + "\n".join(conflicts)
            return ""  # 无冲突时返回空，减少prompt长度
        except Exception as e:
            logger.warning(f"冲突检测异常：{str(e)}")
            return ""  # 异常时不阻塞


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

class LongContextProcessorTool(BaseToolForPrompt):
    def __init__(self, model_max_tokens: int = 8192, reserve_ratio: float = 0.8):
        """
        初始化长文本处理器
        :param model_max_tokens: 模型支持的最大tokens数（如qwen-turbo为8192）
        :param reserve_ratio: 为续写内容预留的比例（默认80%用于前文，20%用于生成）
        """
        self.model_max_tokens = model_max_tokens
        self.reserve_tokens = int(model_max_tokens * reserve_ratio)  # 实际可用的前文tokens
        self.tokenizer = AutoTokenizer.from_pretrained("bert-base-chinese")  # 用于token计数

        # 初始化NLP工具（关键信息提取和摘要）
        self.ner_pipeline = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english",
                                     aggregation_strategy="average")
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.tokenizer.tokenize(text))

    def extract_key_info(self, text: str) -> Dict[str, List[str]]:
        """提取文本中的关键信息（人物、地点、事件）"""
        # 提取命名实体
        entities = self.ner_pipeline(text)
        key_entities = {
            "person": [],
            "location": [],
            "organization": []
        }
        for ent in entities:
            if ent["entity_group"].lower() == "person":
                key_entities["person"].append(ent["word"])
            elif ent["entity_group"].lower() in ["location", "geo"]:
                key_entities["location"].append(ent["word"])

        # 简单提取核心事件（取前3句和后3句）
        sentences = text.split("。")
        core_event = "。".join(sentences[:3] + sentences[-3:]) if len(sentences) > 6 else text

        return {
            "entities": key_entities,
            "core_event": core_event
        }

    def summarize_text(self, text: str, max_length: int = 300) -> str:
        """生成文本摘要"""
        if len(text) < max_length:
            return text
        summary = self.summarizer(
            text,
            max_length=max_length,
            min_length=100,
            do_sample=False
        )
        return summary[0]["summary_text"]

    def sliding_window_truncate(self, text: str, window_size: Optional[int] = None) -> str:
        """
        滑动窗口截断：保留最近的window_size个token
        :param window_size: 窗口大小，默认使用reserve_tokens
        """
        window_size = window_size or self.reserve_tokens
        tokens = self.tokenizer.tokenize(text)
        if len(tokens) <= window_size:
            return text
        # 截断并还原为文本
        truncated_tokens = tokens[-window_size:]
        return self.tokenizer.convert_tokens_to_string(truncated_tokens)

    def process_long_context(self, text: str, strategy: str = "hybrid") -> str:
        """
        处理长文本的主方法
        :param text: 输入的长文本（前文）
        :param strategy: 处理策略
                        - "truncate": 仅滑动窗口截断
                        - "summary": 仅生成摘要
                        - "hybrid": 混合策略（关键信息+最近窗口+摘要）
        :return: 处理后的适合模型输入的文本
        """
        text_tokens = self.count_tokens(text)

        # 如果文本长度在可接受范围内，直接返回
        if text_tokens <= self.reserve_tokens:
            return text

        # 策略1：仅滑动窗口截断
        if strategy == "truncate":
            return self.sliding_window_truncate(text)

        # 策略2：仅生成摘要
        if strategy == "summary":
            return self.summarize_text(text, max_length=int(self.reserve_tokens * 0.8))  # 预留20%token

        # 策略3：混合策略（默认）
        key_info = self.extract_key_info(text)
        recent_context = self.sliding_window_truncate(text, window_size=int(self.reserve_tokens * 0.5))  # 最近50%token
        summary = self.summarize_text(text, max_length=int(self.reserve_tokens * 0.3))  # 摘要30%token

        # 组合结果（关键信息+摘要+最近上下文）
        combined = (
            f"【核心信息】：人物={key_info['entities']['person']}，地点={key_info['entities']['location']}\n"
            f"【故事概要】：{summary}\n"
            f"【最近情节】：{recent_context}"
        )

        # 最终检查长度，确保不超过限制
        if self.count_tokens(combined) > self.reserve_tokens:
            return self.sliding_window_truncate(combined)
        return combined



