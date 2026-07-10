"""
数据库底层读写接口 — SQLite CRUD 封装
对应技术文档 第七章 + 成员 A 分工

设计原则：
  - 所有方法均为静态或类方法，外部无需实例化即可调用
  - 连接通过 context manager 自动管理，防止泄漏
  - 各模块通过读写本模块提供的接口进行解耦，不互相调用类方法
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, Any

from config import DB_PATH


# ── 内部工具 ──────────────────────────────────────────────

def _ensure_dir() -> None:
    """确保数据库文件所在目录存在"""
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def _get_conn():
    """获取数据库连接的上下文管理器"""
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _load_schema(conn: sqlite3.Connection) -> None:
    """从 schema.sql 加载建表脚本"""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn.executescript(sql)


# ── 公共 API ──────────────────────────────────────────────

class DBHelper:
    """
    数据库读写帮助类。
    所有方法为类方法，通过 _get_conn() 自动管理连接生命周期。
    外部使用示例:
        from database.db_helper import DBHelper
        DBHelper.init_db()
        DBHelper.create_session("sess_001", "manor", "庄园谋杀案")
    """

    # ── 初始化 ────────────────────────────────────────────

    @classmethod
    def init_db(cls) -> None:
        """初始化数据库：执行 schema.sql 建表（幂等，已有表不重复创建）"""
        with _get_conn() as conn:
            _load_schema(conn)

    @classmethod
    def reset_db(cls) -> None:
        """清空所有数据（仅测试用）"""
        with _get_conn() as conn:
            tables = [
                "lie_ledger", "forensic_queue", "chat_history",
                "evidence_inventory", "suspect_status", "case_session",
            ]
            for t in tables:
                conn.execute(f"DELETE FROM {t}")
        print("[DBHelper] All tables cleared.")

    # ── case_session CRUD ────────────────────────────────

    @classmethod
    def create_session(cls, session_id: str, case_style: str,
                       case_name: str = "", action_points: int = 10) -> None:
        """创建新游戏会话"""
        with _get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO case_session
                   (session_id, case_style, case_name, current_action_points)
                   VALUES (?, ?, ?, ?)""",
                (session_id, case_style, case_name, action_points)
            )

    @classmethod
    def get_session(cls, session_id: str) -> Optional[dict]:
        """获取会话完整状态"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM case_session WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    @classmethod
    def update_session(cls, session_id: str, **kwargs) -> None:
        """按关键字更新会话字段。示例: DBHelper.update_session(sid, phase='verdict')"""
        allowed = {
            "case_style", "case_name", "current_action_points",
            "current_suspect_id", "phase", "need_approval",
            "is_completed", "updated_at"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = "datetime('now', 'localtime')"
        set_clause = ", ".join(
            f"{k} = {v}" if "datetime" in str(v) else f"{k} = ?"
            for k, v in updates.items()
        )
        values = [v for k, v in updates.items() if "datetime" not in str(v)]
        with _get_conn() as conn:
            conn.execute(
                f"UPDATE case_session SET {set_clause} WHERE session_id = ?",
                values + [session_id]
            )

    @classmethod
    def update_action_points(cls, session_id: str, delta: int) -> int:
        """修改行动点数（正数为增加，负数为消耗），返回剩余值"""
        with _get_conn() as conn:
            conn.execute(
                """UPDATE case_session
                   SET current_action_points = MAX(0, current_action_points + ?),
                       updated_at = datetime('now', 'localtime')
                   WHERE session_id = ?""",
                (delta, session_id)
            )
            row = conn.execute(
                "SELECT current_action_points FROM case_session WHERE session_id = ?",
                (session_id,)
            ).fetchone()
        return row["current_action_points"] if row else 0

    @classmethod
    def set_need_approval(cls, session_id: str, flag: bool) -> None:
        """设置人机协同拦截标记 (Human-in-the-loop)"""
        with _get_conn() as conn:
            conn.execute(
                """UPDATE case_session
                   SET need_approval = ?, updated_at = datetime('now', 'localtime')
                   WHERE session_id = ?""",
                (int(flag), session_id)
            )

    # ── suspect_status CRUD ──────────────────────────────

    @classmethod
    def upsert_suspect(cls, session_id: str, suspect_id: str,
                       name: str, role: str = "", avatar: str = "",
                       profile_json: str = "{}") -> None:
        """插入或更新嫌疑人状态"""
        with _get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO suspect_status
                   (session_id, suspect_id, name, role, avatar, profile_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, suspect_id, name, role, avatar, profile_json)
            )

    @classmethod
    def get_suspect(cls, session_id: str, suspect_id: str) -> Optional[dict]:
        """获取单个嫌疑人完整状态"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM suspect_status WHERE session_id = ? AND suspect_id = ?",
                (session_id, suspect_id)
            ).fetchone()
        return dict(row) if row else None

    @classmethod
    def get_all_suspects(cls, session_id: str) -> list[dict]:
        """获取当前会话全部嫌疑人"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM suspect_status WHERE session_id = ?",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def update_defense_score(cls, session_id: str, suspect_id: str,
                             delta: int) -> int:
        """
        更新心理防线分数（正数为恢复，负数为扣减）。
        返回更新后的值（钳制在 0-100）。
        """
        with _get_conn() as conn:
            conn.execute(
                """UPDATE suspect_status
                   SET defense_score = MAX(0, MIN(100, defense_score + ?))
                   WHERE session_id = ? AND suspect_id = ?""",
                (delta, session_id, suspect_id)
            )
            row = conn.execute(
                "SELECT defense_score FROM suspect_status WHERE session_id = ? AND suspect_id = ?",
                (session_id, suspect_id)
            ).fetchone()
        new_score = row["defense_score"] if row else 100
        # 自动同步表情状态
        cls._sync_expression(session_id, suspect_id, new_score)
        return new_score

    @classmethod
    def set_defense_score(cls, session_id: str, suspect_id: str,
                          score: int) -> None:
        """直接设置心理防线分数（钳制 0-100），自动同步表情"""
        clamped = max(0, min(100, score))
        with _get_conn() as conn:
            conn.execute(
                "UPDATE suspect_status SET defense_score = ? WHERE session_id = ? AND suspect_id = ?",
                (clamped, session_id, suspect_id)
            )
        cls._sync_expression(session_id, suspect_id, clamped)

    @classmethod
    def update_expression(cls, session_id: str, suspect_id: str,
                          expression: str) -> None:
        """手动设置嫌疑人表情状态: calm / nervous / broken"""
        valid = {"calm", "nervous", "broken"}
        if expression not in valid:
            raise ValueError(f"expression must be one of {valid}, got '{expression}'")
        with _get_conn() as conn:
            conn.execute(
                "UPDATE suspect_status SET expression_state = ? WHERE session_id = ? AND suspect_id = ?",
                (expression, session_id, suspect_id)
            )

    @classmethod
    def _sync_expression(cls, session_id: str, suspect_id: str,
                         defense_score: int) -> None:
        """根据防线分数自动推导并写入表情状态"""
        if defense_score >= 70:
            expr = "calm"
        elif defense_score >= 40:
            expr = "nervous"
        else:
            expr = "broken"
        with _get_conn() as conn:
            conn.execute(
                "UPDATE suspect_status SET expression_state = ? WHERE session_id = ? AND suspect_id = ?",
                (expr, session_id, suspect_id)
            )

    # ── evidence_inventory CRUD ──────────────────────────

    @classmethod
    def upsert_evidence(cls, session_id: str, evidence_id: str,
                        name: str, description: str = "",
                        category: str = "physical",
                        related_suspect_id: Optional[str] = None) -> None:
        """插入或更新证物"""
        with _get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO evidence_inventory
                   (session_id, evidence_id, name, description, category, related_suspect_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, evidence_id, name, description, category, related_suspect_id)
            )

    @classmethod
    def get_evidence(cls, session_id: str, evidence_id: str) -> Optional[dict]:
        """获取单个证物"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_inventory WHERE session_id = ? AND evidence_id = ?",
                (session_id, evidence_id)
            ).fetchone()
        return dict(row) if row else None

    @classmethod
    def get_all_evidences(cls, session_id: str) -> list[dict]:
        """获取当前会话全部证物"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_inventory WHERE session_id = ?",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def get_discovered_evidences(cls, session_id: str) -> list[dict]:
        """仅获取已被玩家发现的证物"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_inventory WHERE session_id = ? AND is_discovered = 1",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def discover_evidence(cls, session_id: str, evidence_id: str) -> None:
        """将证物标记为已发现"""
        with _get_conn() as conn:
            conn.execute(
                "UPDATE evidence_inventory SET is_discovered = 1 WHERE session_id = ? AND evidence_id = ?",
                (session_id, evidence_id)
            )

    @classmethod
    def mark_evidence_analyzed(cls, session_id: str, evidence_id: str,
                               result: str) -> None:
        """标记法医化验完成并写入结果"""
        with _get_conn() as conn:
            conn.execute(
                """UPDATE evidence_inventory
                   SET is_analyzed = 1, analysis_result = ?, analysis_pending = 0
                   WHERE session_id = ? AND evidence_id = ?""",
                (result, session_id, evidence_id)
            )

    @classmethod
    def submit_for_analysis(cls, session_id: str, evidence_id: str) -> None:
        """将证物送检（标记为 pending）"""
        with _get_conn() as conn:
            conn.execute(
                "UPDATE evidence_inventory SET analysis_pending = 1 WHERE session_id = ? AND evidence_id = ?",
                (session_id, evidence_id)
            )

    @classmethod
    def get_evidence_count(cls, session_id: str) -> int:
        """获取已发现证物数量（供 GM 拦截判定用）"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM evidence_inventory WHERE session_id = ? AND is_discovered = 1",
                (session_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    @classmethod
    def get_analyzed_evidence_count(cls, session_id: str) -> int:
        """获取已完成法医化验的证物数量"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM evidence_inventory WHERE session_id = ? AND is_analyzed = 1",
                (session_id,)
            ).fetchone()
        return row["cnt"] if row else 0

    # ── chat_history CRUD ────────────────────────────────

    @classmethod
    def add_message(cls, session_id: str, role: str, content: str,
                    suspect_id: Optional[str] = None) -> int:
        """写入一条对话记录，返回自增 ID"""
        with _get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO chat_history (session_id, suspect_id, role, content)
                   VALUES (?, ?, ?, ?)""",
                (session_id, suspect_id, role, content)
            )
            return cur.lastrowid

    @classmethod
    def get_recent_messages(cls, session_id: str, suspect_id: Optional[str] = None,
                            limit: int = 10) -> list[dict]:
        """
        获取最近 N 条对话（默认 10 条，对应 ConversationBufferWindowMemory）。
        可按 suspect_id 过滤。
        """
        with _get_conn() as conn:
            if suspect_id:
                rows = conn.execute(
                    """SELECT * FROM chat_history
                       WHERE session_id = ? AND suspect_id = ?
                       ORDER BY id DESC LIMIT ?""",
                    (session_id, suspect_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM chat_history
                       WHERE session_id = ?
                       ORDER BY id DESC LIMIT ?""",
                    (session_id, limit)
                ).fetchall()
        # 反转以保持时间正序
        return [dict(r) for r in reversed(rows)]

    @classmethod
    def get_session_messages(cls, session_id: str,
                             suspect_id: Optional[str] = None) -> list[dict]:
        """获取全部对话记录"""
        with _get_conn() as conn:
            if suspect_id:
                rows = conn.execute(
                    "SELECT * FROM chat_history WHERE session_id = ? AND suspect_id = ? ORDER BY id ASC",
                    (session_id, suspect_id)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chat_history WHERE session_id = ? ORDER BY id ASC",
                    (session_id,)
                ).fetchall()
        return [dict(r) for r in rows]

    # ── forensic_queue CRUD ──────────────────────────────

    @classmethod
    def enqueue_forensic(cls, session_id: str, evidence_id: str) -> int:
        """
        提交法医化验任务到异步队列，返回任务 ID。
        同时将对应证物的 analysis_pending 置为 1。
        """
        cls.submit_for_analysis(session_id, evidence_id)
        with _get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO forensic_queue (session_id, evidence_id, status)
                   VALUES (?, ?, 'pending')""",
                (session_id, evidence_id)
            )
            return cur.lastrowid

    @classmethod
    def get_pending_analyses(cls, session_id: str) -> list[dict]:
        """获取待处理的化验任务"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM forensic_queue WHERE session_id = ? AND status = 'pending'",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def start_analysis(cls, task_id: int) -> None:
        """将任务标记为 processing"""
        with _get_conn() as conn:
            conn.execute(
                "UPDATE forensic_queue SET status = 'processing' WHERE id = ?",
                (task_id,)
            )

    @classmethod
    def complete_analysis(cls, task_id: int, result: str) -> None:
        """
        完成化验任务：
        1. 更新 forensic_queue 状态 & 结果
        2. 同步更新 evidence_inventory 的 is_analyzed 和 analysis_result
        """
        with _get_conn() as conn:
            task = conn.execute(
                "SELECT * FROM forensic_queue WHERE id = ?", (task_id,)
            ).fetchone()
            if not task:
                return
            conn.execute(
                """UPDATE forensic_queue
                   SET status = 'completed', result = ?, completed_at = datetime('now', 'localtime')
                   WHERE id = ?""",
                (result, task_id)
            )
            conn.execute(
                """UPDATE evidence_inventory
                   SET is_analyzed = 1, analysis_result = ?, analysis_pending = 0
                   WHERE session_id = ? AND evidence_id = ?""",
                (result, task["session_id"], task["evidence_id"])
            )

    @classmethod
    def get_completed_notifications(cls, session_id: str) -> list[dict]:
        """
        获取已完成但尚未被前端拉取的通知（用于异步通知机制）。
        读取后不删除，前端自行判断展示逻辑。
        """
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM forensic_queue WHERE session_id = ? AND status = 'completed' ORDER BY completed_at DESC",
                (session_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── lie_ledger CRUD ──────────────────────────────────

    @classmethod
    def add_lie(cls, session_id: str, suspect_id: str, statement: str,
                contradiction: str = "", evidence_id: Optional[str] = None,
                defense_penalty: int = 15) -> int:
        """记录一条嫌疑人谎言"""
        with _get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO lie_ledger (session_id, suspect_id, statement, contradiction, evidence_id, defense_penalty)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, suspect_id, statement, contradiction, evidence_id, defense_penalty)
            )
            return cur.lastrowid

    @classmethod
    def get_lies_for_suspect(cls, session_id: str,
                             suspect_id: str) -> list[dict]:
        """获取某嫌疑人全部的谎言记录"""
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM lie_ledger WHERE session_id = ? AND suspect_id = ? ORDER BY id ASC",
                (session_id, suspect_id)
            ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def expose_lie(cls, lie_id: int) -> Optional[dict]:
        """
        揭穿一条谎言：
        1. 标记 is_exposed = 1
        2. 根据 defense_penalty 扣减对应嫌疑人的心理防线
        返回更新后的谎言记录
        """
        with _get_conn() as conn:
            conn.execute(
                "UPDATE lie_ledger SET is_exposed = 1 WHERE id = ?", (lie_id,)
            )
            row = conn.execute(
                "SELECT * FROM lie_ledger WHERE id = ?", (lie_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE suspect_status
                       SET defense_score = MAX(0, defense_score - ?)
                       WHERE session_id = ? AND suspect_id = ?""",
                    (row["defense_penalty"], row["session_id"], row["suspect_id"])
                )
        return dict(row) if row else None

    @classmethod
    def get_unexposed_lies(cls, session_id: str,
                           suspect_id: str) -> list[dict]:
        """获取尚未被揭穿的谎言列表"""
        with _get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM lie_ledger
                   WHERE session_id = ? AND suspect_id = ? AND is_exposed = 0
                   ORDER BY id ASC""",
                (session_id, suspect_id)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 聚合查询（供 GM Agent 使用）──────────────────────

    @classmethod
    def get_case_summary(cls, session_id: str) -> dict:
        """
        获取案件摘要，供警长主控 Agent 进行逻辑判定。
        返回：
          - session: 会话基本信息
          - suspects: 所有嫌疑人状态列表
          - discovered_evidences: 已发现证物
          - pending_forensics: 待完成的化验
          - recent_chat: 最近对话
        """
        with _get_conn() as conn:
            session = dict(conn.execute(
                "SELECT * FROM case_session WHERE session_id = ?", (session_id,)
            ).fetchone() or {})

            suspects = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM suspect_status WHERE session_id = ?", (session_id,)
                ).fetchall()
            ]

            evidences = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM evidence_inventory WHERE session_id = ? AND is_discovered = 1",
                    (session_id,)
                ).fetchall()
            ]

            pending = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM forensic_queue WHERE session_id = ? AND status != 'completed'",
                    (session_id,)
                ).fetchall()
            ]

            recent = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT 6",
                    (session_id,)
                ).fetchall()
            ][::-1]

        return {
            "session": session,
            "suspects": suspects,
            "discovered_evidences": evidences,
            "pending_forensics": pending,
            "recent_chat": recent,
        }


# ── 便捷初始化 ────────────────────────────────────────────

def initialize_database() -> None:
    """项目启动时调用：建表 + 确保数据库文件存在"""
    DBHelper.init_db()
    print(f"[DBHelper] Database initialized at: {os.path.abspath(DB_PATH)}")
