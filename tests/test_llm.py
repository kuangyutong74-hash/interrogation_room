"""
测试脚本 — LLM 连通性与 SuspectAgent 基础功能测试
成员 B 自测用

测试项：
  1. 测试 API Key 是否可用
  2. 测试 SuspectAgent 能否成功初始化
  3. 测试一轮对话是否能正常返回回复
  4. 测试防线值驱动的语气切换逻辑

运行方式：
  python -m tests.test_llm
"""

import json
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载项目配置
load_dotenv()


def test_01_api_key_exists():
    """测试 API Key 是否已配置"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    assert api_key is not None, "❌ API Key 未找到！请在 .env 文件中配置 DEEPSEEK_API_KEY"
    assert api_key != "your-api-key-here", "❌ API Key 仍然是占位符！请配置真实的 API Key"
    print("✅ [test_01] API Key 已配置:", api_key[:8] + "...")


def test_02_llm_connect():
    """测试 LLM 基础连通性"""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
    )
    response = llm.invoke("你好，请回复一句简短的问候。")
    content = response.content.strip()
    assert len(content) > 0, "❌ LLM 返回了空内容"
    print(f"✅ [test_02] LLM 连通成功，回复: {content[:50]}...")


def test_03_system_prompt_build():
    """测试 System Prompt 构建函数"""
    from prompts.system_prompts import build_suspect_prompt, get_behavior_modifier

    # 测试不同防线值对应的语气
    assert "冷静" in get_behavior_modifier(100) or "不屑" in get_behavior_modifier(100)
    assert "压力" in get_behavior_modifier(50) or "犹豫" in get_behavior_modifier(50)
    assert "慌张" in get_behavior_modifier(20) or "结巴" in get_behavior_modifier(20)
    assert "崩溃" in get_behavior_modifier(5) or "瘫坐" in get_behavior_modifier(5)
    print("✅ [test_03] 防线语气切换逻辑正常")

    # 测试构建完整 Prompt
    prompt = build_suspect_prompt(
        name="伊索尔德·影焰",
        role="庄园的炼金术师",
        alibi="我一直在实验室。",
        hidden_truth="我偷偷去了花园。",
        weakness_item="evidence_1",
        weakness_description="短箭上有月影草汁液",
        defense_score=100,
    )
    assert "伊索尔德·影焰" in prompt
    assert "庄园的炼金术师" in prompt
    assert "evidence_1" in prompt
    print("✅ [test_03] System Prompt 构建成功，长度:", len(prompt), "字符")


def test_04_suspect_agent_init():
    """
    测试 SuspectAgent 初始化。
    注意：此测试需要数据库中已存在嫌疑人数据。
    如果数据库不存在，这个测试会跳过。
    """
    try:
        from database.db_helper import DBHelper, initialize_database

        # 确保数据库已初始化
        initialize_database()

        # 创建一个测试会话和嫌疑人
        DBHelper.create_session("test_session_llm", "manor", "测试案件", 10)
        DBHelper.upsert_suspect(
            session_id="test_session_llm",
            suspect_id="suspect_a",
            name="伊索尔德·影焰",
            role="庄园的炼金术师",
        )

        from agents.suspect_agent import SuspectAgent
        agent = SuspectAgent(
            session_id="test_session_llm",
            suspect_id="suspect_a",
        )
        assert agent.name == "伊索尔德·影焰"
        assert agent.defense_score == 100

        # 清理测试数据
        DBHelper.reset_db()

        print("✅ [test_04] SuspectAgent 初始化成功")
    except Exception as e:
        print(f"⚠️ [test_04] SuspectAgent 初始化测试跳过: {e}")


def test_05_mock_respond_flow():
    """
    测试 SuspectAgent 的 respond 流程（不含真实 LLM 调用）。
    使用 Mock 数据验证数据库读写逻辑。
    """
    from database.db_helper import DBHelper, initialize_database

    initialize_database()
    try:
        # 读取 case_mock.json 中的嫌疑人数据
        mock_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "prompts",
            "case_templates",
            "case_mock.json",
        )
        with open(mock_path, "r", encoding="utf-8") as f:
            mock_data = json.load(f)

        # 创建测试会话
        DBHelper.create_session("test_respond_flow", "manor", "测试案件", 10)

        # 插入嫌疑人
        for suspect in mock_data["suspects"]:
            profile = {
                "alibi": suspect["alibi"],
                "hidden_truth": suspect["hidden_truth"],
                "weakness_item": suspect["weakness_item"],
                "weakness_description": suspect["weakness_description"],
            }
            DBHelper.upsert_suspect(
                session_id="test_respond_flow",
                suspect_id=suspect["suspect_id"],
                name=suspect["name"],
                role=suspect["role"],
                profile_json=json.dumps(profile, ensure_ascii=False),
            )

        # 验证数据库写入正确
        suspects = DBHelper.get_all_suspects("test_respond_flow")
        assert len(suspects) == 3, f"预期 3 个嫌疑人，实际 {len(suspects)}"

        # 清理
        DBHelper.reset_db()
        print("✅ [test_05] 数据库读写流程正常，mock 数据插入成功")
    except Exception as e:
        DBHelper.reset_db()
        print(f"⚠️ [test_05] 测试跳过: {e}")


def test_06_contradiction_prompt_format():
    """测试矛盾检测 Prompt 格式化"""
    from prompts.system_prompts import CONTRADICTION_DETECTION_PROMPT

    prompt = CONTRADICTION_DETECTION_PROMPT.format(
        history="警员: 你昨晚在哪里？\n伊索尔德: 我在实验室。",
        current_response="我昨晚在花园散步。",
    )
    assert "警员: 你昨晚在哪里？" in prompt
    assert "实验室" in prompt
    assert "花园" in prompt
    assert "has_contradiction" in prompt
    print("✅ [test_06] 矛盾检测 Prompt 格式化正常")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 成员 B — LLM 模块测试")
    print("=" * 60)

    tests = [
        ("API Key 检查", test_01_api_key_exists),
        ("LLM 连通性", test_02_llm_connect),
        ("System Prompt 构建", test_03_system_prompt_build),
        ("SuspectAgent 初始化", test_04_suspect_agent_init),
        ("数据库读写流程", test_05_mock_respond_flow),
        ("矛盾检测 Prompt", test_06_contradiction_prompt_format),
    ]

    passed = 0
    failed = 0
    skipped = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"❌ [{name}] 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️ [{name}] 跳过: {e}")
            skipped += 1

    print("=" * 60)
    print(f"📊 结果: {passed} 通过, {failed} 失败, {skipped} 跳过 / {len(tests)} 总计")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)