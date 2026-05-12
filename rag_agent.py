"""StoryWriter 论文架构：Outline → Planning → Writing。
三阶段共用同一套 LangChain 工具；各阶段按自身上下文构造检索查询并各做一次向量检索；
Human 消息串联共享叙事上下文（前文、意图、上阶段产出）。"""

from typing import Dict, List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from config import logger
from knowledge_base import ChromaKnowledgeBase
from rerank import rerank_documents
from story_markdown_tools import get_story_creation_tools
from storywriter_agents import (
    OUTLINE_AGENT_INSTRUCTION,
    PLANNING_AGENT_INSTRUCTION,
    SHARED_STORY_TOOLS_INSTRUCTION,
    WRITING_AGENT_CORE,
    build_outline_user_message,
    build_planning_user_message,
    format_shared_kb_excerpt,
    format_writing_task_block,
)


class RAGAgent:
    """三段式 Agent：每阶段 tool-calling + 本阶段独立向量检索。"""

    def __init__(self, model, kb: ChromaKnowledgeBase):
        self.model = model
        self.kb = kb

    def _retrieve_for_prompt(self, retrieval_query: str) -> List[Document]:
        """按本阶段的检索语句拉取向量库片段并经 rerank（一次调用即该阶段独有的一次检索）。"""
        q = (retrieval_query or "").strip()
        if not q:
            q = "小说叙事 世界观 角色"
        try:
            docs = self.kb.search_relevant_documents(q, top_n=15)
            if docs:
                docs = rerank_documents(q, docs, top_n=10)
            return docs
        except Exception as e:
            logger.warning("向量检索失败：%s", e)
            return []

    def _bind_chat_temperature(self, chat_llm, max_new_tokens: int, temperature: float):
        llm_tc = chat_llm
        for binder in (
            lambda m: m.bind(max_tokens=int(max_new_tokens), temperature=float(temperature)),
            lambda m: m.bind(temperature=float(temperature)),
        ):
            try:
                return binder(chat_llm)
            except TypeError:
                continue
        return llm_tc

    def _run_shared_tool_agent(
        self,
        chat_llm,
        *,
        core_instruction: str,
        phase_constraint: str,
        kb_docs: List[Document],
        human_input: str,
        max_new_tokens: int,
        temperature: float,
        max_iterations: int = 8,
    ) -> str:
        """三阶段共用：同一套工具 + AgentExecutor。"""
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import MessagesPlaceholder
        except ImportError as e_inner:
            raise RuntimeError(f"缺少 Agent 组件：{e_inner}") from e_inner

        tools = get_story_creation_tools()
        kb_block = format_shared_kb_excerpt(kb_docs)
        system_text = (
            core_instruction.strip()
            + "\n\n"
            + SHARED_STORY_TOOLS_INSTRUCTION
            + "\n\n"
            + phase_constraint.strip()
            + "\n\n【本阶段向量检索摘录】\n"
            + kb_block
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_text),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        llm_tc = self._bind_chat_temperature(chat_llm, max_new_tokens, temperature)
        agent = create_tool_calling_agent(llm_tc, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
        )
        out = executor.invoke({"input": human_input})
        return ((out.get("output") or "")).strip()

    def run(
        self,
        前文: str,
        要求: str = "",
        *,
        max_new_tokens: int = 300,
        temperature: float = 0.6,
    ) -> Dict[str, str]:
        前文 = 前文.strip()
        要求 = 要求.strip()

        chat = getattr(self.model, "chat_llm", None)
        if chat is None:
            raise RuntimeError(
                "未初始化 ChatTongyi（model.chat_llm）。三阶段均依赖共享工具 Agent，请检查 ChatTongyi。"
            )

        # --- Outline：面向全局事件的检索 ---
        rq_outline = "\n".join(
            filter(None, [要求 or None, "长篇故事事件大纲人物关系转折", (前文[-1800:] if 前文 else None)])
        ).strip()
        if not rq_outline:
            rq_outline = 前文[-800:] if 前文 else "故事大纲推演"
        docs_outline = self._retrieve_for_prompt(rq_outline)

        outline = ""
        try:
            outline = self._run_shared_tool_agent(
                chat,
                core_instruction=OUTLINE_AGENT_INSTRUCTION,
                phase_constraint="【阶段约束】最终可见输出必须为**事件化纲要**；严禁小说对白、场景正文段落。",
                kb_docs=docs_outline,
                human_input=build_outline_user_message(前文, 要求),
                max_new_tokens=900,
                temperature=min(0.45, float(temperature)),
            )
            logger.info("StoryWriter Outline Agent（共享工具）已完成")
        except Exception as e:
            logger.warning("Outline Agent 失败：%s", e)

        outline_effective = (outline or "").strip()
        fallback_outline = outline_effective or "（纲要暂缺：请仅依据故事末尾与用户意图推导下一书写单元）"

        # --- Planning：面向下一书写单元的检索（携带大纲共享上下文）---
        rq_plan = "\n".join(
            filter(
                None,
                [
                    要求 or None,
                    fallback_outline[:3000],
                    "紧邻下一书写单元情节规划戏剧性目标衔接",
                    (前文[-1500:] if 前文 else None),
                ],
            )
        ).strip()
        docs_planning = self._retrieve_for_prompt(rq_plan)

        plan_text = ""
        try:
            plan_text = self._run_shared_tool_agent(
                chat,
                core_instruction=PLANNING_AGENT_INSTRUCTION,
                phase_constraint=(
                    "【阶段约束】最终可见输出必须为**书写规划分项**（概括/戏剧性目标/衔接要点）；严禁小说对白与成片正文。"
                ),
                kb_docs=docs_planning,
                human_input=build_planning_user_message(fallback_outline, 前文, 要求),
                max_new_tokens=700,
                temperature=min(0.55, float(temperature)),
            )
            logger.info("StoryWriter Planning Agent（共享工具）已完成")
        except Exception as e:
            logger.warning("Planning Agent 失败：%s", e)

        plan_effective = (plan_text or "").strip()
        if not plan_effective:
            plan_effective = 要求 or "继续自然推导情节，并保持与上文末尾衔接。"

        # --- Writing：面向接续正文的检索（携带大纲+规划共享上下文）---
        rq_write = "\n".join(
            filter(
                None,
                [
                    要求 or None,
                    plan_effective[:2500],
                    outline_effective[:2000] if outline_effective else None,
                    "长篇小说续写衔接叙事连贯",
                    (前文[-1500:] if 前文 else None),
                ],
            )
        ).strip()
        docs_writing = self._retrieve_for_prompt(rq_write)

        answer = self._run_shared_tool_agent(
            chat,
            core_instruction=WRITING_AGENT_CORE,
            phase_constraint=(
                "【阶段约束】最终可见输出必须为**接续小说正文**；禁元话语（如「以下续写」）、禁暴露工具调用过程。"
            ),
            kb_docs=docs_writing,
            human_input=format_writing_task_block(plan_effective, 前文, 要求),
            max_new_tokens=max_new_tokens,
            temperature=float(temperature),
            max_iterations=8,
        )
        logger.info("StoryWriter Writing Agent（共享工具）已完成")

        return {
            "result": answer,
            "outline": outline_effective,
            "planning": plan_effective,
        }
