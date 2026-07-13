"""
法医报告异步弹窗（时序打断）
功能：
  - 轮询 forensic_agent.get_completed_results()
  - 新报告送达时，渲染全屏遮罩弹窗（复古红色法医报告）
  - 玩家点击"已阅"后，报告落入证物抽屉（通过数据库刷新自动展示）
"""
import streamlit as st


def check_and_render():
    """检查是否有未展示的法医报告，如有则渲染弹窗"""
    fa = st.session_state.get("forensic_agent")
    if not fa:
        return

    seen = st.session_state.get("seen_forensic_ids", set())
    completed = fa.get_completed_results()

    # 筛选未展示的新报告
    new_reports = [t for t in completed if t["id"] not in seen]
    if not new_reports:
        return

    # 只展示最新一份（避免堆叠）
    task = new_reports[0]
    seen.add(task["id"])

    # 全屏遮罩 + 复古报告卡片（HTML 层）
    popup_html = f"""
    <div style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.85); z-index:9999; display:flex; align-items:center; justify-content:center;">
        <div style="background:#f4f1e8; color:#1a1a1a; border:4px solid #c62828; padding:30px; max-width:500px; width:90%; box-shadow:0 0 30px rgba(198,40,40,0.6); font-family:'Courier New', monospace;">
            <div style="color:#c62828; font-weight:bold; font-size:1.3rem; margin-bottom:10px; text-align:center;">
                ⚠️ 法医实验室紧急报告送达
            </div>
            <div style="border:2px solid #333; padding:10px; background:#fff; margin-bottom:15px;">
                <div><b>检材编号：</b>{task['evidence_id']}</div>
                <div style="margin-top:8px; white-space:pre-wrap; font-size:0.9rem;">{task['result']}</div>
                <div style="text-align:right; font-size:0.8rem; color:#555; margin-top:10px;">
                    完成时间：{task.get('completed_at', '未知')}
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(popup_html, unsafe_allow_html=True)

    # Streamlit 原生按钮必须放在 HTML 外部才能触发回调
    cols = st.columns([1, 1, 1])
    with cols[1]:
        if st.button("📋 已阅 / 呈交桌面", key=f"read_forensic_{task['id']}"):
            # 刷新页面，evidence_panel 会自动从数据库读取到新的 analysis_result
            st.rerun()