"""
证物与线索抽屉（左下）
功能：
  - 从数据库读取已发现证物，以纸质卡片形式展示
  - 支持选中态（红框高亮）
  - 未分析证物：显示"送检"按钮（消耗行动点，调用 C 的异步队列）
  - 已分析证物：显示"对质"按钮（设置对质状态，供 dialogue_panel 消费）
"""
import streamlit as st
from database.db_helper import DBHelper


def render():
    st.subheader("📁 证物抽屉")

    evidences = st.session_state.get("evidences", [])
    action_points = st.session_state.get("action_points", 0)

    if not evidences:
        st.info("暂无已发现证物")
        return

    st.caption(f"剩余行动点：{'🔵' * action_points}")

    # 两列网格布局
    ev_cols = st.columns(2)
    for idx, ev in enumerate(evidences):
        with ev_cols[idx % 2]:
            is_selected = st.session_state.get("selected_evidence_id") == ev["evidence_id"]
            border_color = "#d32f2f" if is_selected else "#6b5b4f"
            bg_color = "#fff3e0" if is_selected else "#f4f1e8"

            # 纸质卡片 HTML
            card_html = f"""
            <div style="background:{bg_color}; border:2px solid {border_color}; padding:8px; text-align:center; margin-bottom:8px; border-radius:2px; box-shadow:2px 2px 0 rgba(0,0,0,0.2);">
                <div style="font-size:1.5rem;">{'🔬' if ev.get('is_analyzed') else '📄'}</div>
                <div style="font-weight:bold; font-size:1.05rem; color:#2b2b2b;">{ev['name']}</div>
                <div style="font-size:0.8rem; color:#555;">{ev.get('description', '')[:40]}...</div>
                {'<div style="color:#d32f2f; font-size:0.8rem; margin-top:4px;">⏳ 化验中...</div>' if ev.get('analysis_pending') else ''}
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)

            # 选中按钮
            if st.button("选中", key=f"sel_{ev['evidence_id']}", use_container_width=True):
                st.session_state["selected_evidence_id"] = (
                    ev["evidence_id"] if not is_selected else None
                )
                st.rerun()

            # 选中状态下的操作按钮
            if is_selected:
                # 送检：未分析且未在化验中
                if not ev.get("is_analyzed") and not ev.get("analysis_pending"):
                    if st.button("🔬 送检化验", key=f"submit_{ev['evidence_id']}", use_container_width=True):
                        if action_points > 0:
                            # 消耗行动点
                            DBHelper.update_action_points(st.session_state["session_id"], -1)
                            # 提交到异步队列
                            fa = st.session_state.get("forensic_agent")
                            if fa:
                                fa.submit_analysis(ev["evidence_id"])
                            else:
                                DBHelper.submit_for_analysis(st.session_state["session_id"], ev["evidence_id"])
                            st.toast("证物已送检，法医实验室正在分析...", icon="🔬")
                            st.rerun()
                        else:
                            st.toast("行动点数不足！", icon="⚠️")

                # 对质：已分析完成
                if ev.get("is_analyzed"):
                    if st.button("⚡ 对质 CORRELATE", key=f"conf_{ev['evidence_id']}", use_container_width=True):
                        # 将证物对象暂存，dialogue_panel 发送对话时读取
                        st.session_state["confrontation_evidence"] = dict(ev)
                        st.toast(f"已选中证物 [{ev['name']}]，请在审讯中发送对话进行对质。", icon="⚡")
                        st.rerun()