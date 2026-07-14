"""
法医异步化验模块 — 分析技能 + 后台调度器
成员 C 负责

结构：
  Part 1: 分析技能（纯函数，无状态）—— 可直接 import 使用
  Part 2: ForensicAgent（异步调度器）——— 组合技能，管理后台线程

使用示例：
    # 方式1：只调用技能，不走队列
    from agents.forensic_agent import run_analysis, list_available_skills
    report = run_analysis(evidence, skill="fingerprint_match", session_id="sess_001")

    # 方式2：提交异步化验
    from agents.forensic_agent import ForensicAgent
    agent = ForensicAgent(session_id="sess_001")
    task_id = agent.submit_analysis("evidence_1")
    agent.start_scheduler()
    # ... 游戏继续 ...
    results = agent.get_completed_results()
    agent.stop_scheduler()
"""

import asyncio
import os
import random
import sqlite3
import threading
from typing import Optional

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from config import DB_PATH
from database.db_helper import DBHelper

load_dotenv()

# ── LLM 实例（懒加载）─────────────────────────────────────

_llm: Optional[ChatOpenAI] = None


def _get_llm() -> ChatOpenAI:
    """获取共享的 LLM 实例，用于法医报告生成"""
    global _llm
    if _llm is None:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            temperature=0.7,
            api_key=api_key,
            base_url=base_url,
        )
    return _llm


# ══════════════════════════════════════════════════════════════
#  Part 1: 分析技能（纯函数，无状态，无异步）
# ══════════════════════════════════════════════════════════════

# ── 技能元数据 ─────────────────────────────────────────────

SKILL_CATEGORY_MAP = {
    "fingerprint_match":  ["weapon", "document", "physical"],
    "blood_analysis":     ["weapon", "forensic", "physical"],
    "document_verify":    ["document"],
    "toxicology_report":  ["chemical", "forensic"],
    "trace_analysis":     ["forensic", "physical", "testimony"],
}

SKILL_DURATION_MAP = {
    "fingerprint_match": 12,
    "blood_analysis":    15,
    "document_verify":   18,
    "toxicology_report": 20,
    "trace_analysis":    10,
}

# 行动点数（AP）消耗：越复杂的化验消耗越多
SKILL_AP_COST = {
    "fingerprint_match": 1,
    "blood_analysis":    2,
    "document_verify":   1,
    "toxicology_report": 2,
    "trace_analysis":    2,
}

DEFAULT_AP_COST = 1  # 自动选择技能时的默认消耗


# ── 内部工具 ───────────────────────────────────────────────

def _pick_skill_for_evidence(evidence: dict) -> str:
    """根据证物类别自动选择合适的分析技能"""
    category = evidence.get("category", "physical")
    candidates = [
        skill for skill, cats in SKILL_CATEGORY_MAP.items()
        if category in cats
    ]
    if not candidates:
        candidates = ["trace_analysis"]
    return random.choice(candidates)


def _suspect_name(session_id: str, suspect_id: str) -> str:
    """安全获取嫌疑人姓名，失败时返回原始 ID"""
    if not session_id or not suspect_id:
        return suspect_id or "未知人员"
    try:
        s = DBHelper.get_suspect(session_id, suspect_id)
        return s["name"] if s else suspect_id
    except Exception:
        return suspect_id


# ── LLM 报告生成辅助 ────────────────────────────────────

def _llm_report(system_prompt: str, user_prompt: str,
                fallback: str) -> str:
    """调用 LLM 生成法医报告，失败时回退到兜底文本"""
    try:
        llm = _get_llm()
        response = llm.invoke([
            ("system", system_prompt),
            ("human", user_prompt),
        ])
        return response.content.strip()
    except Exception as e:
        print(f"[ForensicAgent] LLM 调用失败 ({e})，使用兜底报告")
        return fallback


# ── 五项技能函数（LangChain LLM 生成报告）──────────────

FORENSIC_SYSTEM_PROMPT = (
    "你是审讯室风云游戏中的法医实验室主任。请根据证物信息生成一份"
    "专业、沉浸式的法医分析报告。报告应包含：检测方法、关键发现、"
    "与嫌疑人的关联、结论。语气专业冷静，150-250字，带【报告标题】。"
    "根据游戏剧情需要，报告结论应模棱两可，既有指向性又不完全确定，"
    "给玩家留下追问空间。不要使用markdown代码块。"
    "报告中必须包含证物的原始名称，不得改写或省略。"
)


def fingerprint_match(evidence: dict, session_id: str = "") -> str:
    """指纹匹配分析。LLM 生成专业指纹比对报告。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    description = evidence.get("description", "")

    fallback = (
        f"【指纹匹配报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：氰基丙烯酸酯熏蒸法 + 磁性粉末刷显法 + AFIS自动指纹识别系统\n"
        f"提取指纹点数：3 枚（1枚完整，2枚残缺）\n"
        f"比对结果：证物表面提取的指纹与 {suspect_name} 的指纹样本存在关联性，"
        f"相似度评分处于灰色区间。\n"
        f"结论：指纹证据具有一定指向意义，但需结合更多物证进行交叉验证，"
        f"单独不足以形成完整证据链。"
    )

    return _llm_report(
        FORENSIC_SYSTEM_PROMPT,
        f"请生成【指纹匹配报告】。\n"
        f"证物名称：{evidence_name}\n"
        f"证物描述：{description}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"检测手段：氰基丙烯酸酯熏蒸法、磁性粉末刷显法、AFIS自动指纹识别系统\n"
        f"要求：报告应包含指纹提取点数、比对匹配度、嫌疑人关联度分析。",
        fallback,
    )


def blood_analysis(evidence: dict, session_id: str = "") -> str:
    """血迹/体液分析。LLM 生成专业血迹分析报告。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    description = evidence.get("description", "")

    fallback = (
        f"【血迹分析报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：鲁米诺发光反应 + PCR-STR 短串联重复序列分析\n"
        f"分析结果：血迹样本经DNA比对分析完成。\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：建议将DNA结果与证人口供进行交叉验证。"
    )

    return _llm_report(
        FORENSIC_SYSTEM_PROMPT,
        f"请生成【血迹分析报告】。\n"
        f"证物名称：{evidence_name}\n"
        f"证物描述：{description}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"检测手段：鲁米诺发光反应、PCR-STR短串联重复序列分析、ABO血型鉴定\n"
        f"要求：报告应包含血型检测结果、DNA微卫星位点匹配情况、血迹来源分析。",
        fallback,
    )


def document_verify(evidence: dict, session_id: str = "") -> str:
    """文件/笔迹鉴定。LLM 生成专业文件鉴定报告。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    description = evidence.get("description", "")

    fallback = (
        f"【文件鉴定报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：VSC-8000 视频光谱比对 + HPLC 高效液相色谱（墨水分析）\n"
        f"笔迹特征分析已完成。\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：文件真实性需结合其他证据综合判断。"
    )

    return _llm_report(
        FORENSIC_SYSTEM_PROMPT,
        f"请生成【文件鉴定报告】。\n"
        f"证物名称：{evidence_name}\n"
        f"证物描述：{description}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"检测手段：VSC-8000视频光谱比对、HPLC高效液相色谱墨水分析、纸张纤维检测\n"
        f"要求：报告应包含笔迹压力/连笔特征、墨水成分年代分析、是否存在伪造或篡改痕迹。",
        fallback,
    )


def toxicology_report(evidence: dict, session_id: str = "") -> str:
    """毒物化验。LLM 生成专业毒理学分析报告。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    description = evidence.get("description", "")

    fallback = (
        f"【毒物分析报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：GC-MS 气相色谱-质谱联用 + 免疫分析法\n"
        f"毒物筛查已完成。\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：需查明毒物来源及嫌疑人是否具备获取条件。"
    )

    return _llm_report(
        FORENSIC_SYSTEM_PROMPT,
        f"请生成【毒物分析报告】。\n"
        f"证物名称：{evidence_name}\n"
        f"证物描述：{description}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"检测手段：GC-MS气相色谱-质谱联用、免疫分析法、毒物数据库筛查\n"
        f"要求：报告应包含是否检出毒物、毒物种类及毒理说明、定量浓度分析。",
        fallback,
    )


def trace_analysis(evidence: dict, session_id: str = "") -> str:
    """微量痕迹分析。LLM 生成专业微量物证比对报告。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    description = evidence.get("description", "")

    fallback = (
        f"【微量痕迹分析报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：SEM 扫描电子显微镜 + 显微红外光谱分析\n"
        f"微量物证分析已完成。\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：证物上的微量痕迹为案件提供了参考线索。"
    )

    return _llm_report(
        FORENSIC_SYSTEM_PROMPT,
        f"请生成【微量痕迹分析报告】。\n"
        f"证物名称：{evidence_name}\n"
        f"证物描述：{description}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"检测手段：SEM扫描电子显微镜、显微红外光谱分析、偏振光显微镜\n"
        f"要求：报告应包含检出的痕迹类型（纤维/毛发/土壤/玻璃/油漆等）、"
        f"与嫌疑人的关联度、对案件的指向意义。",
        fallback,
    )


# ── 技能注册表 ─────────────────────────────────────────────

SKILL_FUNCTIONS = {
    "fingerprint_match": fingerprint_match,
    "blood_analysis":    blood_analysis,
    "document_verify":   document_verify,
    "toxicology_report": toxicology_report,
    "trace_analysis":    trace_analysis,
}


# ── 公共入口 ───────────────────────────────────────────────

def run_analysis(evidence: dict, skill: Optional[str] = None,
                 session_id: str = "") -> dict:
    """
    对单个证物运行指定的分析技能，返回结构化报告。

    参数:
      evidence: 证物数据字典（从 DBHelper.get_evidence() 获取）
      skill: 技能名称（不传则根据证物类别自动选择）
      session_id: 会话 ID（用于获取嫌疑人姓名）

    返回:
      {"skill": str, "result": str, "evidence_id": str, "duration": int}
    """
    if skill is None:
        skill = _pick_skill_for_evidence(evidence)
    elif skill not in SKILL_FUNCTIONS:
        valid = list(SKILL_FUNCTIONS.keys())
        raise ValueError(f"未知技能 '{skill}'，可用: {valid}")

    func = SKILL_FUNCTIONS[skill]
    result_text = func(evidence, session_id)

    return {
        "skill": skill,
        "result": result_text,
        "evidence_id": evidence.get("evidence_id", ""),
        "duration": SKILL_DURATION_MAP.get(skill, 15),
    }


def list_available_skills() -> dict:
    """列出所有可用的分析技能及其适用类别、耗时和AP消耗"""
    return {
        "skills": list(SKILL_FUNCTIONS.keys()),
        "category_mapping": SKILL_CATEGORY_MAP,
        "durations": SKILL_DURATION_MAP,
        "ap_costs": SKILL_AP_COST,
    }


# ── LangChain Tool 包装 ──────────────────────────────────
# 给每个技能包一层 @tool 装饰器，让 LLM Agent（如 GMAgent）
# 能通过 Function Calling 直接调用法医技能。
# 参数统一为 (evidence_id: str, session_id: str)，内部从 DB 读取证物。

@tool
def fingerprint_match_tool(evidence_id: str, session_id: str) -> str:
    """指纹匹配分析。对证物进行氰基丙烯酸酯熏蒸及磁性粉末刷显，提取指纹后与嫌疑人数据库比对。
    适用类别: weapon / document / physical。
    输入 evidence_id（如 evidence_1）和 session_id，返回结构化指纹匹配报告。"""
    evidence = _get_evidence_or_error(session_id, evidence_id)
    if evidence is None:
        return f"错误：证物 '{evidence_id}' 不存在"
    return fingerprint_match(evidence, session_id)


@tool
def blood_analysis_tool(evidence_id: str, session_id: str) -> str:
    """血迹/体液分析。使用鲁米诺发光反应及 PCR-STR 短串联重复序列分析，检测证物上的血迹来源。
    适用类别: weapon / forensic / physical。
    输入 evidence_id 和 session_id，返回结构化血迹分析报告。"""
    evidence = _get_evidence_or_error(session_id, evidence_id)
    if evidence is None:
        return f"错误：证物 '{evidence_id}' 不存在"
    return blood_analysis(evidence, session_id)


@tool
def document_verify_tool(evidence_id: str, session_id: str) -> str:
    """文件/笔迹鉴定。使用 VSC-8000 视频光谱比对及 HPLC 高效液相色谱分析墨水成分，
    判断文件是否存在伪造或篡改。适用类别: document。
    输入 evidence_id 和 session_id，返回结构化文件鉴定报告。"""
    evidence = _get_evidence_or_error(session_id, evidence_id)
    if evidence is None:
        return f"错误：证物 '{evidence_id}' 不存在"
    return document_verify(evidence, session_id)


@tool
def toxicology_report_tool(evidence_id: str, session_id: str) -> str:
    """毒物化验。使用 GC-MS 气相色谱-质谱联用及免疫分析法，筛查证物中是否含有毒物。
    适用类别: chemical / forensic。
    输入 evidence_id 和 session_id，返回结构化毒物分析报告。"""
    evidence = _get_evidence_or_error(session_id, evidence_id)
    if evidence is None:
        return f"错误：证物 '{evidence_id}' 不存在"
    return toxicology_report(evidence, session_id)


@tool
def trace_analysis_tool(evidence_id: str, session_id: str) -> str:
    """微量痕迹分析。使用 SEM 扫描电子显微镜及显微红外光谱分析证物上的纤维、毛发、
    土壤、玻璃碎片等微量物证。适用类别: forensic / physical / testimony。
    输入 evidence_id 和 session_id，返回结构化微量痕迹分析报告。"""
    evidence = _get_evidence_or_error(session_id, evidence_id)
    if evidence is None:
        return f"错误：证物 '{evidence_id}' 不存在"
    return trace_analysis(evidence, session_id)


def _get_evidence_or_error(session_id: str, evidence_id: str) -> Optional[dict]:
    """从 DB 读取证物，不存在时返回 None（工具调用方自行处理错误消息）"""
    return DBHelper.get_evidence(session_id, evidence_id)


FORENSIC_TOOLS = [
    fingerprint_match_tool,
    blood_analysis_tool,
    document_verify_tool,
    toxicology_report_tool,
    trace_analysis_tool,
]


def get_forensic_tools() -> list:
    """返回所有法医分析技能对应的 LangChain Tool 列表。
    可直接传给 LangChain Agent 的 tools 参数。

    用法:
        from agents.forensic_agent import get_forensic_tools
        agent = create_react_agent(llm, get_forensic_tools(), ...)
    """
    return FORENSIC_TOOLS


# ══════════════════════════════════════════════════════════════
#  Part 2: 异步调度器（组合技能，管理后台线程）
# ══════════════════════════════════════════════════════════════

class ForensicAgent:
    """
    法医异步化验调度器。

    在后台守护线程中运行 asyncio 事件循环，持续监控 forensic_queue 表：
    1. 查询 pending 任务 → 标记为 processing
    2. 读取证物信息 → 调用 run_analysis() 生成报告
    3. 按技能耗时模拟等待（10-20 秒）
    4. 调用 DBHelper.complete_analysis() 写回结果

    线程模型：
      - 主线程：游戏 UI / CLI 操作
      - 后台守护线程：asyncio 事件循环，生命周期跟随主进程
    """

    POLL_INTERVAL = 2

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._processed_tasks: set = set()

    # ── 提交化验任务 ─────────────────────────────────────

    def submit_analysis(self, evidence_id: str, skill: Optional[str] = None) -> int:
        """将证物送检，写入 forensic_queue，自动扣除行动点数。返回 task_id。"""
        evidence = DBHelper.get_evidence(self.session_id, evidence_id)
        if evidence is None:
            raise ValueError(
                f"证物 '{evidence_id}' 不存在于会话 '{self.session_id}'"
            )
        if evidence.get("is_analyzed"):
            raise ValueError(f"证物 '{evidence_id}' 已经完成化验，无需重复送检")
        if evidence.get("analysis_pending"):
            raise ValueError(f"证物 '{evidence_id}' 已送检，正在等待化验结果")

        # ── AP 消耗 ──
        actual_skill = skill or _pick_skill_for_evidence(evidence)
        ap_cost = SKILL_AP_COST.get(actual_skill, DEFAULT_AP_COST)
        remaining = DBHelper.update_action_points(self.session_id, -ap_cost)
        if remaining <= 0:
            DBHelper.update_action_points(self.session_id, ap_cost)  # 回退
            raise ValueError(
                f"行动点数不足！送检 {evidence['name']} 需要 {ap_cost} AP，"
                f"当前剩余 {remaining + ap_cost} AP"
            )

        task_id = DBHelper.enqueue_forensic(self.session_id, evidence_id)
        print(
            f"[ForensicAgent] 证物 '{evidence['name']}' 已送检，"
            f"任务 ID: {task_id}，消耗 {ap_cost} AP（剩余 {remaining} AP）"
        )
        return task_id

    def submit_analysis_batch(self, evidence_ids: list[str]) -> list[int]:
        """批量提交化验任务。返回成功提交的 task_id 列表。"""
        task_ids = []
        for eid in evidence_ids:
            try:
                tid = self.submit_analysis(eid)
                task_ids.append(tid)
            except ValueError as e:
                print(f"[ForensicAgent] 跳过 '{eid}': {e}")
        return task_ids

    # ── 同步直接分析（不经队列）───────────────────────────

    def run_skill_now(self, evidence_id: str,
                      skill: Optional[str] = None) -> dict:
        """直接对证物运行分析技能，同步返回报告（不经过队列）。"""
        evidence = DBHelper.get_evidence(self.session_id, evidence_id)
        if evidence is None:
            raise ValueError(f"证物 '{evidence_id}' 不存在")
        return run_analysis(evidence, skill, self.session_id)

    # ── 调度器生命周期 ────────────────────────────────────

    def start_scheduler(self) -> None:
        """启动后台异步调度器（守护线程）。"""
        if self._running:
            print("[ForensicAgent] 调度器已在运行中，无需重复启动")
            return

        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._run_event_loop,
            name="forensic-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        print("[ForensicAgent] 异步调度器已启动（后台守护线程）")

    def stop_scheduler(self, timeout: float = 30.0) -> None:
        """停止后台调度器，等待当前任务完成后退出。"""
        if not self._running:
            return

        print("[ForensicAgent] 正在停止调度器...")
        self._running = False

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=timeout)

        print("[ForensicAgent] 调度器已停止")

    @property
    def is_running(self) -> bool:
        """调度器是否在运行"""
        return (
            self._running
            and self._scheduler_thread is not None
            and self._scheduler_thread.is_alive()
        )

    # ── 内部实现 ──────────────────────────────────────────

    def _run_event_loop(self) -> None:
        """在后台线程中创建并运行 asyncio 事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._process_queue_loop())
        except (asyncio.CancelledError, RuntimeError):
            pass
        finally:
            pending = asyncio.all_tasks(self._loop)
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()
            self._loop = None

    async def _process_queue_loop(self) -> None:
        """后台主循环：监控队列 → 处理任务 → 写回数据库"""
        print("[ForensicAgent] 队列监控循环启动...")

        while self._running:
            try:
                pending = DBHelper.get_pending_analyses(self.session_id)

                for task in pending:
                    if not self._running:
                        break

                    task_id = task["id"]
                    if task_id in self._processed_tasks:
                        continue
                    self._processed_tasks.add(task_id)

                    evidence_id = task["evidence_id"]
                    DBHelper.start_analysis(task_id)
                    print(
                        f"[ForensicAgent] 开始化验: {evidence_id} "
                        f"(task #{task_id})"
                    )

                    evidence = DBHelper.get_evidence(
                        self.session_id, evidence_id
                    )
                    if evidence is None:
                        DBHelper.complete_analysis(
                            task_id,
                            f"【错误】证物 '{evidence_id}' 不存在"
                        )
                        continue

                    skill = _pick_skill_for_evidence(evidence)
                    duration = SKILL_DURATION_MAP.get(skill, 15)
                    print(
                        f"[ForensicAgent]   使用技能: {skill} "
                        f"（预计 {duration} 秒）"
                    )

                    await self._simulate_analysis(
                        duration, task_id, evidence_id
                    )

                    if not self._running:
                        break

                    analysis_result = run_analysis(
                        evidence, skill, self.session_id
                    )
                    DBHelper.complete_analysis(
                        task_id, analysis_result["result"]
                    )
                    print(
                        f"[ForensicAgent] 化验完成: {evidence_id} "
                        f"(task #{task_id}, 耗时 {duration}s)"
                    )

                if self._running:
                    await asyncio.sleep(self.POLL_INTERVAL)

            except Exception as e:
                print(f"[ForensicAgent] 调度器异常: {e}")
                if self._running:
                    await asyncio.sleep(5)

        print("[ForensicAgent] 队列监控循环已退出")

    async def _simulate_analysis(self, duration: int, task_id: int,
                                  evidence_id: str) -> None:
        """分步等待模拟化验耗时，支持运行时取消"""
        elapsed = 0
        step = 3
        while elapsed < duration and self._running:
            wait = min(step, duration - elapsed)
            await asyncio.sleep(wait)
            elapsed += wait
            if elapsed < duration:
                print(
                    f"[ForensicAgent]   #{task_id} {evidence_id} 化验中..."
                    f"({elapsed}/{duration}s)"
                )

    # ── 查询接口 ─────────────────────────────────────────

    def get_pending_tasks(self) -> list[dict]:
        """获取所有待处理/处理中的化验任务"""
        return DBHelper.get_pending_analyses(self.session_id)

    def get_completed_results(self) -> list[dict]:
        """获取已完成的化验结果（供前端轮询）"""
        return DBHelper.get_completed_notifications(self.session_id)

    def get_queue_summary(self) -> dict:
        """获取队列状态摘要（供调试和 UI 展示）"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            pending = conn.execute(
                """SELECT COUNT(*) as cnt FROM forensic_queue
                   WHERE session_id = ? AND status = 'pending'""",
                (self.session_id,)
            ).fetchone()["cnt"]
            processing = conn.execute(
                """SELECT COUNT(*) as cnt FROM forensic_queue
                   WHERE session_id = ? AND status = 'processing'""",
                (self.session_id,)
            ).fetchone()["cnt"]
            completed = conn.execute(
                """SELECT COUNT(*) as cnt FROM forensic_queue
                   WHERE session_id = ? AND status = 'completed'""",
                (self.session_id,)
            ).fetchone()["cnt"]
        finally:
            conn.close()

        return {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "total": pending + processing + completed,
            "scheduler_running": self.is_running,
        }

    # ── 上下文管理器 ─────────────────────────────────────

    def __enter__(self):
        self.start_scheduler()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_scheduler()
        return False
