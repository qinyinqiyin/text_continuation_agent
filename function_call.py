"""
Function Call 工具集成框架
支持标准化的函数调用：注册、发现、执行
"""
import os
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime
from config import logger


class FunctionCallTool(ABC):
    """可调用工具基类"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """返回工具的 JSON Schema 定义"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回标准化结果"""
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数是否符合 schema"""
        schema = self.get_schema()
        required_params = schema.get("required", [])
        for param in required_params:
            if param not in params:
                return False
        return True


class FunctionCallRegistry:
    """函数调用注册表"""

    def __init__(self):
        self.tools: Dict[str, FunctionCallTool] = {}

    def register(self, tool: FunctionCallTool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"注册 Function Call 工具: {tool.name}")

    def get_tool(self, name: str) -> Optional[FunctionCallTool]:
        """获取工具"""
        return self.tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.get_schema()
            }
            for tool in self.tools.values()
        ]

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"工具 '{tool_name}' 未找到"}
        if not tool.validate_params(params):
            return {"success": False, "error": f"工具 '{tool_name}' 参数验证失败"}
        try:
            result = tool.execute(**params)
            return {"success": True, "tool": tool_name, "result": result}
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {str(e)}")
            return {"success": False, "error": str(e)}


# ==================== 文件系统工具 ====================

class FilesystemTool(FunctionCallTool):
    """文件系统工具：批量导入、导出、备份"""

    def __init__(self):
        super().__init__(
            name="filesystem",
            description="文件系统操作，支持批量导入、导出知识库、备份恢复"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["import_directory", "export_knowledge_base", "backup", "restore", "list_files"],
                    "description": "操作类型"
                },
                "source_path": {"type": "string", "description": "源路径"},
                "target_path": {"type": "string", "description": "目标路径"},
                "file_extensions": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["action"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        action = kwargs.get("action")
        if action == "import_directory":
            return self._import_directory(kwargs.get("source_path"), kwargs.get("file_extensions", [".txt"]))
        elif action == "export_knowledge_base":
            return self._export_knowledge_base(kwargs.get("target_path"))
        elif action == "backup":
            return self._backup(kwargs.get("target_path"))
        elif action == "restore":
            return self._restore(kwargs.get("source_path"))
        elif action == "list_files":
            return self._list_files(kwargs.get("source_path", "."))
        return {"error": f"不支持的操作: {action}"}

    def _import_directory(self, source_path: str, extensions: List[str]) -> Dict[str, Any]:
        if not source_path or not os.path.exists(source_path):
            return {"error": f"路径不存在: {source_path}"}
        if not os.path.isdir(source_path):
            return {"error": f"不是目录: {source_path}"}
        imported_files = []
        failed_files = []
        for root, dirs, files in os.walk(source_path):
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)
                if ext.lower() in extensions:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        imported_files.append({"file": file, "path": file_path, "size": len(content),
                            "content_preview": content[:100] + "..." if len(content) > 100 else content})
                    except Exception as e:
                        failed_files.append({"file": file, "error": str(e)})
        return {"imported_count": len(imported_files), "failed_count": len(failed_files),
                "imported_files": imported_files, "failed_files": failed_files}

    def _export_knowledge_base(self, target_path: str) -> Dict[str, Any]:
        cache_file = "faiss_kb_cache.pkl"
        if not os.path.exists(cache_file):
            return {"error": "知识库缓存文件不存在"}
        if not target_path:
            target_path = f"export_kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        try:
            import shutil
            shutil.copy2(cache_file, target_path)
            return {"success": True, "export_path": target_path, "size": os.path.getsize(target_path), "message": "知识库已导出"}
        except Exception as e:
            return {"error": str(e)}

    def _backup(self, target_path: str) -> Dict[str, Any]:
        cache_file = "faiss_kb_cache.pkl"
        if not os.path.exists(cache_file):
            return {"error": "知识库缓存文件不存在"}
        if not target_path:
            target_path = f"backup_kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        try:
            import shutil
            shutil.copy2(cache_file, target_path)
            return {"success": True, "backup_path": target_path, "size": os.path.getsize(target_path)}
        except Exception as e:
            return {"error": str(e)}

    def _restore(self, source_path: str) -> Dict[str, Any]:
        if not source_path or not os.path.exists(source_path):
            return {"error": f"备份文件不存在: {source_path}"}
        cache_file = "faiss_kb_cache.pkl"
        try:
            import shutil
            if os.path.exists(cache_file):
                backup_current = f"{cache_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(cache_file, backup_current)
            shutil.copy2(source_path, cache_file)
            return {"success": True, "restored_from": source_path, "message": "知识库已恢复，请刷新页面"}
        except Exception as e:
            return {"error": str(e)}

    def _list_files(self, source_path: str) -> Dict[str, Any]:
        if not os.path.exists(source_path):
            return {"error": f"路径不存在: {source_path}"}
        files = []
        if os.path.isdir(source_path):
            for item in os.listdir(source_path):
                item_path = os.path.join(source_path, item)
                if os.path.isfile(item_path):
                    files.append({"name": item, "path": item_path, "size": os.path.getsize(item_path),
                        "modified": datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()})
        else:
            files.append({"name": os.path.basename(source_path), "path": source_path, "size": os.path.getsize(source_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(source_path)).isoformat()})
        return {"path": source_path, "file_count": len(files), "files": files}


# ==================== 文本分析工具 ====================

class TextAnalysisTool(FunctionCallTool):
    """文本分析工具：风格检测、质量评分、连贯性检查"""

    def __init__(self):
        super().__init__(name="text_analysis", description="文本分析：风格检测、质量评分、连贯性检查、重复检测")

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["style_detection", "quality_score", "coherence_check", "duplicate_detection", "sentiment_analysis"]},
                "text": {"type": "string"},
                "reference_text": {"type": "string"},
                "style": {"type": "string", "enum": ["fantasy", "ancient", "sci-fi", "EasternFantasy", "Suspense"]}
            },
            "required": ["action", "text"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        action = kwargs.get("action")
        text = kwargs.get("text", "")
        if not text:
            return {"error": "文本不能为空"}
        if action == "style_detection":
            return self._style_detection(text, kwargs.get("style"))
        elif action == "quality_score":
            return self._quality_score(text)
        elif action == "coherence_check":
            return self._coherence_check(text, kwargs.get("reference_text", ""))
        elif action == "duplicate_detection":
            return self._duplicate_detection(text, kwargs.get("reference_text", ""))
        elif action == "sentiment_analysis":
            return self._sentiment_analysis(text)
        return {"error": f"不支持的分析类型: {action}"}

    def _style_detection(self, text: str, target_style: Optional[str] = None) -> Dict[str, Any]:
        style_keywords = {
            "fantasy": ["魔法", "精灵", "咒语", "奇幻", "神秘", "魔法师", "龙"],
            "ancient": ["道", "视", "奔", "忽", "俄而", "古", "雅", "典"],
            "sci-fi": ["量子", "飞船", "人工智能", "星际", "纳米", "科技", "未来"],
            "EasternFantasy": ["灵气", "修炼", "经脉", "法宝", "修仙", "境界", "宗门", "凝气", "锻气"],
            "Suspense": ["谜团", "线索", "诡异", "阴影", "秘密", "悬疑", "未知", "疑"]
        }
        scores = {s: {"score": sum(1 for kw in kws if kw in text), "percentage": 0} for s, kws in style_keywords.items()}
        for s, kws in style_keywords.items():
            if kws:
                scores[s]["percentage"] = (scores[s]["score"] / len(kws)) * 100
        main_style = max(scores.items(), key=lambda x: x[1]["score"])
        result = {"text_length": len(text), "style_scores": scores, "detected_style": main_style[0], "confidence": main_style[1]["percentage"]}
        if target_style:
            ts = scores.get(target_style, {}).get("percentage", 0)
            result["target_style_match"] = target_style
            result["target_style_score"] = ts
            result["match_quality"] = "优秀" if ts > 60 else "良好" if ts > 30 else "需要改进"
        return result

    def _quality_score(self, text: str) -> Dict[str, Any]:
        length = len(text)
        length_score = 100 if 100 <= length <= 5000 else (length / 100) * 100 if length < 100 else max(0, 100 - (length - 5000) / 50)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        sentence_count = len([s for s in text.replace('！', '。').replace('？', '。').split('。') if s.strip()])
        scores = {
            "length": round(length_score, 2),
            "paragraph_structure": round(min(100, len(paragraphs) * 20) if paragraphs else 0, 2),
            "sentence_diversity": round(min(100, sentence_count * 5), 2),
            "vocabulary_richness": round(min(100, (len(set(text.replace(' ', '').replace('\n', ''))) / max(len(text.replace(' ', '').replace('\n', '')), 1)) * 200), 2) if text else 0
        }
        overall = sum(scores.values()) / len(scores)
        return {"overall_score": round(overall, 2), "scores": scores, "quality_level": "优秀" if overall >= 80 else "良好" if overall >= 60 else "需要改进",
                "text_length": length, "paragraph_count": len(paragraphs), "sentence_count": sentence_count}

    def _coherence_check(self, text: str, reference_text: str) -> Dict[str, Any]:
        if not reference_text:
            return {"error": "需要提供参考文本"}
        import re
        ref_nouns = set(re.findall(r'[\u4e00-\u9fa5]{2,}', reference_text[-500:]))
        text_nouns = set(re.findall(r'[\u4e00-\u9fa5]{2,}', text[:500]))
        common = ref_nouns & text_nouns
        score = (len(common) / max(len(ref_nouns), 1)) * 100
        return {"coherence_score": round(score, 2), "common_elements": len(common), "reference_elements": len(ref_nouns), "text_elements": len(text_nouns),
                "coherence_level": "优秀" if score >= 70 else "良好" if score >= 40 else "需要改进"}

    def _duplicate_detection(self, text: str, reference_text: str) -> Dict[str, Any]:
        if not reference_text:
            return {"error": "需要提供参考文本"}
        def lcs(s1, s2):
            m, n = len(s1), len(s2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            mx = 0
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i-1] == s2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                        mx = max(mx, dp[i][j])
            return mx
        max_common = lcs(text, reference_text)
        ratio = (max_common / max(len(text), len(reference_text))) * 100 if text or reference_text else 0
        return {"max_common_length": max_common, "duplicate_ratio": round(ratio, 2), "has_duplicate": ratio > 20,
                "warning": "检测到较多重复内容" if ratio > 20 else "重复内容在可接受范围内"}

    def _sentiment_analysis(self, text: str) -> Dict[str, Any]:
        pos = ["好", "美", "快乐", "成功", "胜利", "希望", "爱", "幸福", "温暖"]
        neg = ["坏", "痛苦", "失败", "绝望", "恐惧", "悲伤", "愤怒", "黑暗"]
        pc = sum(1 for w in pos if w in text)
        nc = sum(1 for w in neg if w in text)
        total = pc - nc
        sentiment = "积极" if total > 2 else "消极" if total < -2 else "中性"
        return {"sentiment": sentiment, "positive_score": pc, "negative_score": nc, "overall_score": total}


# ==================== 故事创作工具 ====================

class StoryToolsAdapter(FunctionCallTool):
    """故事创作工具：封装 story_tools 的 5 个核心方法"""

    def __init__(self, story_state_manager=None):
        super().__init__(name="story_tools", description="故事创作：剧情状态、设定检索、一致性检查")
        self.story_manager = story_state_manager

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"tool_name": {"type": "string", "enum": ["get_story_state", "update_story_state", "check_consistency", "search_lore", "search_character"]}, "params": {"type": "object"}},
            "required": ["tool_name"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        if not self.story_manager:
            return {"error": "故事状态管理器未初始化"}
        tool_name = kwargs.get("tool_name")
        params = kwargs.get("params", {})
        tool_map = {
            "get_story_state": self.story_manager.get_story_state,
            "update_story_state": lambda: self.story_manager.update_story_state(params),
            "check_consistency": lambda: self.story_manager.check_consistency(params.get("draft", ""), params.get("settings")),
            "search_lore": lambda: self.story_manager.search_lore(params.get("query", ""), params.get("top_k", 5)),
            "search_character": lambda: self.story_manager.search_character(params.get("name", ""))
        }
        if tool_name not in tool_map:
            return {"error": f"未知的工具名称: {tool_name}"}
        try:
            return tool_map[tool_name]()
        except Exception as e:
            logger.error(f"执行故事工具 {tool_name} 失败: {str(e)}")
            return {"success": False, "error": str(e)}


# ==================== 工厂函数 ====================

def create_function_registry(story_state_manager=None) -> FunctionCallRegistry:
    """创建并注册所有 Function Call 工具"""
    registry = FunctionCallRegistry()
    registry.register(FilesystemTool())
    registry.register(TextAnalysisTool())
    if story_state_manager:
        registry.register(StoryToolsAdapter(story_state_manager))
    return registry
