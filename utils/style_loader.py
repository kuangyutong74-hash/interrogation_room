"""加载自定义 CSS 样式表"""

import streamlit as st
import os


def load_css() -> None:
    """将 assets/style.css 注入 Streamlit 页面"""
    css_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "style.css"
    )
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
