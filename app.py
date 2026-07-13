"""
前端主入口（成员 D 负责）
职责：页面配置 → CSS注入 → 数据库初始化 → 状态管理器调度 → 布局渲染
"""
import streamlit as st
import os

from utils.style_loader import load_css
from database.db_helper import DBHelper
from state.session_manager import GameSessionManager
from components import (
    header,
    suspect_panel,
    defense_bar,
    evidence_panel,
    dialogue_panel,
    control_panel,
    forensic_popup,
)

# ── 页面配置 ──
st.set_page_config(
    page_title="审讯室风云 | Interrogation Room",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 加载复古CSS（像素风、纸质纹理、LED仪表盘样式） ──
load_css()

# ── 初始化数据库（幂等，已有表不重复创建） ──
DBHelper.init_db()

# ── 游戏状态管理器 ──
manager = GameSessionManager()

# 首次访问：自动创建新案件
if "session_id" not in st.session_state:
    manager.start_new_game("manor")

# 每次 rerun 从数据库同步最新状态
manager.refresh_all()

# ── 时序打断：检查法医异步报告 ──
forensic_popup.check_and_render()

# ── 结案遮罩（逮捕/释放印章动画） ──
if st.session_state.get("case_closed"):
    stamp = st.session_state.get("stamp_anim", "")
    color = "#c62828" if stamp == "arrest" else "#2e7d32"
    text = "ARRESTED" if stamp == "arrest" else "RELEASED"
    st.markdown(
        f"""
        <div style="position:fixed; top:30%; left:50%; transform:translate(-50%,-50%) rotate(-15deg);
                    border:8px solid {color}; color:{color}; padding:20px 40px; font-size:3rem;
                    font-family:VT323, monospace; font-weight:bold; opacity:0.9; z-index:9999;
                    background:rgba(0,0,0,0.8);">
            {text}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("重新开始新案件", key="reset_case"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ── 主布局：左右分栏（审讯桌） ──
header.render()

left, right = st.columns([4, 5])

with left:
    # 左上：嫌疑人档案 + 心理防线
    suspect_panel.render()
    defense_bar.render()
    # 左下：证物抽屉
    evidence_panel.render()

with right:
    # 右侧：打字机纸卷对话区
    dialogue_panel.render()

st.divider()

# 底栏：盖章控制台
control_panel.render()