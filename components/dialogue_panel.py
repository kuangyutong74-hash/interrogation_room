"""
审讯对话记录纸卷（右侧）
功能：
  - 从数据库读取当前嫌疑人的对话历史
  - 打字机纸卷视觉风格（浅黄底色 + 横线 + 等宽字体）
  - 生成 ABC 三个对话选项供玩家选择（点击即发送）
  - D 选项由玩家输入，AI 润色后发送
  - 调用 SuspectAgent.respond() 生成回复
  - 自动处理对质状态（如果 evidence_panel 设置了 confrontation_evidence）
"""
import streamlit as st
from agents.suspect_agent import SuspectAgent


# ── 辅助函数 ───────────────────────────────────────────────────


def _ensure_options_generated() -> None:
    """如果当前没有对话选项或需要刷新，重新生成 ABC 选项。"""
    if (
        st.session_state.get("_need_regenerate")
        or "dialogue_options" not in st.session_state
    ):
        sid = st.session_state.get("session_id")
        suspect_id = st.session_state.get("current_suspect_id", "suspect_a")
        if not sid:
            return

        try:
            agent = SuspectAgent(session_id=sid, suspect_id=suspect_id)
            case_bg = st.session_state.get("case_background", "")
            options = agent.generate_question_options(case_background=case_bg)
            st.session_state["dialogue_options"] = options
        except Exception:
            # LLM 调用失败时的保底选项
            st.session_state["dialogue_options"] = [
                "A: 解释一下你案发时在哪里？",
                "B: 我们掌握了一些对你不利的证据。",
                "C: 老实交代对你更有利。",
            ]
        st.session_state["_need_regenerate"] = False


def _send_message(text: str) -> None:
    """
    发送玩家消息 → 获取嫌疑人回复 → 标记重新生成选项 → 页面刷新。

    参数:
        text: 玩家发送的问话文本
    """
    sid = st.session_state.get("session_id")
    suspect_id = st.session_state.get("current_suspect_id", "suspect_a")
    if not sid or not text:
        return

    confrontation = st.session_state.pop("confrontation_evidence", None)

    try:
        agent = SuspectAgent(session_id=sid, suspect_id=suspect_id)
        if confrontation:
            agent.set_confrontation(confrontation["name"])

        result = agent.respond(text)

        if result.get("is_broken"):
            st.toast("💥 嫌疑人心理防线彻底崩溃！", icon="😵")
    except Exception as e:
        st.error(f"对话处理失败: {e}")

    # 标记需要重新生成选项（下一次渲染时生效）
    st.session_state["_need_regenerate"] = True
    st.rerun()


# ── 主渲染函数 ─────────────────────────────────────────────────


def render():
    st.subheader("📜 审讯对话记录")

    # ── 1. 历史对话纸卷 ──
    history = st.session_state.get("chat_history", [])

    chat_html = (
        '<div style="background-color:#e8e4d9; '
        'background-image:repeating-linear-gradient('
        '0deg, transparent, transparent 24px, #c9c5b8 25px); '
        'border:1px solid #8b7d6b; padding:15px; min-height:300px; max-height:500px; '
        'overflow-y:auto; font-family:\'Courier New\', monospace; line-height:25px;">'
    )
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "player":
            chat_html += (
                '<div style="text-align:right; margin-bottom:6px;">'
                '<span style="background:#2b2b2b; color:#e0e0d0; padding:4px 8px; '
                'border-radius:2px; font-size:0.9rem;">👮 {}</span></div>'
            ).format(content)
        elif role == "system":
            chat_html += (
                '<div style="text-align:center; color:#c62828; font-size:0.85rem; '
                'margin:6px 0; font-weight:bold;">{}</div>'
            ).format(content)
        else:
            chat_html += (
                '<div style="margin-bottom:6px;">'
                '<span style="background:#fff; padding:4px 8px; border:1px solid #ccc; '
                'border-radius:2px; color:#1a1a1a; font-size:0.9rem;">💬 {}</span></div>'
            ).format(content)
    chat_html += "</div>"

    st.markdown(chat_html, unsafe_allow_html=True)

    st.markdown("---")

    # ── 2. 确保 ABC 选项已生成 ──
    _ensure_options_generated()
    options = st.session_state.get("dialogue_options", [])

    # ── 3. ABC 三选项按钮 ──
    st.markdown("#### 🎯 审讯策略选项")
    st.caption("点击选项直接发送，或使用下方的自定义输入")

    ab_cols = st.columns(3)
    labels = ["A", "B", "C"]
    # 每个选项一个颜色标识
    accent_colors = ["#1a5276", "#1e8449", "#922b21"]

    for i, col in enumerate(ab_cols):
        with col:
            text = options[i] if i < len(options) else f"选项 {labels[i]}"
            # 去掉 "A: " / "B: " / "C: " 前缀做展示
            display = text
            for prefix in [f"{labels[i]}:", f"{labels[i]}："]:
                if text.startswith(prefix):
                    display = text[len(prefix) :].strip()
                    break

            # 用 st.markdown + st.button 组合实现带颜色的标签按钮
            st.markdown(
                f'<p style="margin:0 0 2px 0; font-size:0.75rem; '
                f'color:{accent_colors[i]}; font-weight:bold;">'
                f"策略 {labels[i]}</p>",
                unsafe_allow_html=True,
            )
            if st.button(
                display,
                key=f"opt_{labels[i]}",
                use_container_width=True,
            ):
                _send_message(text)

    # ── 4. D 选项：自定义输入 + AI 润色 ──
    st.markdown("---")
    st.markdown("##### ✏️ D: 自定义审问话术")

    d_col1, d_col2 = st.columns([5, 1])
    with d_col1:
        d_input = st.text_input(
            "自定义输入",
            placeholder="输入你想问的问题，AI 将自动润色后发送...",
            key="d_custom_input",
            label_visibility="collapsed",
        )
    with d_col2:
        if st.button("✨ 润色发送", key="polish_d", use_container_width=True):
            raw_text = st.session_state.get("d_custom_input", "").strip()
            if raw_text:
                sid = st.session_state.get("session_id")
                suspect_id = st.session_state.get(
                    "current_suspect_id", "suspect_a"
                )
                try:
                    agent = SuspectAgent(
                        session_id=sid, suspect_id=suspect_id
                    )
                    polished = agent.polish_user_input(raw_text)
                except Exception:
                    polished = raw_text  # 润色失败则使用原文

                st.toast("✨ 话术已润色并发送", icon="✨")
                _send_message(polished)
            else:
                st.warning("请输入审讯话术后再发送。")
