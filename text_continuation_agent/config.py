import logging
import streamlit as st

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TextContinuationAgent")

# 重定向日志到Streamlit
class StreamlitLogger(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        if record.levelno == logging.ERROR:
            st.error(msg)
        elif record.levelno == logging.WARNING:
            st.warning(msg)
        else:
            st.info(msg)

logger.addHandler(StreamlitLogger())