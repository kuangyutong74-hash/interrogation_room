"""
嫌疑人档案区（左上）
功能：
  - 顶部横向档案夹：切换当前审讯对象
  - 从 session_state 读取嫌疑人数据（name, role, expression_state, profile_json）
  - 根据 role 关键词动态映射像素风头像（管家/富商/炼金术师等）
  - 根据 expression_state（calm/nervous/broken）切换表情图
  - 解析 profile_json 展示不在场证明
  - 无素材时回退到像素风 Emoji
"""
import json
import os
import streamlit as st
from database.db_helper import DBHelper

# ── 角色类型 → 头像素材前缀映射表 ──
# key: 剧本中可能出现的 role 关键词（小写）
# value: assets/images/ 目录下的文件名前缀
ROLE_AVATAR_MAP = {
    "管家": "butler",
    "butler": "butler",
    "富商": "merchant",
    "merchant": "merchant",
    "炼金术师": "alchemist",
    "alchemist": "alchemist",
    "法医": "forensic",
    "doctor": "forensic",
    "侦探": "detective",
    "军官": "officer",
    "学者": "scholar",
    "默认": "default",
}

# ── 表情状态 → 文件名后缀 ──
EXPR_SUFFIX = {
    "calm": "calm",
    "nervous": "nervous",
    "broken": "broken",
}


def _resolve_avatar(role: str, expression: str, assets_dir: str = "assets/images") -> str:
    """
    根据角色描述和表情状态，解析对应的头像文件路径。
    如果精确匹配文件不存在，依次回退到：
      1. 该角色的 calm 表情图
      2. 空字符串（组件会回退到 Emoji 占位）
    """
    # 1. 从 role 中提取关键词（如"庄园的管家" → 匹配"管家"）
    role_lower = role.lower()
    avatar_prefix = ROLE_AVATAR_MAP.get("默认")
    for keyword, prefix in ROLE_AVATAR_MAP.items():
        if keyword in role_lower:
            avatar_prefix = prefix
            break

    # 2. 拼接表情后缀
    expr_key = EXPR_SUFFIX.get(expression, "calm")
    filename = f"{avatar_prefix}_{expr_key}.png"
    filepath = os.path.join(assets_dir, filename)

    # 3. 文件不存在时回退到默认表情
    if not os.path.exists(filepath):
        fallback = os.path.join(assets_dir, f"{avatar_prefix}_calm.png")
        if os.path.exists(fallback):
            return fallback
        return ""  # 最终回退到 Emoji

    return filepath


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

    current_id = st.session_state.get("current_suspect_id", "suspect_a")

    # 横向档案夹按钮
    cols = st.columns(len(all_suspects))
    for idx, s in enumerate(all_suspects):
        is_active = s["suspect_id"] == current_id
        border_bottom = "3px solid #c62828" if is_active else "1px solid #8b7d6b"
        bg = "#e8e4d9" if is_active else "#d4c5a9"

        with cols[idx]:
            if st.button(
                f"📁 {s['name']}",
                key=f"tab_{s['suspect_id']}",
                use_container_width=True,
                help=f"切换审讯对象：{s['role']}"
            ):
                st.session_state["current_suspect_id"] = s["suspect_id"]
                st.rerun()

            # 视觉指示条（HTML 实现档案夹标签效果）
            st.markdown(
                f"<div style='height:4px; background:{border_bottom}; margin-top:-8px;'></div>",
                unsafe_allow_html=True
            )

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    # ── 2. 当前嫌疑人详情展示 ──
    suspect = st.session_state.get("current_suspect", {})
    if not suspect:
        st.info("加载中...")
        return

    name = suspect.get("name", "???")
    role = suspect.get("role", "???")
    expr = suspect.get("expression_state", "calm")

    # 动态解析头像路径（按 role + expression 映射）
    avatar_path = _resolve_avatar(role, expr)

    if avatar_path:
        st.image(avatar_path, width=220)
    else:
        # 无素材时的像素风 Emoji 占位方案
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
        alibi = profile.get("alibi", "")
        if alibi:
            st.markdown(
                f"<div style='font-size:0.85rem; color:#555; margin-top:8px;'>📝 <i>\"{alibi}\"</i></div>",
                unsafe_allow_html=True,
            )
    except (json.JSONDecodeError, TypeError):
        pass