"""
盖章控制台（底栏）
功能：
  - 逮捕按钮：内联 GM 审批逻辑（证据链判定 + 防线判定）
  - 若证据不足，触发 Human-in-the-loop 拦截（need_approval）
  - 释放按钮：直接结案
  - 二次确认：玩家可在警告框中"强行盖章"
"""
import streamlit as st
from database.db_helper import DBHelper


def render():
    st.markdown("---")

    c1, c2, c3 = st.columns([1, 1, 2])

    session_id = st.session_state.get("session_id")
    suspect_id = st.session_state.get("current_suspect_id")

    with c1:
        if st.button("🔴 逮捕\nARREST", key="btn_arrest", use_container_width=True):
            # --- 内联 GM 审批逻辑（B 的 GMAgent 实现后可替换） ---
            summary = DBHelper.get_case_summary(session_id)
            analyzed_count = DBHelper.get_analyzed_evidence_count(session_id)
            suspect = DBHelper.get_suspect(session_id, suspect_id)
            defense_score = suspect["defense_score"] if suspect else 100

            evidence_count = len(summary.get("discovered_evidences", []))

            # 判定规则：已发现证物 >= 2 且 已化验 >= 1 且 防线 < 50
            approved = (evidence_count >= 2 and analyzed_count >= 1 and defense_score < 50)

            if not approved:
                DBHelper.set_need_approval(session_id, True)
                st.session_state["need_approval"] = True
                st.toast("⚠️ 警长拒绝：证据链不完整，强行逮捕将导致嫌疑人保释！", icon="🛑")
            else:
                st.session_state["stamp_anim"] = "arrest"
                st.session_state["case_closed"] = True
                st.balloons()
            st.rerun()

    with c2:
        if st.button("🟢 保释\nRELEASE", key="btn_release", use_container_width=True):
            st.session_state["stamp_anim"] = "release"
            st.session_state["case_closed"] = True
            st.rerun()

    with c3:
        # 人机协同拦截：显示警长书面警告
        if st.session_state.get("need_approval"):
            st.warning(
                "⚠️ **警长书面警告**：证据不足以获得搜查令，强行逮捕可能导致嫌疑人保释并投诉我们。\n\n"
                "**确定要签字吗？**"
            )
            if st.button("确认强行盖章", key="force_arrest"):
                DBHelper.set_need_approval(session_id, False)
                st.session_state["need_approval"] = False
                st.session_state["stamp_anim"] = "arrest"
                st.session_state["case_closed"] = True
                st.rerun()
        else:
            st.markdown("**案件结论决定书**")
            analyzed = DBHelper.get_analyzed_evidence_count(session_id)
            st.caption(f"当前证据链完整度：{analyzed}/3（已化验证物）")