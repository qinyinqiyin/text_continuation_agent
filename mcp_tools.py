"""
MCP (Model Context Protocol) 工具集成框架
支持标准化的工具调用和结果返回
"""
import json
import os
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime
from config import logger


class MCPTool(ABC):
    """MCP工具基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """返回工具的JSON Schema定义"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回标准化结果"""
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证参数是否符合schema"""
        schema = self.get_schema()
        required_params = schema.get("required", [])
        
        for param in required_params:
            if param not in params:
                return False
        
        return True


class MCPToolRegistry:
    """MCP工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
    
    def register(self, tool: MCPTool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.info(f"注册MCP工具: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
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
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 未找到"
            }
        
        if not tool.validate_params(params):
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 参数验证失败"
            }
        
        try:
            result = tool.execute(**params)
            return {
                "success": True,
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# ==================== 文件系统工具 ====================

class FilesystemMCPTool(MCPTool):
    """文件系统MCP工具：支持批量导入、导出、备份"""
    
    def __init__(self):
        super().__init__(
            name="filesystem",
            description="文件系统操作工具，支持批量导入文章、导出知识库、备份恢复"
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
                "source_path": {
                    "type": "string",
                    "description": "源路径（导入/恢复时使用）"
                },
                "target_path": {
                    "type": "string",
                    "description": "目标路径（导出/备份时使用）"
                },
                "file_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件扩展名过滤（导入时使用）",
                    "default": [".txt"]
                }
            },
            "required": ["action"]
        }
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        action = kwargs.get("action")
        
        if action == "import_directory":
            return self._import_directory(
                kwargs.get("source_path"),
                kwargs.get("file_extensions", [".txt"])
            )
        elif action == "export_knowledge_base":
            return self._export_knowledge_base(kwargs.get("target_path"))
        elif action == "backup":
            return self._backup(kwargs.get("target_path"))
        elif action == "restore":
            return self._restore(kwargs.get("source_path"))
        elif action == "list_files":
            return self._list_files(kwargs.get("source_path", "."))
        else:
            return {"error": f"不支持的操作: {action}"}
    
    def _import_directory(self, source_path: str, extensions: List[str]) -> Dict[str, Any]:
        """批量导入目录中的文件"""
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
                        
                        imported_files.append({
                            "file": file,
                            "path": file_path,
                            "size": len(content),
                            "content_preview": content[:100] + "..." if len(content) > 100 else content
                        })
                    except Exception as e:
                        failed_files.append({
                            "file": file,
                            "error": str(e)
                        })
        
        return {
            "imported_count": len(imported_files),
            "failed_count": len(failed_files),
            "imported_files": imported_files,
            "failed_files": failed_files
        }
    
    def _export_knowledge_base(self, target_path: str) -> Dict[str, Any]:
        """导出知识库到文件"""
        # 这个方法需要knowledge_base实例，将在集成时处理
        # 实际导出逻辑应该在agent中实现
        cache_file = "faiss_kb_cache.pkl"
        if not os.path.exists(cache_file):
            return {"error": "知识库缓存文件不存在"}
        
        if not target_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = f"export_kb_{timestamp}.pkl"
        
        try:
            import shutil
            shutil.copy2(cache_file, target_path)
            return {
                "success": True,
                "export_path": target_path,
                "size": os.path.getsize(target_path),
                "message": "知识库已导出"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _backup(self, target_path: str) -> Dict[str, Any]:
        """备份知识库"""
        cache_file = "faiss_kb_cache.pkl"
        if not os.path.exists(cache_file):
            return {"error": "知识库缓存文件不存在"}
        
        if not target_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = f"backup_kb_{timestamp}.pkl"
        
        try:
            import shutil
            shutil.copy2(cache_file, target_path)
            return {
                "success": True,
                "backup_path": target_path,
                "size": os.path.getsize(target_path)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _restore(self, source_path: str) -> Dict[str, Any]:
        """恢复知识库"""
        if not source_path or not os.path.exists(source_path):
            return {"error": f"备份文件不存在: {source_path}"}
        
        cache_file = "faiss_kb_cache.pkl"
        try:
            import shutil
            # 先备份当前文件
            if os.path.exists(cache_file):
                backup_current = f"{cache_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(cache_file, backup_current)
            
            # 恢复
            shutil.copy2(source_path, cache_file)
            return {
                "success": True,
                "restored_from": source_path,
                "message": "知识库已恢复，请刷新页面"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _list_files(self, source_path: str) -> Dict[str, Any]:
        """列出目录中的文件"""
        if not os.path.exists(source_path):
            return {"error": f"路径不存在: {source_path}"}
        
        files = []
        if os.path.isdir(source_path):
            for item in os.listdir(source_path):
                item_path = os.path.join(source_path, item)
                if os.path.isfile(item_path):
                    files.append({
                        "name": item,
                        "path": item_path,
                        "size": os.path.getsize(item_path),
                        "modified": datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                    })
        else:
            files.append({
                "name": os.path.basename(source_path),
                "path": source_path,
                "size": os.path.getsize(source_path),
                "modified": datetime.fromtimestamp(os.path.getmtime(source_path)).isoformat()
            })
        
        return {
            "path": source_path,
            "file_count": len(files),
            "files": files
        }


# ==================== 文本分析工具 ====================

class TextAnalysisMCPTool(MCPTool):
    """文本分析MCP工具：风格检测、质量评分、连贯性检查"""
    
    def __init__(self):
        super().__init__(
            name="text_analysis",
            description="文本分析工具，支持风格检测、质量评分、连贯性检查、重复检测"
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["style_detection", "quality_score", "coherence_check", "duplicate_detection", "sentiment_analysis"],
                    "description": "分析类型"
                },
                "text": {
                    "type": "string",
                    "description": "待分析的文本"
                },
                "reference_text": {
                    "type": "string",
                    "description": "参考文本（用于风格对比或连贯性检查）"
                },
                "style": {
                    "type": "string",
                    "enum": ["fantasy", "ancient", "sci-fi", "EasternFantasy", "Suspense"],
                    "description": "目标风格（风格检测时使用）"
                }
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
        else:
            return {"error": f"不支持的分析类型: {action}"}
    
    def _style_detection(self, text: str, target_style: Optional[str] = None) -> Dict[str, Any]:
        """风格检测"""
        style_keywords = {
            "fantasy": ["魔法", "精灵", "咒语", "奇幻", "神秘", "魔法师", "龙"],
            "ancient": ["道", "视", "奔", "忽", "俄而", "古", "雅", "典"],
            "sci-fi": ["量子", "飞船", "人工智能", "星际", "纳米", "科技", "未来"],
            "EasternFantasy": ["灵气", "修炼", "经脉", "法宝", "修仙", "境界", "宗门", "凝气", "锻气"],
            "Suspense": ["谜团", "线索", "诡异", "阴影", "秘密", "悬疑", "未知", "疑"]
        }
        
        scores = {}
        for style, keywords in style_keywords.items():
            count = sum(1 for kw in keywords if kw in text)
            scores[style] = {
                "score": count,
                "percentage": (count / len(keywords)) * 100 if keywords else 0
            }
        
        # 确定主要风格
        main_style = max(scores.items(), key=lambda x: x[1]["score"])
        
        result = {
            "text_length": len(text),
            "style_scores": scores,
            "detected_style": main_style[0],
            "confidence": main_style[1]["percentage"]
        }
        
        if target_style:
            target_score = scores.get(target_style, {}).get("percentage", 0)
            result["target_style_match"] = target_style
            result["target_style_score"] = target_score
            result["match_quality"] = "优秀" if target_score > 60 else "良好" if target_score > 30 else "需要改进"
        
        return result
    
    def _quality_score(self, text: str) -> Dict[str, Any]:
        """质量评分"""
        scores = {}
        
        # 1. 长度评分（100-5000字符为理想范围）
        length = len(text)
        if 100 <= length <= 5000:
            length_score = 100
        elif length < 100:
            length_score = (length / 100) * 100
        else:
            length_score = max(0, 100 - (length - 5000) / 50)
        scores["length"] = round(length_score, 2)
        
        # 2. 段落结构评分
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraph_score = min(100, len(paragraphs) * 20) if paragraphs else 0
        scores["paragraph_structure"] = round(paragraph_score, 2)
        
        # 3. 句子多样性评分（基于标点符号）
        sentences = text.replace('。', '。').replace('！', '！').replace('？', '？')
        sentence_count = len([s for s in sentences.split('。') if s.strip()])
        diversity_score = min(100, sentence_count * 5)
        scores["sentence_diversity"] = round(diversity_score, 2)
        
        # 4. 词汇丰富度（简单计算：唯一字符比例）
        unique_chars = len(set(text.replace(' ', '').replace('\n', '')))
        vocab_score = min(100, (unique_chars / len(text.replace(' ', '').replace('\n', ''))) * 200) if text else 0
        scores["vocabulary_richness"] = round(vocab_score, 2)
        
        # 总体评分
        overall_score = sum(scores.values()) / len(scores)
        
        return {
            "overall_score": round(overall_score, 2),
            "scores": scores,
            "quality_level": "优秀" if overall_score >= 80 else "良好" if overall_score >= 60 else "需要改进",
            "text_length": length,
            "paragraph_count": len(paragraphs),
            "sentence_count": sentence_count
        }
    
    def _coherence_check(self, text: str, reference_text: str) -> Dict[str, Any]:
        """连贯性检查"""
        if not reference_text:
            return {"error": "需要提供参考文本"}
        
        # 简单的连贯性检查：检查人物名称、关键名词是否一致
        import re
        
        # 提取参考文本中的主要名词（简单实现）
        ref_nouns = set(re.findall(r'[\u4e00-\u9fa5]{2,}', reference_text[-500:]))  # 取最后500字符
        text_nouns = set(re.findall(r'[\u4e00-\u9fa5]{2,}', text[:500]))  # 取前500字符
        
        common_nouns = ref_nouns & text_nouns
        coherence_score = (len(common_nouns) / max(len(ref_nouns), 1)) * 100
        
        return {
            "coherence_score": round(coherence_score, 2),
            "common_elements": len(common_nouns),
            "reference_elements": len(ref_nouns),
            "text_elements": len(text_nouns),
            "coherence_level": "优秀" if coherence_score >= 70 else "良好" if coherence_score >= 40 else "需要改进"
        }
    
    def _duplicate_detection(self, text: str, reference_text: str) -> Dict[str, Any]:
        """重复内容检测"""
        if not reference_text:
            return {"error": "需要提供参考文本"}
        
        # 简单的重复检测：计算最长公共子串
        def longest_common_substring(s1: str, s2: str) -> int:
            m, n = len(s1), len(s2)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            max_len = 0
            
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if s1[i-1] == s2[j-1]:
                        dp[i][j] = dp[i-1][j-1] + 1
                        max_len = max(max_len, dp[i][j])
                    else:
                        dp[i][j] = 0
            
            return max_len
        
        max_common = longest_common_substring(text, reference_text)
        duplicate_ratio = (max_common / max(len(text), len(reference_text))) * 100 if text or reference_text else 0
        
        return {
            "max_common_length": max_common,
            "duplicate_ratio": round(duplicate_ratio, 2),
            "has_duplicate": duplicate_ratio > 20,
            "warning": "检测到较多重复内容" if duplicate_ratio > 20 else "重复内容在可接受范围内"
        }
    
    def _sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """情感分析（简化版）"""
        positive_words = ["好", "美", "快乐", "成功", "胜利", "希望", "爱", "幸福", "温暖"]
        negative_words = ["坏", "痛苦", "失败", "绝望", "恐惧", "悲伤", "愤怒", "黑暗"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        total_score = positive_count - negative_count
        
        if total_score > 2:
            sentiment = "积极"
        elif total_score < -2:
            sentiment = "消极"
        else:
            sentiment = "中性"
        
        return {
            "sentiment": sentiment,
            "positive_score": positive_count,
            "negative_score": negative_count,
            "overall_score": total_score
        }


# ==================== 工具注册 ====================

def create_mcp_registry() -> MCPToolRegistry:
    """创建并注册所有MCP工具"""
    registry = MCPToolRegistry()
    
    # 注册文件系统工具
    registry.register(FilesystemMCPTool())
    
    # 注册文本分析工具
    registry.register(TextAnalysisMCPTool())
    
    return registry

