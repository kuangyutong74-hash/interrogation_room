"""
法医异步化验模块自测脚本 — 成员 C 使用
验证 forensic_agent.py 全部功能：
  1. 五项分析技能独立运行（Part 1）
  2. 异步调度器启动/停止（Part 2, ForensicAgent）
  3. 主线程非阻塞验证
  4. 数据库自动回写验证

运行方式:
    cd interrogation_room
    python tests/test_forensic.py
"""

import sys
import os
import time
import json

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_helper import DBHelper, initialize_database
from agents.forensic_agent import (
    ForensicAgent,
    run_analysis,
    list_available_skills,
    SKILL_FUNCTIONS,
)

TEST_SESSION = "test_forensic_001"


def print_result(name: str, ok: bool, detail: str = "") -> None:
    """统一输出格式"""
    status = "[PASS]" if ok else "[FAIL]"
    extra = f"  -> {detail}" if detail else ""
    print(f"{status} {name}{extra}")


# ══════════════════════════════════════════════════════════════
#  Setup: 准备测试环境
# ══════════════════════════════════════════════════════════════

def setup_test_env():
    """初始化数据库并创建测试用例"""
    initialize_database()

    # 创建测试会话
    DBHelper.create_session(TEST_SESSION, "manor", "法医自测案件", action_points=10)

    # 创建嫌疑人
    profile_a = json.dumps({
        "alibi": "我在实验室工作",
        "hidden_truth": "我偷偷去了现场",
        "weakness_item": "evidence_1",
        "weakness_description": "凶器上有指纹",
    }, ensure_ascii=False)
    DBHelper.upsert_suspect(
        TEST_SESSION, "suspect_a", "伊索尔德·影焰",
        role="炼金术师", profile_json=profile_a
    )
    DBHelper.upsert_suspect(
        TEST_SESSION, "suspect_b", "塞德里克·铁卫",
        role="护卫队长", profile_json="{}"
    )

    # 创建证物（覆盖五种技能所需的类别）
    DBHelper.upsert_evidence(
        TEST_SESSION, "evidence_1", "沾有霜冻魔力的银白短箭",
        description="贯穿死者胸口的凶器。箭尖上除血迹外还沾有微量月影草汁液。",
        category="weapon", related_suspect_id="suspect_a"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "evidence_2", "高塔彩色玻璃窗上的指纹",
        description="窗户内侧窗框发现一枚清晰指纹。",
        category="document", related_suspect_id="suspect_b"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "evidence_3", "死者胃内容物样本",
        description="从死者胃部提取的残留物。",
        category="chemical", related_suspect_id="suspect_a"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "evidence_4", "案发现场的黑色玫瑰花瓣",
        description="干枯的黑色花瓣，带有异常魔力残留。",
        category="forensic", related_suspect_id="suspect_a"
    )
    DBHelper.upsert_evidence(
        TEST_SESSION, "evidence_5", "嫌疑人衣物纤维样本",
        description="从嫌疑人衣物上采集的纤维。",
        category="physical", related_suspect_id="suspect_b"
    )

    # 标记为已发现
    for eid in ["evidence_1", "evidence_2", "evidence_3", "evidence_4", "evidence_5"]:
        DBHelper.discover_evidence(TEST_SESSION, eid)

    print_result("测试环境初始化", True, f"5件证物 + 2名嫌疑人")


# ══════════════════════════════════════════════════════════════
#  Test 1: 技能函数独立测试
# ══════════════════════════════════════════════════════════════

def test_skill_fingerprint():
    """指纹匹配技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_2")
    result = fingerprint_match(evidence, TEST_SESSION)
    assert "指纹匹配报告" in result, "报告标题缺失"
    assert evidence["name"] in result, "应包含证物名称"
    assert "塞德里克" in result or "suspect_b" in result, "应包含嫌疑人信息"
    ok = "指纹匹配报告" in result and len(result) > 100
    print_result("fingerprint_match", ok, f"报告长度={len(result)}字")


def test_skill_blood_analysis():
    """血迹分析技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_1")
    result = blood_analysis(evidence, TEST_SESSION)
    assert "血迹分析报告" in result
    ok = "血迹分析报告" in result and "证物" in result
    print_result("blood_analysis", ok, f"报告长度={len(result)}字")


def test_skill_document_verify():
    """文件鉴定技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_2")
    result = document_verify(evidence, TEST_SESSION)
    assert "文件鉴定报告" in result
    ok = "文件鉴定报告" in result and "笔迹特征分析" in result
    print_result("document_verify", ok, f"报告长度={len(result)}字")


def test_skill_toxicology():
    """毒物化验技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_3")
    result = toxicology_report(evidence, TEST_SESSION)
    assert "毒物分析报告" in result
    ok = "毒物分析报告" in result and "GC-MS" in result
    print_result("toxicology_report", ok, f"报告长度={len(result)}字")


def test_skill_trace_analysis():
    """微量痕迹分析技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_5")
    result = trace_analysis(evidence, TEST_SESSION)
    assert "微量痕迹分析报告" in result
    ok = "微量痕迹分析报告" in result and "SEM" in result
    print_result("trace_analysis", ok, f"报告长度={len(result)}字")


def test_run_analysis_auto_skill():
    """自动选择技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_4")  # forensic 类
    result = run_analysis(evidence, session_id=TEST_SESSION)
    assert "skill" in result
    assert "result" in result
    assert "evidence_id" in result
    assert "duration" in result
    assert result["evidence_id"] == "evidence_4"
    ok = (
        result["skill"] in SKILL_FUNCTIONS
        and len(result["result"]) > 50
    )
    print_result("自动技能选择", ok, f"类别=forensic → {result['skill']}")


def test_run_analysis_specific_skill():
    """指定技能"""
    evidence = DBHelper.get_evidence(TEST_SESSION, "evidence_1")
    result = run_analysis(evidence, skill="toxicology_report", session_id=TEST_SESSION)
    assert result["skill"] == "toxicology_report"
    assert "毒物分析报告" in result["result"]
    ok = result["skill"] == "toxicology_report"
    print_result("指定技能运行", ok, f"手动指定 toxicology_report 成功")


# ══════════════════════════════════════════════════════════════
#  Test 2: ForensicAgent 提交与校验
# ══════════════════════════════════════════════════════════════

def test_agent_submit_analysis():
    """提交化验任务"""
    agent = ForensicAgent(session_id=TEST_SESSION)

    task_id = agent.submit_analysis("evidence_1")
    assert task_id > 0, "任务 ID 应大于 0"
    print_result("提交化验任务", True, f"task_id={task_id}")

    # 重复提交应抛出异常
    try:
        agent.submit_analysis("evidence_1")
        print_result("重复提交拦截", False, "应抛出 ValueError")
    except ValueError as e:
        print_result("重复提交拦截", True, str(e)[:50])

    # clean: 移除刚才提交的任务以便后续测试
    DBHelper.complete_analysis(task_id, "[自测] 清理用")
    return agent


def test_agent_submit_batch():
    """批量提交化验任务"""
    agent = ForensicAgent(session_id=TEST_SESSION)
    task_ids = agent.submit_analysis_batch([
        "evidence_2", "evidence_3", "evidence_4", "evidence_5"
    ])
    assert len(task_ids) >= 3, f"至少 3 件应提交成功: 实际 {len(task_ids)}"

    # clean
    for tid in task_ids:
        DBHelper.complete_analysis(tid, "[自测] 批量清理用")
    print_result("批量提交化验", True, f"成功提交 {len(task_ids)} 件")


def test_agent_validation():
    """输入校验"""
    agent = ForensicAgent(session_id=TEST_SESSION)

    # 不存在的证物
    try:
        agent.submit_analysis("evidence_nonexist")
        print_result("无效证物校验", False, "应抛出 ValueError")
    except ValueError:
        print_result("无效证物校验", True, "不存在的证物正确拒绝")


# ══════════════════════════════════════════════════════════════
#  Test 3: 异步调度器 — 非阻塞 & 自动回写
# ══════════════════════════════════════════════════════════════

def test_scheduler_non_blocking():
    """
    核心测试：验证后台调度器运行时不阻塞主线程。
    在化验进行期间，主线程可以继续执行其他操作。
    """
    print()
    print("─" * 50)
    print("  异步调度器核心测试（约 15 秒）")
    print("─" * 50)

    # ── 使用独立 session，彻底隔离前序测试影响 ──
    SESS = "test_scheduler_isolated"
    DBHelper.create_session(SESS, "manor", "调度器隔离测试", action_points=10)
    DBHelper.upsert_suspect(SESS, "suspect_a", "测试嫌疑人A", role="管家", profile_json="{}")
    DBHelper.upsert_evidence(
        SESS, "ev_test", "测试证物",
        description="用于调度器测试的证物",
        category="weapon", related_suspect_id="suspect_a"
    )
    DBHelper.discover_evidence(SESS, "ev_test")

    agent = ForensicAgent(session_id=SESS)

    # 提交一个化验任务
    task_id = agent.submit_analysis("ev_test")
    assert task_id > 0

    # 启动调度器
    agent.start_scheduler()
    assert agent.is_running, "调度器应处于运行状态"
    print_result("调度器启动", True, f"is_running={agent.is_running}")

    # ★ 关键验证：在化验期间，主线程可以执行其他操作 ★
    print()
    print("  >>> 主线程非阻塞验证：化验进行期间执行其他操作...")

    busy_checks = []
    for i in range(3):
        time.sleep(2)  # 每 2 秒检查一次
        summary = agent.get_queue_summary()
        completed = agent.get_completed_results()

        has_completed = summary["completed"] > 0
        busy_checks.append({
            "round": i + 1,
            "elapsed": (i + 1) * 2,
            "pending": summary["pending"],
            "processing": summary["processing"],
            "completed": summary["completed"],
            "has_result": has_completed,
        })
        print(
            f"     [{i+1}] {(i+1)*2}s 后: "
            f"pending={summary['pending']}, "
            f"processing={summary['processing']}, "
            f"completed={summary['completed']}"
        )

    # 等待化验完成（最多 40 秒，足够覆盖 18s 最慢技能）
    print()
    print("  >>> 等待化验完成...")
    completed_before = len(agent.get_completed_results())
    wait_start = time.time()
    result_found = False
    while time.time() - wait_start < 40:
        time.sleep(1)
        if not agent.is_running:
            print("     (调度器意外停止)")
            break
        completed = agent.get_completed_results()
        # 检查是否有新增的已完成任务（含"报告"关键词）
        new_completed = [c for c in completed if "报告" in (c.get("result") or "")]
        if len(new_completed) > 0:
            result_found = True
            break

    elapsed = time.time() - wait_start
    agent.stop_scheduler()

    # 验证数据库已自动更新
    evidence = DBHelper.get_evidence(SESS, "ev_test")
    is_analyzed = evidence["is_analyzed"] == 1
    has_result = evidence.get("analysis_result", "") != ""
    contains_report = "报告" in (evidence.get("analysis_result") or "")

    print()
    print_result(
        "数据库自动回写 (is_analyzed)", is_analyzed,
        f"is_analyzed={evidence['is_analyzed']}"
    )
    print_result(
        "化验报告内容正确", contains_report,
        (evidence.get("analysis_result") or "N/A")[:80] + "..."
    )

    # 总结非阻塞验证
    all_non_blocking = len(busy_checks) == 3 and all(
        c["processing"] >= 0 for c in busy_checks
    )
    print_result(
        "主线程非阻塞验证",
        all_non_blocking and result_found and is_analyzed and contains_report,
        f"化验期间主线程执行了 {len(busy_checks)} 次状态查询, "
        f"任务耗时 {elapsed:.0f}s"
    )

    return agent


def test_scheduler_stop_restart():
    """调度器停止与重启"""
    agent = ForensicAgent(session_id=TEST_SESSION)

    agent.start_scheduler()
    assert agent.is_running
    print_result("调度器启动", True)

    agent.stop_scheduler()
    assert not agent.is_running
    print_result("调度器停止", True)

    # 重启
    agent.start_scheduler()
    assert agent.is_running
    agent.stop_scheduler()
    print_result("调度器重启", True)


# ══════════════════════════════════════════════════════════════
#  Test 4: 同步技能 & 上下文管理器
# ══════════════════════════════════════════════════════════════

def test_run_skill_now():
    """同步直接分析（不经队列）"""
    agent = ForensicAgent(session_id=TEST_SESSION)
    result = agent.run_skill_now("evidence_3")
    assert "skill" in result
    assert "result" in result
    assert result["evidence_id"] == "evidence_3"
    ok = len(result["result"]) > 50
    print_result("run_skill_now 同步分析", ok, f"技能={result['skill']}")


def test_context_manager():
    """with 语句自动管理调度器生命周期"""
    with ForensicAgent(session_id=TEST_SESSION) as agent:
        assert agent.is_running
    assert not agent.is_running
    print_result("with 上下文管理器", True, "自动启动/停止正常")


def test_queue_summary():
    """队列状态摘要"""
    agent = ForensicAgent(session_id=TEST_SESSION)
    summary = agent.get_queue_summary()
    required_keys = {"pending", "processing", "completed", "total", "scheduler_running"}
    ok = all(k in summary for k in required_keys)
    print_result(
        "队列状态摘要", ok,
        f"total={summary['total']}, scheduler_running={summary['scheduler_running']}"
    )


# ══════════════════════════════════════════════════════════════
#  Test 5: 辅助函数
# ══════════════════════════════════════════════════════════════

def test_list_skills():
    """技能列表"""
    info = list_available_skills()
    assert "skills" in info
    assert len(info["skills"]) == 5
    assert "fingerprint_match" in info["skills"]
    print_result("技能列表", True, f"共 {len(info['skills'])} 项技能")


# ══════════════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  法医异步化验模块自测 (ForensicAgent)")
    print("=" * 60)

    # Setup
    print()
    print(">>> 环境初始化 <<<")
    setup_test_env()

    # Test 1: 技能函数
    print()
    print(">>> Test 1: 五项分析技能 <<<")
    from agents.forensic_agent import (
        fingerprint_match, blood_analysis, document_verify,
        toxicology_report, trace_analysis,
    )
    test_skill_fingerprint()
    test_skill_blood_analysis()
    test_skill_document_verify()
    test_skill_toxicology()
    test_skill_trace_analysis()
    test_run_analysis_auto_skill()
    test_run_analysis_specific_skill()

    # Test 2: 提交与校验
    print()
    print(">>> Test 2: 提交与校验 <<<")
    test_agent_submit_analysis()
    test_agent_submit_batch()
    test_agent_validation()

    # Test 3: 异步调度器（核心测试，耗时较长）
    print()
    print(">>> Test 3: 异步调度器 <<<")
    test_scheduler_stop_restart()
    test_scheduler_non_blocking()

    # Test 4: 辅助功能
    print()
    print(">>> Test 4: 辅助功能 <<<")
    test_run_skill_now()
    test_context_manager()
    test_queue_summary()

    # Test 5: 技能列表
    print()
    print(">>> Test 5: 技能列表 <<<")
    test_list_skills()

    print()
    print("=" * 60)
    print("  全部自测完成")
    print("=" * 60)
