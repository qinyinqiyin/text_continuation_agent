"""
StoryWriter 论文风格的多阶段提示编排（arxiv:2506.16445）。
架构：Outline → Planning → Writing；三阶段共用**同一套可调工具**，共享叙事上下文（前文、意图、上阶段产出）；
向量库为**各阶段根据其 Prompt / 上下文各检索一次**，摘录注入该阶段系统提示。
"""
from __future__ import annotations

from typing import List

from langchain_core.documents import Document


# ---------- 三阶段完全一致的工具说明（与各 Agent 系统指令拼接） ----------
SHARED_STORY_TOOLS_INSTRUCTION = """\
【共享工具｜Outline / Planning / Writing 三套 Agent 完全一致】
以下工具任选调用（参数与含义不变）；章节与模板 Markdown 默认位于项目 `markdown/`：
• query_article_chapter_markdown(chapter_identifier)：传入章节数字或「第N章」，从合并稿 `existing articles.md` 自动切分正文；也可用文件名主干读取单文件；
• query_reference_template_markdown(template_name)：读取参考模板 Markdown（如 reference template）；
• web_search_story_assistance(query)：DuckDuckGo 简短联网检索，辅助事实与世界观核查。
按需使用即可；最终以本阶段指定的**可见输出体裁**为准（下文「阶段约束」），勿在最终答案里输出工具 JSON。"""


# ---------- Outline Agent：事件化大纲 ----------
OUTLINE_AGENT_INSTRUCTION = """\
你是 StoryWriter 框架中的 **Outline Agent**（参考论文 Outline Agent）。
任务：在共享叙事上下文上，依据**系统消息中【本阶段向量检索摘录】**（与该阶段 Outline 任务对齐的一次检索），并可在需要时调用**共享工具**，产出**事件驱动**的长篇故事纲要。
纲要须包含但不限于：
1）主要情节事件链条（可分条列出）；2）涉及的**人物要点**与人际/立场关系；3）事件之间的因果、时间或递进关系。
要求：纲要简洁可执行；不要写小说对白与场景正文；不要使用「以下为大纲」类套话。
输出语言与用户的正文语言一致（默认中文）。
"""


def format_shared_kb_excerpt(docs: List[Document]) -> str:
    """将本阶段检索到的 Document 片段格式化为可读摘录。"""
    if not docs:
        return "（本阶段向量检索未命中条目；请依赖正文、意图与可选工具素材。）"
    parts: List[str] = []
    for i, d in enumerate(docs, start=1):
        meta = d.metadata or {}
        t = meta.get("type", "")
        prefix = f"[{i}]"
        if t:
            prefix += f"〈{t}〉"
        parts.append(f"{prefix}\n{d.page_content.strip()}")
    return "\n\n────────\n\n".join(parts)


def build_outline_user_message(已有正文: str, 用户意图: str) -> str:
    """Outline 轮的 Human：**仅**共享叙事上下文；知识库摘录在系统提示中（本阶段独立检索）。"""
    tail = 已有正文[-6000:] if len(已有正文) > 6000 else 已有正文
    intent = (用户意图 or "").strip() or "（无额外说明：请根据已有正文续推情节势能）"
    return (
        "【三阶段共享叙事上下文 · Outline 轮】\n"
        f"【本轮写作意图】\n{intent}\n\n"
        f"【已有故事正文（含末尾；用于推导全局事件结构）】\n{tail}\n\n"
        "请输出**更新后的事件化大纲**。"
    )


def build_planning_user_message(事件大纲: str, 已有正文: str, 用户意图: str) -> str:
    """Planning 轮的 Human：携带 Outline 产出，与下文 Writing 对齐。"""
    tail = 已有正文[-4000:] if len(已有正文) > 4000 else 已有正文
    intent = (用户意图 or "").strip() or "（无）"
    return (
        "【三阶段共享叙事上下文 · Planning 轮】\n"
        f"【事件大纲（Outline Agent；与 Writing 共用）】\n{事件大纲}\n\n"
        f"【本轮写作意图】\n{intent}\n\n"
        f"【已有故事末尾（用于对齐衔接）】\n{tail}\n\n"
        "请给出**下一轮 Writing Agent 应执行的书写规划**（按上文格式要求分项输出）。"
    )


# ---------- Planning Agent：章节内的书写规划 ----------
PLANNING_AGENT_INSTRUCTION = """\
你是 StoryWriter 框架中的 **Planning Agent**（参考论文 Planning Agent）。
任务：在共享叙事上下文上，依据**系统消息中【本阶段向量检索摘录】**（与该阶段 Planning 任务对齐的一次检索），并可在需要时调用**共享工具**，细化**紧邻下一书写单元**的规划：让读者感到情节交织、递进自然。
产出须明确给出：
• **当前应写的情节事件一句话概括**；
• **本段应落实的戏剧性目标**（如信息揭示、冲突升级、伏笔回收之一）；
• **与上文衔接要点**（指代上文哪些线索，不要复述原文）。
勿写成片正文或对白；不要使用「以下为规划」等套话。
输出语言与用户正文一致（默认中文）。
"""


# ---------- Writing Agent：接续正文 ----------
WRITING_AGENT_CORE = """\
你是 StoryWriter 框架中的 **Writing Agent**（参考论文 Writing Agent）。
任务：在共享叙事上下文上，依据**系统消息中【本阶段向量检索摘录】**（与该阶段续写任务对齐的一次检索），并可在需要时调用**与 Outline、Planning 完全相同的共享工具**，产出**连贯的小说正文**，从接写锚点**最后一句之后**自然续写。
写法要求：
• **动态关照全文线索**：你已看到故事末尾节选与规划——请像论文中一样**压缩并利用**这些信息，不写与规划无关的支线；
• **话语连贯**：时态、人称、称谓与上文一致；
• **不输出元话语**（如「以下续写」「第一章」）；除非用户明确要求，少用 Markdown 大标题堆砌；
• 【本阶段向量检索摘录】仅为参考：与正文冲突时以已有故事正文与用户意图为准；
• 切勿机械复述「接写锚点」原文句子，应从下一句顺延展开。
"""


def format_writing_task_block(current_event_plan: str, 故事前文: str, 用户意图: str) -> str:
    """Writing 轮的 Human：汇合 Planning 产出与接写上下文（知识库摘录在系统侧）。"""
    intent = (用户意图 or "").strip()
    chunks = ["【三阶段共享叙事上下文 · Writing 轮】"]
    if intent:
        chunks.append(f"【用户意图】\n{intent}")
    chunks.append(f"【Planning Agent 对本回合的规划】\n{current_event_plan}")
    chunks.append(
        "【故事接写锚点（仅从最后一句话之后续写；勿重复大块上文）】\n"
        + 故事前文
    )
    chunks.append(
        "请直接输出接续正文："
    )
    return "\n\n".join(chunks)
