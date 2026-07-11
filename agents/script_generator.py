"""
动态剧本生成器 — ScriptGenerator
成员 B 负责

功能：
  1. 利用 LLM JSON Mode (with_structured_output) 根据风格动态生成完整案件剧本
  2. 输出严格符合 case_schema.json 定义的 JSON 结构
  3. 生成后自动写入 SQLite 三张表：case_session + suspect_status + evidence_inventory

使用示例：
    from agents.script_generator import ScriptGenerator
    generator = ScriptGenerator()
    case_data = generator.generate_case("蒸汽朋克")
    generator.save_to_db(case_data, session_id="sess_001")

运行测试：
    python -c "from agents.script_generator import demo_generate; demo_generate()"
"""

import json
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from database.db_helper import DBHelper

load_dotenv()

# ── 用 Pydantic 定义 LLM 输出结构（替代 JSON Schema 校验） ──


class SuspectSchema(BaseModel):
    """嫌疑人数据模型"""
    suspect_id: str = Field(description="嫌疑人 ID: suspect_a / suspect_b / suspect_c")
    name: str = Field(description="嫌疑人全名")
    role: str = Field(description="身份角色，如'庄园的炼金术师'")
    alibi: str = Field(description="不在场证明/公开辩解")
    hidden_truth: str = Field(description="隐藏的真实秘密")
    weakness_item: str = Field(description="弱点证物 ID，如 evidence_1")
    weakness_description: str = Field(description="为何该证物能击破防线")


class EvidenceSchema(BaseModel):
    """证物数据模型"""
    evidence_id: str = Field(description="证物 ID: evidence_1 ~ evidence_5")
    name: str = Field(description="证物名称")
    description: str = Field(description="证物描述")
    location_found: str = Field(description="发现地点")
    category: str = Field(description="类别: weapon / document / forensic / testimony / chemical")
    related_suspect_id: str = Field(description="关联嫌疑人 ID")


class CaseSchema(BaseModel):
    """完整案件数据模型（LLM输出的顶层结构）"""
    case_name: str = Field(description="案件名称")
    background: str = Field(description="案件背景描述（包含时间、地点、死者、现场）")
    suspects: list[SuspectSchema] = Field(description="嫌疑人列表（2-3人）")
    evidences: list[EvidenceSchema] = Field(description="证物列表（3-5件）")


# ── 剧本生成提示词模板 ──

STYLE_PROMPTS = {
    "manor": """
你正在创作一个"庄园谋杀案"风格的侦探故事。

时代背景：中世纪魔法世界，贵族庄园，银月魔法，炼金术与古老诅咒。
叙事风格：哥特式悬疑，阴森华丽，充满秘密与背叛。

请生成一个逻辑自洽的谋杀案，包含：
- 1 个案件名称
- 一段案件背景描述（含死亡时间、地点、死者、现场状况）
- 3 名嫌疑人（每个都有不在场证明、隐藏秘密、弱点证物）
- 4-5 件证物（每件关联一名嫌疑人）

输出要求：
- suspect_id 格式为 suspect_a, suspect_b, suspect_c
- evidence_id 格式为 evidence_1, evidence_2 ...
- category 只能取: weapon / document / forensic / testimony / chemical
""",
    "steampunk": """
你正在创作一个"蒸汽朋克"风格的侦探故事。

时代背景：维多利亚风格蒸汽工业城市，齿轮与蒸汽机，黄铜管道，工厂与机械。
叙事风格：工业革命时期的黑暗写实，阶级矛盾与技术犯罪。

请生成一个逻辑自洽的谋杀案，包含：
- 1 个案件名称
- 一段案件背景描述（含死亡时间、地点、死者、现场状况）
- 3 名嫌疑人（每个都有不在场证明、隐藏秘密、弱点证物）
- 4-5 件证物（每件关联一名嫌疑人）

输出要求：
- suspect_id 格式为 suspect_a, suspect_b, suspect_c
- evidence_id 格式为 evidence_1, evidence_2 ...
- category 只能取: weapon / document / forensic / testimony / chemical
""",
    "sci_fi": """
你正在创作一个"废土科幻"风格的侦探故事。

时代背景：未来废土世界，破败的科技都市，全息投影与基因改造，反乌托邦政府。
叙事风格：赛博朋克式的阴冷，科技罪恶，人性挣扎。

请生成一个逻辑自洽的谋杀案，包含：
- 1 个案件名称
- 一段案件背景描述（含死亡时间、地点、死者、现场状况）
- 3 名嫌疑人（每个都有不在场证明、隐藏秘密、弱点证物）
- 4-5 件证物（每件关联一名嫌疑人）

输出要求：
- suspect_id 格式为 suspect_a, suspect_b, suspect_c
- evidence_id 格式为 evidence_1, evidence_2 ...
- category 只能取: weapon / document / forensic / testimony / chemical
""",
}

GENERATION_SYSTEM_PROMPT = """你是"审讯室风云"游戏的剧本生成器。你的任务是生成本格推理风格的谋杀案剧本。

{style_prompt}

=== 关键逻辑规则（必须遵守）===
1. 每个嫌疑人的 hidden_truth 必须能解释 TA 为何行为可疑但未必是真凶
2. 每个嫌疑人的 weakness_item 必须指向一件证物，且该证物确实与 TA 有关联
3. 证物描述要具体、有细节，能让玩家通过对比判断真伪
4. 案件要逻辑自洽，不存在明显的时间线漏洞
5. 不要使用任何真实人名地名，使用虚构的奇幻/科幻名字
"""


class ScriptGenerator:
    """
    动态剧本生成器。

    利用 LLM 的 with_structured_output 功能（JSON Mode），
    根据选择的故事风格生成符合 Schema 的完整案件剧本。
    """

    def __init__(
        self,
        model_name: str = "deepseek-chat",
        temperature: float = 0.9,
    ):
        """
        初始化剧本生成器。

        参数:
          model_name: LLM 模型名
          temperature: 生成温度（越高创意越丰富）
        """
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")

        base_llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
        )
        # 优先使用 json_mode，如果失败则回退到 function_calling
        self.llm_structured = base_llm.with_structured_output(CaseSchema, method="json_mode")
        self.llm_fallback = base_llm

    def generate_case(self, style: str = "manor") -> CaseSchema:
        """
        根据风格生成完整案件剧本。

        参数:
          style: 风格名称 — "manor"(庄园) / "steampunk"(蒸汽朋克) / "sci_fi"(废土科幻)

        返回:
          CaseSchema 对象（Pydantic 模型），可直接 .model_dump() 为字典
        """
        if style not in STYLE_PROMPTS:
            valid = list(STYLE_PROMPTS.keys())
            raise ValueError(f"未知风格 '{style}'，可选: {valid}")

        style_prompt = STYLE_PROMPTS[style]
        system_prompt = GENERATION_SYSTEM_PROMPT.format(style_prompt=style_prompt)

        # 优先尝试 structured output (json_mode)
        try:
            case_data: CaseSchema = self.llm_structured.invoke([
                ("system", system_prompt),
                ("human", f"请生成一个 {style} 风格的谋杀案剧本，用 JSON 格式输出。"),
            ])
            return case_data
        except Exception as e:
            print(f"[ScriptGenerator] structured_output 失败 ({e})，尝试 fallback...")
            # fallback: 从纯文本回复中解析 JSON
            resp = self.llm_fallback.invoke([
                ("system", system_prompt + "\n请确保输出是合法的 JSON 格式，不要包含代码块标记。"),
                ("human", f"请生成一个 {style} 风格的谋杀案剧本，仅输出 JSON 格式数据。"),
            ])
            text = resp.content.strip()
            # 移除可能的 ```json ... ``` 包裹
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                text = text.rsplit("```", 1)[0] if "```" in text else text
            text = text.strip()
            case_dict = json.loads(text)
            return CaseSchema(**case_dict)

    def save_to_db(
        self,
        case_data: CaseSchema,
        session_id: Optional[str] = None,
        action_points: int = 10,
    ) -> str:
        """
        将生成的案件数据写入 SQLite 数据库。

        写入三张表：
          1. case_session     — 会话基本信息和风格
          2. suspect_status   — 每个嫌疑人的状态和 Profile
          3. evidence_inventory — 每件证物记录

        参数:
          case_data: 案件数据（CaseSchema 对象或 dict）
          session_id: 会话 ID（不传则自动生成 UUID）
          action_points: 初始行动点数

        返回:
          session_id: 写入后的会话 ID
        """
        if isinstance(case_data, CaseSchema):
            case_dict = case_data.model_dump()
        else:
            case_dict = case_data

        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:12]}"

        # 1. 写入 case_session
        DBHelper.create_session(
            session_id=session_id,
            case_style=case_dict.get("style", "manor"),
            case_name=case_dict["case_name"],
            action_points=action_points,
        )

        # 2. 写入嫌疑人
        for suspect in case_dict["suspects"]:
            profile_json = json.dumps(
                {
                    "alibi": suspect["alibi"],
                    "hidden_truth": suspect["hidden_truth"],
                    "weakness_item": suspect["weakness_item"],
                    "weakness_description": suspect["weakness_description"],
                },
                ensure_ascii=False,
            )
            DBHelper.upsert_suspect(
                session_id=session_id,
                suspect_id=suspect["suspect_id"],
                name=suspect["name"],
                role=suspect["role"],
                profile_json=profile_json,
            )

        # 3. 写入证物
        for evidence in case_dict["evidences"]:
            DBHelper.upsert_evidence(
                session_id=session_id,
                evidence_id=evidence["evidence_id"],
                name=evidence["name"],
                description=evidence["description"],
                category=evidence.get("category", "physical"),
                related_suspect_id=evidence.get("related_suspect_id", ""),
            )

        print(f"[ScriptGenerator] 案件 '{case_dict['case_name']}' 已写入数据库")
        print(f"          会话 ID: {session_id}")
        print(f"          嫌疑人: {len(case_dict['suspects'])} 人")
        print(f"          证物: {len(case_dict['evidences'])} 件")

        return session_id

    def generate_and_save(
        self,
        style: str = "manor",
        session_id: Optional[str] = None,
        action_points: int = 10,
    ) -> tuple[str, dict]:
        """
        生成剧本并直接写入数据库（便捷一步到位）。

        参数:
          style: 风格名称
          session_id: 会话 ID（不传则自动生成）
          action_points: 初始行动点数

        返回:
          (session_id, case_dict)
        """
        case_data = self.generate_case(style)
        case_dict = case_data.model_dump()
        sid = self.save_to_db(case_data, session_id, action_points)
        return sid, case_dict


# ── 便捷演示函数 ──

def demo_generate(style: str = "manor") -> None:
    """快速演示生成一个案件并输出到控制台"""
    generator = ScriptGenerator()
    case_data = generator.generate_case(style)
    case_dict = case_data.model_dump()

    print("=" * 60)
    print(f"📜 生成案件: {case_dict['case_name']}")
    print(f"📖 背景: {case_dict['background'][:100]}...")
    print("-" * 60)

    for s in case_dict["suspects"]:
        print(f"🔍 嫌疑人 {s['suspect_id']}: {s['name']}（{s['role']}）")
        print(f"   口供: {s['alibi'][:60]}...")
        print(f"   秘密: {s['hidden_truth'][:60]}...")

    print("-" * 60)
    for e in case_dict["evidences"]:
        print(f"📦 证物 {e['evidence_id']}: {e['name']}")
        print(f"   描述: {e['description'][:80]}...")

    print("=" * 60)


def demo_save_to_db(style: str = "manor") -> str:
    """生成案件并写入数据库，返回 session_id"""
    generator = ScriptGenerator()
    case_data = generator.generate_case(style)
    session_id = generator.save_to_db(case_data)
    return session_id