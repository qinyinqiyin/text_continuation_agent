"""统一故事创作工具：冲突检测（生成 prompt 片段）+ 状态管理 + 设定检索"""
import json
import os
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

from config import logger


class StoryTools:
    """
    故事创作工具集合：
    - generate_prompt_fragment: 续写时自动注入冲突检测片段
    - get_story_state / update_story_state: 剧情状态管理
    - check_consistency: 一致性检查
    - search_lore / search_character: 设定检索
    """

    def __init__(self, knowledge_base, state_file: str = "story_state.json"):
        self.kb = knowledge_base
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载剧情状态失败: {e}")
        return {
            "characters": [], "locations": [], "goals": [], "foreshadowing": [],
            "conflicts": [], "timeline": [], "last_updated": None
        }

    def _save_state(self):
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存剧情状态失败: {e}")

    # ---------- 续写时自动调用：生成 prompt 片段 ----------
    def generate_prompt_fragment(self, content: str) -> str:
        """冲突检测：检查前文是否违反情节限制，返回可注入 prompt 的片段"""
        try:
            conflicts = []
            for doc, meta in self.kb.get_all_settings():
                if meta.get("type") == "情节限制" and "不能" in doc:
                    restriction = doc.split("不能")[-1].strip()[:20]
                    if restriction and any(kw in content for kw in restriction.split()[:3]):
                        conflicts.append(f"⚠️ 可能违反限制：{doc[:60]}...")
                        if len(conflicts) >= 2:
                            break
            if conflicts:
                return "【冲突检查】\n" + "\n".join(conflicts)
            return ""
        except Exception as e:
            logger.warning(f"冲突检测异常：{str(e)}")
            return ""

    # ---------- API / Function Call 调用：状态管理 ----------
    def get_story_state(self) -> Dict[str, Any]:
        """获取当前剧情状态"""
        return {
            "success": True,
            "result": {
                "characters": self.state.get("characters", []),
                "locations": self.state.get("locations", []),
                "goals": self.state.get("goals", []),
                "foreshadowing": self.state.get("foreshadowing", []),
                "conflicts": self.state.get("conflicts", []),
                "timeline": self.state.get("timeline", []),
                "last_updated": self.state.get("last_updated")
            }
        }

    def update_story_state(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """更新剧情状态"""
        try:
            for key, value in changes.items():
                if key in ["characters", "locations", "goals", "foreshadowing", "conflicts", "timeline"]:
                    if isinstance(value, list):
                        self.state[key] = value
                    elif isinstance(value, dict) and "action" in value:
                        action = value["action"]
                        if action == "append" and key in self.state:
                            self.state[key].extend(value.get("items", []))
                        elif action == "remove" and key in self.state:
                            self.state[key] = [x for x in self.state[key] if x not in value.get("items", [])]
            self._save_state()
            return {"success": True, "message": "剧情状态已更新"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_consistency(self, draft: str, settings: Optional[List[str]] = None) -> Dict[str, Any]:
        """检查一致性与情节限制"""
        violations, inconsistencies, suggestions = [], [], []
        for doc, meta in self.kb.get_all_settings():
            if meta.get("type") == "情节限制" and ("不能" in doc or "禁止" in doc):
                for keyword in re.findall(r'不能[^。]*|禁止[^。]*', doc):
                    if keyword in draft:
                        violations.append({"type": "情节限制", "content": doc[:100], "violation": keyword[:50]})

        if violations:
            suggestions.append("请检查是否违反了已设定的情节限制")

        return {
            "success": True,
            "result": {
                "violates_rules": len(violations) > 0,
                "violations": violations,
                "inconsistencies": inconsistencies,
                "suggestions": suggestions if suggestions else ["文本一致性检查通过"]
            }
        }

    def search_lore(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """检索世界观设定"""
        try:
            results = self.kb.search_relevant_settings(query, top_n=top_k)
            all_settings = self.kb.get_all_settings()
            lore_results = []
            for doc in results:
                for s, meta in all_settings:
                    if s == doc and meta.get("type") in ["世界观设定", "关键物品设定"]:
                        lore_results.append({"content": doc, "type": meta.get("type", "未知")})
                        break
            return {"success": True, "result": {"query": query, "count": len(lore_results), "results": lore_results}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_character(self, name: str) -> Dict[str, Any]:
        """人物档案检索"""
        try:
            results = self.kb.search_relevant_settings(name, top_n=5)
            all_settings = self.kb.get_all_settings()
            character_info = None
            for doc in results:
                for s, meta in all_settings:
                    if s == doc and meta.get("type") == "角色设定" and name in doc:
                        character_info = {"name": name, "content": doc, "from_kb": True}
                        break
            if not character_info:
                for char in self.state.get("characters", []):
                    if isinstance(char, dict) and char.get("name") == name:
                        character_info = dict(char)
                        character_info["from_state"] = True
                        break
            return {"success": True, "result": character_info} if character_info else {"success": False, "error": f"未找到角色：{name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
