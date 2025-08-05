from base_classes import BaseStrategy
from config import logger

class FantasyStrategy(BaseStrategy):
    def format_prompt(self, input_data: dict) -> str:
        return (
            f"请续写以下奇幻片段，保持神秘魔法氛围：\n"
            f"前文：{input_data['前文']}\n"
            f"要求：{input_data['要求']}\n"
            f"续写内容："
        )

    def post_process(self, output: str) -> str:
        fantasy_keywords = ["魔法", "精灵", "咒语", "奇幻", "神秘"]
        if not any(kw in output for kw in fantasy_keywords):
            logger.warning("续写内容可能缺少奇幻元素")
            return output + " 周围的魔法光环突然闪烁，古老的咒语在空气中回响。"
        return output

class AncientStyleStrategy(BaseStrategy):
    def format_prompt(self, input_data: dict) -> str:
        return (
            f"请续写以下古风片段，语言典雅：\n"
            f"前文：{input_data['前文']}\n"
            f"要求：{input_data['要求']}\n"
            f"续写内容："
        )

    def post_process(self, output: str) -> str:
        modern_to_ancient = {
            "说": "道", "看": "视", "跑": "奔", "突然": "忽", "很快": "俄而"
        }
        for modern, ancient in modern_to_ancient.items():
            output = output.replace(modern, ancient)
        return output

class SciFiStrategy(BaseStrategy):  # 补充科幻策略
    def format_prompt(self, input_data: dict) -> str:
        return (
            f"请续写以下科幻片段，体现科技感与未来感：\n"
            f"前文：{input_data['前文']}\n"
            f"要求：{input_data['要求']}\n"
            f"续写内容："
        )

    def post_process(self, output: str) -> str:
        sci_fi_keywords = ["量子", "飞船", "人工智能", "星际", "纳米"]
        if not any(kw in output for kw in sci_fi_keywords):
            output += " 控制台的全息投影突然闪烁，量子引擎发出低沉的嗡鸣。"
        return output

class EasternFantasyStyleStrategy(BaseStrategy):
    def format_prompt(self, input_data: dict) -> str:
        return (
            f"请续写以下玄幻片段，体现东方仙侠韵味，包含修炼、灵气等元素：\n"
            f"前文：{input_data['前文']}\n"
            f"要求：{input_data['要求']}\n"
            f"续写内容："
        )

    def post_process(self, output: str) -> str:
        eastern_fantasy_keywords = ["灵气", "修炼", "经脉", "法宝", "修仙", "境界", "宗门"]
        if not any(kw in output for kw in eastern_fantasy_keywords):
            logger.warning("续写内容可能缺少玄幻元素")
            return output + " 体内灵气骤然翻涌，丹田处似有暖流运转，竟是突破了当前境界。"
        return output


class SuspenseStrategy(BaseStrategy):
    def format_prompt(self, input_data: dict) -> str:
        return (
            f"请续写以下悬疑片段，保持紧张氛围和未知感，留有悬念：\n"
            f"前文：{input_data['前文']}\n"
            f"要求：{input_data['要求']}\n"
            f"续写内容："
        )

    def post_process(self, output: str) -> str:
        suspense_keywords = ["谜团", "线索", "诡异", "阴影", "秘密", "悬疑", "未知"]
        if not any(kw in output for kw in suspense_keywords):
            logger.warning("续写内容可能缺少悬疑元素")
            return output + " 黑暗中传来细微的声响，那道若隐若现的影子似乎动了一下，真相仍隐藏在迷雾深处。"
        return output
