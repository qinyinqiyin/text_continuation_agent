"""
可选占位：LangChain @tool 演示，不向任何注册表登记。

创作管线工具见 `story_markdown_tools.py`；Outline / Planning / Writing 三阶段均在 `rag_agent.RAGAgent` 中经由同一套工具与各自的向量检索摘录运行。

需在链/agent 中使用工具时：对 Chat 模型 `bind_tools` 或使用 AgentExecutor 即可。
"""

from langchain_core.tools import tool


@tool
def heartbeat() -> str:
    """占位探活工具，无参数、无副作用。"""
    return "ok"
