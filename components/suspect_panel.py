"""
嫌疑人档案区（左上）
新增功能：顶部横向排列全部嫌疑人档案夹，点击切换当前审讯对象
"""
import json
import os
import streamlit as st
from database.db_helper import DBHelper


def render():
    sid = st.session_state.get("session_id")
    if not sid:
        st.warning("会话未初始化")
        return

    # ── 1. 嫌疑人档案夹切换栏 ──
    all_suspects = DBHelper.get_all_suspects(sid)
    if not all_suspects:
        st.warning("本案暂无嫌疑人数据")
        return

    # 当前正在审讯的嫌疑人
    current_id = st.session_state.get("current_suspect_id", "suspect_a")

    # 用列布局实现横向档案夹
    cols = st.columns(len(all_suspects))
    for idx, s in enumerate(all_suspects):
        is_active = s["suspect_id"] == current_id
        # 档案夹标签样式：当前选中有红色下划线
        border_bottom = "3px solid #c62828" if is_active else "1px solid #8b7d6b"
        bg = "#e8e4d9" if is_active else "#d4c5a9"
        
        with cols[idx]:
            # 点击档案夹名称切换嫌疑人
            if st.button(
                f"📁 {s['name']}",
                key=f"tab_{s['suspect_id']}",
                use_container_width=True,
                help=f"切换审讯对象：{s['role']}"
            ):
                st.session_state["current_suspect_id"] = s["suspect_id"]
                st.rerun()  # 触发页面刷新，session_manager.refresh_all() 会重新加载新嫌疑人的数据
            
            # 视觉指示条（HTML 实现档案夹标签效果）
            st.markdown(
                f"<div style='height:4px; background:{border_bottom}; margin-top:-8px;'></div>",
                unsafe_allow_html=True
            )

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    # ── 2. 当前嫌疑人详情展示（原有逻辑） ──
    suspect = st.session_state.get("current_suspect", {})
    if not suspect:
        st.info("加载中...")
        return

    name = suspect.get("name", "???")
    role = suspect.get("role", "???")
    expr = suspect.get("expression_state", "calm")

    # 像素风头像
    avatar_path = suspect.get("avatar", "")
    if avatar_path and os.path.exists(avatar_path):
        st.image(avatar_path, width=220)
    else:
        emoji_map = {"calm": "😐", "nervous": "😰", "broken": "😵"}
        st.markdown(
            f"<div style='font-size:4rem; text-align:center; filter:grayscale(100%) contrast(120%);'>{emoji_map.get(expr, '😐')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='text-align:center; font-size:0.9rem; color:#555; font-family:VT323;'>{expr.upper()}</div>",
            unsafe_allow_html=True,
        )

    st.markdown(f"### {name}")
    st.caption(role)

    # 解析 profile_json 展示不在场证明
    profile_raw = suspect.get("profile_json", "{}")
    try:
        profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
        alibi = profile.get("alibi", "无记录")
        st.markdown(
            f"<div style='font-size:0.85rem; color:#555; margin-top:8px;'>📝 <i>\"{alibi}\"</i></div>",
            unsafe_allow_html=True,
        )
    except (json.JSONDecodeError, TypeError):
        pass