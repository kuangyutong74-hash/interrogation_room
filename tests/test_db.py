"""
数据库模块自测脚本 — 成员 A 使用
验证 schema.sql 建表 + db_helper 全部 CRUD 接口

运行方式:
    cd interrogation_room
    python tests/test_db.py
"""

import sys
import os
import json

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_helper import DBHelper, initialize_database


TEST_SESSION = "test_sess_001"


def print_result(name: str, ok: bool, detail: str = "") -> None:
    """统一输出格式"""
    status = "[PASS]" if ok else "[FAIL]"
    extra = f"  -> {detail}" if detail else ""
    print(f"{status} {name}{extra}")


def test_init():
    """初始化数据库"""
    initialize_database()
    print_result("数据库初始化", True)


def test_session_crud():
    """会话 CRUD"""
    DBHelper.reset_db()

    # 创建
    DBHelper.create_session(TEST_SESSION, "manor", "庄园谋杀案", action_points=10)
    sess = DBHelper.get_session(TEST_SESSION)
    assert sess is not None, "创建后 session 不应为空"
    assert sess["case_style"] == "manor"
    assert sess["current_action_points"] == 10
    print_result("创建会话", True, f"session_id={TEST_SESSION}")

    # 更新行动点
    remaining = DBHelper.update_action_points(TEST_SESSION, -2)
    assert remaining == 8, f"应剩余 8 点，实际 {remaining}"
    print_result("消耗行动点", True, f"10 - 2 = {remaining}")

    # 设置拦截标记
    DBHelper.set_need_approval(TEST_SESSION, True)
    sess = DBHelper.get_session(TEST_SESSION)
    assert sess["need_approval"] == 1
    print_result("人机协同拦截标记", True)

    # 更新阶段
    DBHelper.update_session(TEST_SESSION, phase="interrogation", current_suspect_id="s_01")
    sess = DBHelper.get_session(TEST_SESSION)
    assert sess["phase"] == "interrogation"
    assert sess["current_suspect_id"] == "s_01"
    print_result("更新会话阶段", True)


def test_suspect_crud():
    """嫌疑人 CRUD"""
    profile = json.dumps({
        "name": "塞巴斯蒂安",
        "role": "庄园管家",
        "base_defense": 100,
        "hidden_truth": "九点整我确实去了酒窖，但我是在藏匿带血的开瓶器",
        "alibi": "我在酒窖里整理2005年的拉菲",
        "weakness": "无法解释为什么开瓶器上会有死者的皮屑组织"
    }, ensure_ascii=False)

    # 插入
    DBHelper.upsert_suspect(
        TEST_SESSION, "s_01", "塞巴斯蒂安",
        role="管家", avatar="assets/images/suspect_a_calm.png",
        profile_json=profile
    )
    DBHelper.upsert_suspect(
        TEST_SESSION, "s_02", "亨利·艾什福德",
        role="富商", avatar="assets/images/suspect_b_calm.png",
        profile_json="{}"
    )

    suspects = DBHelper.get_all_suspects(TEST_SESSION)
    assert len(suspects) == 2, f"应有 2 个嫌疑人，实际 {len(suspects)}"
    print_result("插入嫌疑人", True, f"数量={len(suspects)}")

    # 读取单个
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["name"] == "塞巴斯蒂安"
    assert s["defense_score"] == 100
    assert s["expression_state"] == "calm"
    print_result("读取嫌疑人", True, s["name"])

    # 防线扣减 → 自动同步表情
    DBHelper.update_defense_score(TEST_SESSION, "s_01", -20)
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["defense_score"] == 80
    assert s["expression_state"] == "calm"  # 80 >= 70 → calm
    print_result("防线扣减 (100→80)", True, f"expression={s['expression_state']}")

    # 继续扣减到 nervous 区间
    DBHelper.update_defense_score(TEST_SESSION, "s_01", -30)
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["defense_score"] == 50
    assert s["expression_state"] == "nervous"
    print_result("防线扣减 (80→50)", True, f"expression={s['expression_state']}")

    # 扣到崩溃区间
    DBHelper.set_defense_score(TEST_SESSION, "s_01", 30)
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["expression_state"] == "broken"
    print_result("防线崩塌 (30)", True, f"expression={s['expression_state']}")

    # 表达式手动设置
    DBHelper.update_expression(TEST_SESSION, "s_01", "calm")
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["expression_state"] == "calm"
    print_result("手动设置表情", True)


def test_evidence_crud():
    """证物 CRUD"""
    DBHelper.upsert_evidence(
        TEST_SESSION, "ev_01", "带血的开瓶器",
        description="开瓶器上检测出受害者的A型血迹和管家的指纹",
        category="weapon", related_suspect_id="s_01"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "ev_02", "考勤记录卡",
        description="案发当晚的值班室打卡记录，显示管家在21:00-22:00期间未离开",
        category="document", related_suspect_id="s_01"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "ev_03", "遗书",
        description="死者留下的遗书，字迹疑似伪造",
        category="document", related_suspect_id="s_02"
    )

    all_ev = DBHelper.get_all_evidences(TEST_SESSION)
    assert len(all_ev) == 3
    print_result("插入证物", True, f"数量={len(all_ev)}")

    # 发现证物
    DBHelper.discover_evidence(TEST_SESSION, "ev_01")
    DBHelper.discover_evidence(TEST_SESSION, "ev_02")
    discovered = DBHelper.get_discovered_evidences(TEST_SESSION)
    assert len(discovered) == 2
    count = DBHelper.get_evidence_count(TEST_SESSION)
    assert count == 2
    print_result("发现证物", True, f"已发现={count}")

    # 送检 + 完成化验
    DBHelper.submit_for_analysis(TEST_SESSION, "ev_01")
    ev = DBHelper.get_evidence(TEST_SESSION, "ev_01")
    assert ev["analysis_pending"] == 1
    print_result("送检标记", True)

    DBHelper.mark_evidence_analyzed(
        TEST_SESSION, "ev_01",
        "【化验结果】开瓶器表面检出A型血迹（与死者一致），手柄处指纹与管家塞巴斯蒂安全匹配。"
    )
    ev = DBHelper.get_evidence(TEST_SESSION, "ev_01")
    assert ev["is_analyzed"] == 1
    assert "A型血迹" in ev["analysis_result"]
    print_result("化验完成", True, ev["analysis_result"][:30] + "...")


def test_chat_history():
    """对话历史"""
    DBHelper.add_message(TEST_SESSION, "player", "你在案发当晚去了哪里？", suspect_id="s_01")
    DBHelper.add_message(TEST_SESSION, "suspect", "我在酒窖整理红酒，一晚上没离开。", suspect_id="s_01")
    DBHelper.add_message(TEST_SESSION, "player", "可是考勤记录显示你在九点离开了值班室。", suspect_id="s_01")

    recent = DBHelper.get_recent_messages(TEST_SESSION, suspect_id="s_01", limit=5)
    assert len(recent) == 3
    assert recent[0]["content"] == "你在案发当晚去了哪里？"
    print_result("对话写入 & 记忆窗口", True, f"最近 {len(recent)} 条")

    all_msgs = DBHelper.get_session_messages(TEST_SESSION, suspect_id="s_01")
    assert len(all_msgs) == 3
    print_result("全量对话读取", True, f"共 {len(all_msgs)} 条")


def test_forensic_queue():
    """法医异步队列"""
    task_id = DBHelper.enqueue_forensic(TEST_SESSION, "ev_03")
    assert task_id > 0
    print_result("提交化验任务", True, f"task_id={task_id}")

    pending = DBHelper.get_pending_analyses(TEST_SESSION)
    assert any(t["id"] == task_id for t in pending)
    print_result("查询待处理任务", True, f"pending={len(pending)}")

    DBHelper.start_analysis(task_id)
    DBHelper.complete_analysis(task_id, "【化验结果】遗书字迹与富商亨利的笔迹样本匹配度 92%。")

    notifications = DBHelper.get_completed_notifications(TEST_SESSION)
    has_notification = any("笔迹样本" in (n["result"] or "") for n in notifications)
    assert has_notification
    print_result("化验完成通知", True, "遗书字迹分析完成")


def test_lie_ledger():
    """谎言追踪"""
    lie_id = DBHelper.add_lie(
        TEST_SESSION, "s_01",
        statement="我在酒窖整理红酒，一晚上没离开。",
        contradiction="考勤记录显示21:00-22:00期间管家未在值班室（离开岗位）",
        evidence_id="ev_02",
        defense_penalty=15
    )
    assert lie_id > 0
    print_result("记录谎言", True, f"lie_id={lie_id}")

    lies = DBHelper.get_lies_for_suspect(TEST_SESSION, "s_01")
    assert len(lies) == 1
    print_result("查询嫌疑人谎言", True, f"共 {len(lies)} 条")

    unexposed = DBHelper.get_unexposed_lies(TEST_SESSION, "s_01")
    assert len(unexposed) == 1
    print_result("未揭穿谎言", True, f"共 {len(unexposed)} 条")

    # 揭穿谎言 → 自动扣防线
    DBHelper.set_defense_score(TEST_SESSION, "s_01", 80)
    result = DBHelper.expose_lie(lie_id)
    s = DBHelper.get_suspect(TEST_SESSION, "s_01")
    assert s["defense_score"] == 65  # 80 - 15
    assert result["is_exposed"] == 1
    print_result("揭穿谎言 → 扣防线", True, f"80 → {s['defense_score']}")


def test_case_summary():
    """聚合查询"""
    summary = DBHelper.get_case_summary(TEST_SESSION)
    assert summary["session"]["session_id"] == TEST_SESSION
    assert len(summary["suspects"]) == 2
    assert len(summary["discovered_evidences"]) == 2
    assert len(summary["recent_chat"]) > 0
    print_result(
        "GM 案件摘要", True,
        f"session={summary['session']['case_name']}, "
        f"suspects={len(summary['suspects'])}, "
        f"evidences={len(summary['discovered_evidences'])}"
    )


# ── 主入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SQLite 数据库模块自测")
    print("=" * 60)

    test_init()
    print()
    test_session_crud()
    print()
    test_suspect_crud()
    print()
    test_evidence_crud()
    print()
    test_chat_history()
    print()
    test_forensic_queue()
    print()
    test_lie_ledger()
    print()
    test_case_summary()

    print()
    print("=" * 60)
    print("  全部自测完成")
    print("=" * 60)
