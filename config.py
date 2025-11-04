import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TextContinuationAgent")

# 重定向日志到Streamlit（仅在Streamlit环境中使用）
try:
    import streamlit as st
    
    class StreamlitLogger(logging.Handler):
        def emit(self, record):
            msg = self.format(record)
            if record.levelno == logging.ERROR:
                st.error(msg)
            elif record.levelno == logging.WARNING:
                st.warning(msg)
            else:
                st.info(msg)
    
    # 仅在Streamlit环境中添加handler
    logger.addHandler(StreamlitLogger())
except ImportError:
    # Flask环境或其他非Streamlit环境，使用标准日志
    pass