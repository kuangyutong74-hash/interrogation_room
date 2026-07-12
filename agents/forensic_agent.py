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
import random
import sqlite3
import threading
from typing import Optional

from config import DB_PATH
from database.db_helper import DBHelper


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


# ── 五项技能函数 ──────────────────────────────────────────

def fingerprint_match(evidence: dict, session_id: str = "") -> str:
    """指纹匹配分析。模拟从证物上提取指纹并与嫌疑人数据库比对。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"
    match_level = random.choice(["完全匹配", "完全匹配", "部分匹配", "不匹配"])

    if match_level == "完全匹配":
        result = (
            f"【指纹匹配报告】\n"
            f"证物：{evidence_name}\n"
            f"检测方法：氰基丙烯酸酯熏蒸 + 磁性粉末刷显\n"
            f"提取指纹点数：{random.randint(3, 8)} 枚完整指纹\n"
            f"比对结果：与 {suspect_name} 的指纹样本匹配度达 99.7%\n"
            f"结论：该证物上的指纹确认为 {suspect_name} 所留，构成直接物证。\n"
            f"附加发现：指纹纹路有轻微磨损痕迹，疑似长期接触化学品所致。"
        )
    elif match_level == "部分匹配":
        result = (
            f"【指纹匹配报告】\n"
            f"证物：{evidence_name}\n"
            f"检测方法：氰基丙烯酸酯熏蒸 + 磁性粉末刷显\n"
            f"提取指纹点数：{random.randint(1, 3)} 枚残缺指纹\n"
            f"比对结果：与 {suspect_name} 的指纹样本相似度约 {random.randint(60, 85)}%\n"
            f"结论：存在一定关联性，但指纹残缺不足以作为决定性证据。\n"
            f"建议：结合其他物证进行交叉验证。"
        )
    else:
        result = (
            f"【指纹匹配报告】\n"
            f"证物：{evidence_name}\n"
            f"检测方法：氰基丙烯酸酯熏蒸 + 磁性粉末刷显\n"
            f"提取指纹点数：{random.randint(1, 2)} 枚模糊指纹\n"
            f"比对结果：与 {suspect_name} 的指纹不匹配\n"
            f"结论：证物上未发现 {suspect_name} 的指纹。\n"
            f"备注：可能已被擦拭或嫌疑人佩戴了手套。"
        )
    return result


def blood_analysis(evidence: dict, session_id: str = "") -> str:
    """血迹/体液分析。模拟血型检测、DNA 比对等法医学分析。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"

    blood_types = ["A型", "B型", "AB型", "O型"]
    victim_blood = random.choice(blood_types)
    found_blood = random.choice(blood_types)

    if found_blood == victim_blood:
        analysis = (
            f"血迹血型：{found_blood}（与死者一致）\n"
            f"DNA 微卫星位点匹配数：{random.randint(13, 16)}/16\n"
            f"结论：血迹确认来源于死者。"
        )
    else:
        analysis = (
            f"血迹血型：{found_blood}（与死者的 {victim_blood} 不一致）\n"
            f"可能来源：非死者血迹，建议扩大比对范围。\n"
            f"附加检测：血迹中含有微量"
            f"{random.choice(['镇静剂', '抗凝血剂', '酒精'])}成分。"
        )

    result = (
        f"【血迹分析报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：鲁米诺发光反应 + PCR-STR 短串联重复序列分析\n"
        f"{analysis}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"备注：建议将 DNA 样本与 {suspect_name} 的口腔拭子进行交叉比对。"
    )
    return result


def document_verify(evidence: dict, session_id: str = "") -> str:
    """文件/笔迹鉴定。模拟笔迹比对、纸张年代测定、墨水成分分析等。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"

    forgery_methods = [
        "字迹压力分布不均，疑似临摹伪造",
        "墨水成分与声称年代不符（检测到现代合成染料）",
        "纸张纤维中含有荧光增白剂——该物质在声称的年代尚未广泛使用",
        "笔迹整体流畅自然，与样本匹配度高，应为同一人所写",
        "发现有刮擦改写痕迹——原文字被化学方法去除后重新书写",
    ]
    forgery_finding = random.choice(forgery_methods)
    is_forged = any(kw in forgery_finding for kw in ["伪造", "不符", "改写"])

    result = (
        f"【文件鉴定报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：VSC-8000 视频光谱比对 + HPLC 高效液相色谱（墨水分析）\n"
        f"笔迹特征分析：\n"
        f"  · 书写压力曲线：{random.choice(['异常波动', '正常分布', '可疑平直'])}\n"
        f"  · 起收笔特征：{random.choice(['与样本一致', '存在差异', '刻意模仿痕迹'])}\n"
        f"  · 连笔习惯：{random.choice(['自然流畅', '断笔异常', '与样本匹配'])}\n"
        f"关键发现：{forgery_finding}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：{'该文件存在伪造嫌疑，建议对 ' + suspect_name + ' 进行进一步询问。'
                if is_forged else '文件分析未见明显异常。'}"
    )
    return result


def toxicology_report(evidence: dict, session_id: str = "") -> str:
    """毒物化验报告。模拟毒理学分析、药物筛查等。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"

    toxins = [
        ("乌头碱（Aconitine）", "剧毒生物碱，作用于钠离子通道，致死剂量 2mg"),
        ("氰化物（Cyanide）", "细胞色素c氧化酶抑制剂，作用迅速"),
        ("毛地黄苷（Digoxin）", "强心苷类，过量导致心律失常"),
        ("砷化合物（Arsenic）", "经典毒物，蓄积性中毒，症状类似自然疾病"),
        ("月影草毒素（Lunaris Toxin）", "魔法植物提取物，神经麻痹作用，需特殊解药"),
    ]
    toxin, toxin_desc = random.choice(toxins)
    detected = random.choice([True, True, False])

    if detected:
        result = (
            f"【毒物分析报告】\n"
            f"证物：{evidence_name}\n"
            f"检测方法：GC-MS 气相色谱-质谱联用 + 免疫分析法\n"
            f"检测结果：阳性 —— 检出 {toxin}\n"
            f"毒理说明：{toxin_desc}\n"
            f"定量分析：样本中浓度为 {random.uniform(0.5, 50):.1f} μg/mL\n"
            f"关联嫌疑人：{suspect_name}\n"
            f"结论：该证物含有致命毒物。"
            f"需查明毒物来源及 {suspect_name} 是否具备获取条件。"
        )
    else:
        result = (
            f"【毒物分析报告】\n"
            f"证物：{evidence_name}\n"
            f"检测方法：GC-MS 气相色谱-质谱联用 + 免疫分析法\n"
            f"检测结果：阴性 —— 未检出常见毒物成分\n"
            f"备注：已覆盖{random.randint(80, 120)}种常见毒物数据库筛查\n"
            f"关联嫌疑人：{suspect_name}\n"
            f"结论：该证物不含毒物。"
            f"若怀疑中毒，建议对死者血液样本进行更深入的毒理学筛查。"
        )
    return result


def trace_analysis(evidence: dict, session_id: str = "") -> str:
    """微量痕迹分析。模拟纤维、毛发、土壤、玻璃碎片等微量物证比对。"""
    evidence_name = evidence.get("name", "未知证物")
    related = evidence.get("related_suspect_id", "")
    suspect_name = _suspect_name(session_id, related) if related else "未知人员"

    trace_options = [
        ("纺织纤维",
         f"证物表面附着{random.randint(3, 15)}根纤维，经偏振光显微镜比对，"
         f"与 {suspect_name} 衣物纤维材质一致"
         f"（{random.choice(['羊毛', '亚麻', '丝绸', '棉涤混纺'])}）"),
        ("毛发",
         f"发现{random.randint(1, 4)}根毛发，毛囊完整度"
         f"{random.choice(['良好', '一般', '较差'])}，"
         f"线粒体 DNA 分析指向与 {suspect_name} 高度相关"),
        ("土壤颗粒",
         f"证物缝隙中的土壤矿物成分与案发现场花园土壤的 pH 值和石英含量"
         f"{random.choice(['高度一致', '存在差异', '部分匹配'])}"),
        ("玻璃碎片",
         f"碎片折射率 {random.uniform(1.51, 1.53):.4f}，"
         f"与案发现场破碎的玻璃窗折射率"
         f"{random.choice(['一致', '略有偏差', '不同'])}"),
        ("油漆屑",
         f"证物表面刮擦处附着的油漆层序结构（底漆→面漆→清漆）"
         f"与 {suspect_name} 处的油漆"
         f"{random.choice(['完全匹配', '不匹配', '部分匹配'])}"),
    ]
    trace_name, trace_detail = random.choice(trace_options)
    match_keywords = ["一致", "匹配", "高度相关"]
    is_match = any(kw in trace_detail for kw in match_keywords)

    result = (
        f"【微量痕迹分析报告】\n"
        f"证物：{evidence_name}\n"
        f"检测方法：SEM 扫描电子显微镜 + 显微红外光谱分析\n"
        f"检出痕迹类型：{trace_name}\n"
        f"分析详情：{trace_detail}\n"
        f"关联嫌疑人：{suspect_name}\n"
        f"结论：证物上的微量痕迹为案件关联性提供了"
        f"{'重要' if is_match else '参考'}线索。"
    )
    return result


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
    """列出所有可用的分析技能及其适用类别和耗时"""
    return {
        "skills": list(SKILL_FUNCTIONS.keys()),
        "category_mapping": SKILL_CATEGORY_MAP,
        "durations": SKILL_DURATION_MAP,
    }


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

    def submit_analysis(self, evidence_id: str) -> int:
        """将证物送检，写入 forensic_queue。返回 task_id。"""
        evidence = DBHelper.get_evidence(self.session_id, evidence_id)
        if evidence is None:
            raise ValueError(
                f"证物 '{evidence_id}' 不存在于会话 '{self.session_id}'"
            )
        if evidence.get("is_analyzed"):
            raise ValueError(f"证物 '{evidence_id}' 已经完成化验，无需重复送检")
        if evidence.get("analysis_pending"):
            raise ValueError(f"证物 '{evidence_id}' 已送检，正在等待化验结果")

        task_id = DBHelper.enqueue_forensic(self.session_id, evidence_id)
        print(
            f"[ForensicAgent] 证物 '{evidence['name']}' 已送检，"
            f"任务 ID: {task_id}"
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
