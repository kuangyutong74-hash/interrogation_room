"""
游戏会话状态管理器
职责：
  1. 新游戏初始化（调用 B 的剧本生成器写入数据库）
  2. 启动 C 的法医异步调度器
  3. 从 SQLite 刷新数据到 Streamlit session_state
"""
import streamlit as st
from database.db_helper import DBHelper
from agents.script_generator import ScriptGenerator
from agents.forensic_agent import ForensicAgent


class GameSessionManager:
    """统一管理游戏生命周期与前后端状态同步"""

    def start_new_game(self, style: str = "manor") -> str:
        """
        生成剧本 → 写入 SQLite → 启动法医后台线程 → 初始化 SessionState。
        返回创建的 session_id。
        """
        generator = ScriptGenerator()
        session_id, case_dict = generator.generate_and_save(style)

        # --- Streamlit 状态初始化 ---
        st.session_state["session_id"] = session_id
        st.session_state["current_suspect_id"] = "suspect_a"
        st.session_state["seen_forensic_ids"] = set()
        st.session_state["case_closed"] = False
        st.session_state["stamp_anim"] = None
        st.session_state["need_approval"] = False
        st.session_state["selected_evidence_id"] = None
        st.session_state["confrontation_evidence"] = None
        st.session_state["_last_refreshed_suspect_id"] = None

        # --- 启动法医异步调度器（后台守护线程）---
        fa = ForensicAgent(session_id=session_id)
        fa.start_scheduler()
        st.session_state["forensic_agent"] = fa

        # --- Demo 阶段简化：自动发现所有剧本证物 ---
        all_ev = DBHelper.get_all_evidences(session_id)
        for ev in all_ev:
            DBHelper.discover_evidence(session_id, ev["evidence_id"])

        return session_id

    def refresh_all(self) -> None:
        """
        从 SQLite 读取最新数据，写入 Streamlit session_state。
        每次页面刷新（rerun）时由 app.py 调用。
        """
        sid = st.session_state.get("session_id")
        if not sid:
            return

        suspect_id = st.session_state.get("current_suspect_id", "suspect_a")

        # ── 关键修复：只在切换嫌疑人时重置选中态 ──
        last_suspect = st.session_state.get("_last_refreshed_suspect_id")
        if last_suspect != suspect_id:
            st.session_state["confrontation_evidence"] = None
            st.session_state["selected_evidence_id"] = None
            st.session_state["_last_refreshed_suspect_id"] = suspect_id

        # 1. 嫌疑人状态（含 profile_json、expression_state）
        suspect = DBHelper.get_suspect(sid, suspect_id)
        st.session_state["current_suspect"] = suspect or {}
        st.session_state["defense_score"] = suspect["defense_score"] if suspect else 100

        # 2. 已发现证物（保留选中态，不要覆盖）
        st.session_state["evidences"] = DBHelper.get_discovered_evidences(sid)

        # 3. 当前嫌疑人的对话历史
        st.session_state["chat_history"] = DBHelper.get_session_messages(sid, suspect_id)

        # 4. 会话元数据（行动点、审批标记、阶段）
        session = DBHelper.get_session(sid)
        if session:
            st.session_state["action_points"] = session["current_action_points"]
            st.session_state["need_approval"] = bool(session["need_approval"])
            st.session_state["phase"] = session["phase"]