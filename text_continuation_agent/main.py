import streamlit as st
import json
import os
from config import logger
from models import APIModel
from strategies import (
    FantasyStrategy, AncientStyleStrategy, SciFiStrategy,
    EasternFantasyStyleStrategy, SuspenseStrategy
)
from knowledge_base import FAISSKnowledgeBase
from agent import RAGTextContinuationAgent


class StrategyFactory:
    @staticmethod
    def get_strategy(style: str):
        strategy_map = {
            "fantasy": FantasyStrategy,
            "ancient": AncientStyleStrategy,
            "sci-fi": SciFiStrategy,
            "EasternFantasy": EasternFantasyStyleStrategy,
            "Suspense": SuspenseStrategy
        }
        if style not in strategy_map:
            raise ValueError(f"不支持的风格：{style}")
        return strategy_map[style]()


def main():
    st.set_page_config(page_title="文本续写助手", page_icon="📝", layout="wide")

    if "knowledge_base" not in st.session_state:
        st.session_state.knowledge_base = FAISSKnowledgeBase()

    tab1, tab2 = st.tabs(["📝 文本续写", "⚙️ 设定管理"])

    with tab2:
        st.header("故事设定管理（RAG检索用）")

        # 添加新设定区域
        st.subheader("添加新设定")
        col1, col2 = st.columns([1, 3])
        with col1:
            setting_type = st.selectbox(
                "设定类型",
                ["角色设定", "世界观设定", "关键物品设定", "情节限制"]
            )
        with col2:
            setting_content = st.text_area(
                "设定内容",
                placeholder=f"请输入{setting_type}...",
                height=100
            )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("添加设定", type="primary"):
                if setting_content.strip():
                    msg = st.session_state.knowledge_base.add_setting(
                        setting_type, setting_content
                    )
                    st.success(msg)
                    st.rerun()
                else:
                    st.error("请输入设定内容")

        with btn_col2:
            # 为按钮添加唯一key，避免状态缓存
            if st.button("清空所有设定", type="secondary", use_container_width=True, key="clear_btn"):
                # 使用st.empty()创建占位符，确保状态刷新
                status_placeholder = st.empty()
                if st.checkbox("确认清空所有设定（此操作不可恢复）", key="confirm_clear"):
                    with status_placeholder:
                        msg = st.session_state.knowledge_base.clear_all_settings()
                        st.success(msg)

                    # 双重刷新机制：先延迟再刷新
                    import time
                    time.sleep(0.3)  # 等待缓存操作完成
                    st.rerun()
        # 显示已添加的设定（核心修改：通过索引删除）
        st.markdown("---")
        st.subheader("已添加的设定")
        all_settings = st.session_state.knowledge_base.get_all_settings()

        if not all_settings:
            st.info("尚未添加任何设定")
        else:
            # 按类型分组显示
            type_groups = {}
            for idx, (doc, meta) in enumerate(all_settings):
                setting_type = meta["type"]
                if setting_type not in type_groups:
                    type_groups[setting_type] = []
                type_groups[setting_type].append((idx, doc))

            for setting_type, items in type_groups.items():
                with st.expander(f"📌 {setting_type}", expanded=True):
                    for idx, (original_index, doc) in enumerate(items):
                        col_content, col_action = st.columns([4, 1])
                        with col_content:
                            st.write(f"**设定 {idx + 1}**：{doc}")
                        with col_action:
                            # 通过原始索引删除
                            if st.button(
                                    "删除",
                                    key=f"del_{original_index}",  # 使用原始索引作为唯一标识
                                    type="secondary",
                                    use_container_width=True
                            ):
                                success = st.session_state.knowledge_base.delete_setting(original_index)
                                if success:
                                    st.success(f"已删除【{setting_type}】的设定")
                                    st.rerun()
                                else:
                                    st.error("删除失败，请重试")
                    st.divider()

    with tab1:
        st.title("📝 文本风格续写助手（PyTorch版）")

        with st.sidebar:
            st.header("⚙️ 配置选项")
            api_key = st.text_input("阿里云DashScope API密钥", type="password")
            style = st.selectbox(
                "续写风格",
                ["fantasy", "ancient", "sci-fi", "EasternFantasy", "Suspense"],
                format_func=lambda x: {
                    "fantasy": "奇幻风格",
                    "ancient": "古风风格",
                    "sci-fi": "科幻风格",
                    "EasternFantasy": "玄幻风格",
                    "Suspense": "悬疑风格"
                }[x]
            )
            max_length = st.slider("最大续写长度", 100, 1000, 300)
            temperature = st.slider("创造性", 0.0, 1.0, 0.6, 0.1)
            use_rag = st.checkbox("启用RAG（参考设定）", value=True)

        context = st.text_area("前文内容", placeholder="请输入需要续写的前文...", height=200)
        requirements = st.text_input("续写要求", placeholder="例如：承接剧情发展，增加悬念...")

        if st.button("🚀 开始续写", type="primary"):
            if not api_key or not context.strip():
                st.error("请完善API密钥和前文内容")
                return

            try:
                with st.spinner("生成中..."):
                    model = APIModel(api_key=api_key)
                    strategy = StrategyFactory.get_strategy(style)
                    agent = RAGTextContinuationAgent(
                        model, strategy, st.session_state.knowledge_base
                    )

                    input_data = {"前文": context, "要求": requirements}
                    if use_rag:
                        result = agent.run_with_rag(
                            input_data,
                            max_new_tokens=max_length,
                            temperature=temperature
                        )
                    else:
                        result = agent.run(
                            input_data,
                            max_new_tokens=max_length,
                            temperature=temperature
                        )

                    st.subheader("续写结果")
                    st.success(result)

                    history_json = json.dumps(
                        agent.history_memory,
                        ensure_ascii=False,
                        indent=2
                    )
                    st.download_button(
                        "💾 下载历史记录",
                        data=history_json,
                        file_name="continuation_history.json",
                        mime="application/json"
                    )
            except Exception as e:
                logger.error(f"续写失败: {str(e)}")
                st.error(f"操作失败：{str(e)}")

    st.markdown("---")
    st.caption("© 文本续写助手 | 基于PyTorch+FAISS实现")


if __name__ == "__main__":
    main()
