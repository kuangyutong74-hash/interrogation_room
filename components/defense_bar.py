"""
心理防线 LED 仪表盘（左上档案区下方）
功能：
  - 将 0-100 分渲染为 20 个粗颗粒 LED 方块
  - 按分数段显示绿(70+)/黄(40+)/红(<40)三色
  - 附带状态文字说明
"""
import streamlit as st


def render():
    score = st.session_state.get("defense_score", 100)

    st.markdown("### 🛡️ 心理防线波动仪")

    # 构造 20 个 LED 方块 HTML
    total = 20
    filled = int(score / 100 * total)
    blocks = ""
    for i in range(total):
        if i < filled:
            if score >= 70:
                color, shadow = "#4caf50", "0 0 4px #4caf50"
            elif score >= 40:
                color, shadow = "#ffeb3b", "0 0 4px #ffeb3b"
            else:
                color, shadow = "#f44336", "0 0 4px #f44336"
            style = f"background-color:{color}; box-shadow:{shadow}; border:1px solid #555;"
        else:
            style = "background-color:#333; box-shadow:inset 1px 1px 2px rgba(0,0,0,0.5); border:1px solid #555;"
        blocks += f'<div style="width:14px; height:20px; {style} display:inline-block; margin-right:3px;"></div>'

    st.markdown(
        f'<div style="display:flex; align-items:center; flex-wrap:wrap; gap:3px;">{blocks}<span style="margin-left:8px; font-size:1.2rem; font-family:VT323;">{score}%</span></div>',
        unsafe_allow_html=True,
    )

    # 状态文字
    if score >= 70:
        st.caption("状态：态度傲慢、冷静，回答滴水不漏。")
    elif score >= 40:
        st.caption("状态：出现防御性姿态，回答含糊。")
    else:
        st.caption("状态：神色慌张，开始吐露关键旁证。")