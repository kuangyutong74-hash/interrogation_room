"""
审讯对话记录纸卷（右侧）
功能：
  - 从数据库读取当前嫌疑人的对话历史
  - 打字机纸卷视觉风格（浅黄底色 + 横线 + 等宽字体）
  - 输入框接收玩家话术，调用 B 的 SuspectAgent.respond() 生成回复
  - 自动处理对质状态（如果 evidence_panel 设置了 confrontation_evidence）
"""
import streamlit as st
from database.db_helper import DBHelper
from agents.suspect_agent import SuspectAgent


def render():
    st.subheader("📜 审讯对话记录")

    history = st.session_state.get("chat_history", [])

    # 打字机纸卷容器（浅黄底色 + 模拟横线）
    chat_html = '<div style="background-color:#e8e4d9; background-image:repeating-linear-gradient(0deg, transparent, transparent 24px, #c9c5b8 25px); border:1px solid #8b7d6b; padding:15px; min-height:300px; max-height:500px; overflow-y:auto; font-family:\'Courier New\', monospace; line-height:25px;">'
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "player":
            chat_html += f'<div style="text-align:right; margin-bottom:6px;"><span style="background:#2b2b2b; color:#e0e0d0; padding:4px 8px; border-radius:2px; font-size:0.9rem;">{content}</span></div>'
        elif role == "system":
            chat_html += f'<div style="text-align:center; color:#c62828; font-size:0.85rem; margin:6px 0; font-weight:bold;">{content}</div>'
        else:
            chat_html += f'<div style="margin-bottom:6px;"><span style="background:#fff; padding:4px 8px; border:1px solid #ccc; border-radius:2px; color:#1a1a1a; font-size:0.9rem;">{content}</span></div>'
    chat_html += "</div>"

    st.markdown(chat_html, unsafe_allow_html=True)

    # 终端输入框
    user_input = st.chat_input("输入审讯话术...")
    if user_input:
        sid = st.session_state.get("session_id")
        suspect_id = st.session_state.get("current_suspect_id", "suspect_a")

        # 取出 evidence_panel 设置的对质证物（如果有）
        confrontation = st.session_state.pop("confrontation_evidence", None)

        # 调用 B 的 SuspectAgent（内部已包含：写入玩家输入 → LLM生成 → 写入嫌疑人回复 → 矛盾检测）
        agent = SuspectAgent(session_id=sid, suspect_id=suspect_id)
        if confrontation:
            agent.set_confrontation(confrontation["name"])

        # 生成回复（数据库已自动写入）
        result = agent.respond(user_input)

        # 如果防线崩溃，可在此处触发额外特效（如页面抖动、音效占位）
        if result.get("is_broken"):
            st.toast("💥 嫌疑人心理防线彻底崩溃！", icon="😵")

        # 强制刷新页面，让新对话和防线值显示
        st.rerun()