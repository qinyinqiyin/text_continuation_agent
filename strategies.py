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
        # 优化后的玄幻风格提示词，专为整章续写设计
        requirements_text = f"\n续写要求：{input_data['要求']}" if input_data.get('要求') else ""
        
        # 检测前文是否包含章节信息，并提取章节编号
        context = input_data['前文']
        import re
        chapter_match = re.search(r'第(\d+)章', context[:500])
        
        if chapter_match:
            current_chapter = int(chapter_match.group(1))
            next_chapter = current_chapter + 1
            chapter_instruction = f"""
【章节结构要求】
- 必须以"第{next_chapter}章 [章节标题]"的格式开头
- 章节标题要简洁有力（2-6字），概括本章核心情节或亮点
- 新章节要从上一章结尾自然承接，不可突兀转折或重复上一章内容
- 整个章节要有完整的情节弧线：开端→发展→小高潮/转折→结尾（含悬念）
- 章节结尾处设置悬念、转折或新的目标，为下一章留下钩子
- 章节长度要适中，内容丰富但不过于冗长"""
        else:
            chapter_instruction = """
【章节结构要求】
- 建议以"第X章 [章节标题]"的格式开头（如检测到上一章编号则自动递增）
- 章节要有完整的起承转合，不能只是片段
- 结尾处设置悬念，为后续做铺垫"""
        
        return f"""请根据前文内容续写新的章节，需严格遵循以下要求：

【风格要求】
1. 语言风格：
   - 半文半白，既保持古风韵味又不过度文言化
   - 对话使用简洁有力的现代白话，避免过度文绉绉
   - 叙述可适当加入古风词汇（如"倏忽"、"俄而"、"不禁"等）
   - 保持与前文一致的语感和节奏

2. 叙事节奏：
   - 紧凑有力，避免拖沓冗长
   - 多使用短句和短段落，营造紧张感和阅读节奏
   - 重要情节详细描写，过渡情节简洁带过

3. 描写重点：
   - 战斗场面：详细描写动作细节、灵气运转、攻防转换、招式效果
   - 修炼突破：细致描述灵气变化、境界感悟、身体反应、突破过程
   - 心理活动：通过内心独白展现人物思考，但要简洁不冗长
   - 环境描写：简洁有效，服务于情节推进和氛围营造

4. 玄幻元素：
   - 自然融入以下元素：灵气、修炼、境界（凝气、锻气、气海、妖境等）、功法、法宝、易道、易师、灵石等
   - 不可生硬堆砌，要让元素为情节服务
   - 修炼体系的运用要符合设定（人境三重天、妖境等）

5. 情节推进：
   - 保持悬念，适当埋下伏笔
   - 重要情节要有铺垫，不可突然转折
   - 章节结尾处要有悬念或转折点，为下一章留下吸引点

6. 人物塑造：
   - 通过行动和对话展现性格，避免空洞的描述
   - 保持人物性格一致性
   - 主要人物（熊心、魂鸟/幽、小泽等）的性格特点要与前文一致

【前文内容】
{context}{requirements_text}
{chapter_instruction}

【续写要求】
1. 情节承接：从上一章的结尾自然过渡，保持情节连贯性
2. 人物一致性：保持所有登场人物的性格、能力、关系与前文一致
3. 世界观一致性：遵循已建立的修炼体系、设定和规则
4. 语言统一：语言风格、叙事节奏与前文保持一致
5. 章节完整：本章要有完整的起承转合，不能只是片段
6. 内容丰富：达到要求的字数，内容充实，有具体的情节发展
7. 伏笔设置：适当埋下伏笔，为后续章节做铺垫

请开始续写新章节："""
        
    def post_process(self, output: str) -> str:
        # 移除可能添加的多余元素，保持原始输出
        eastern_fantasy_keywords = ["灵气", "修炼", "经脉", "法宝", "修仙", "境界", "宗门", "凝气", "锻气", "气海", "易师", "妖境"]
        # 不再强制添加元素，仅做检查
        if not any(kw in output for kw in eastern_fantasy_keywords):
            logger.warning("续写内容可能缺少玄幻元素")
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
