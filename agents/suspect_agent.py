"""
嫌疑人 SubAgent — 角色大脑与记忆对比引擎
成员 B 负责

功能：
  1. 根据防线分数动态生成不同语气的 LLM 回复
  2. 集成 ConversationBufferWindowMemory 记忆最近 5 轮对话
  3. 谎言/矛盾检测：比对历史回答与当前回答，发现冲突时输出扣分信号
  4. 对接数据库：对话写入 chat_history，防线变化更新到 suspect_status

使用示例：
    from agents.suspect_agent import SuspectAgent
    agent = SuspectAgent(session_id="demo_session_001", suspect_id="suspect_a")
    result = agent.respond("你昨晚在哪里？")
    # result = {"reply": "...", "defense_delta": 0, "contradiction_detected": False, "is_broken": False}
"""

import json
import os
from typing import Optional

from dotenv import load_dotenv
from langchain.memory import ConversationBufferWindowMemory
from langchain_openai import ChatOpenAI

from database.db_helper import DBHelper
from prompts.system_prompts import (
    build_suspect_prompt,
    CONTRADICTION_DETECTION_PROMPT,
)

# 加载 .env 中的 API Key
load_dotenv()


class SuspectAgent:
    """
    嫌疑人角色大脑。

    每个嫌疑人拥有：
      - 独立的对话记忆 (最近 10 轮)
      - 动态防线值驱动的语气切换
      - 谎言/矛盾自动检测
      - 数据库持久化（对话记录 + 防线值）
    """

    def __init__(
        self,
        session_id: str,
        suspect_id: str,
        model_name: str = "deepseek-chat",
        temperature: float = 0.8,
        memory_window: int = 10,
    ):
        """
        初始化嫌疑人 Agent。

        参数:
          session_id: 当前游戏会话 ID
          suspect_id: 嫌疑人 ID（如 suspect_a）
          model_name: LLM 模型名，deepseek-chat 对应 DeepSeek V3
          temperature: 生成温度（越高越有创造性）
          memory_window: 记忆窗口大小（最近 N 轮对话）
        """
        self.session_id = session_id
        self.suspect_id = suspect_id

        # 从数据库加载嫌疑人 Profile
        suspect_data = DBHelper.get_suspect(session_id, suspect_id)
        if suspect_data is None:
            raise ValueError(
                f"Suspect '{suspect_id}' not found in session '{session_id}'. "
                f"Make sure the suspect is created in database first."
            )

        self.name = suspect_data["name"]
        self.role = suspect_data.get("role", "")
        self.profile_json = json.loads(suspect_data.get("profile_json", "{}"))
        self.defense_score = suspect_data["defense_score"]

        # 从 profile_json 中提取字段（兼容 template_manor.json / template_steampunk.json 格式）
        profile = self.profile_json
        self.alibi = profile.get("alibi", "")
        self.hidden_truth = profile.get("hidden_truth", "")
        self.weakness_item = profile.get("weakness_item", "")
        self.weakness_description = profile.get("weakness_description", "")

        # 初始化 LLM（兼容 OpenAI / DeepSeek / 任何 OpenAI 兼容 API）
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv(
            "LLM_BASE_URL",
            "https://api.deepseek.com/v1"
        )

        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,
        )

        # 对话记忆窗口（最近 N 轮，从数据库加载初始化）
        self.memory = ConversationBufferWindowMemory(
            k=memory_window,
            return_messages=True,
        )
        self._load_memory_from_db()

        # 当前对质证物（None 表示无对质）
        self.current_confrontation_item: Optional[str] = None

    # ── 记忆管理 ─────────────────────────────────────────

    def _load_memory_from_db(self) -> None:
        """从数据库加载最近对话到内存窗口"""
        messages = DBHelper.get_recent_messages(
            self.session_id,
            suspect_id=self.suspect_id,
            limit=self.memory.k * 2,  # 加载略多，保证记忆窗口填满
        )
        for msg in messages:
            if msg["role"] == "player":
                self.memory.chat_memory.add_user_message(msg["content"])
            elif msg["role"] == "suspect":
                self.memory.chat_memory.add_ai_message(msg["content"])

    def _get_chat_history_text(self) -> str:
        """
        将记忆窗口中的对话历史转换为纯文本格式，
        用于注入到 System Prompt 和矛盾检测。
        """
        history = self.memory.load_memory_variables({})
        messages = history.get("history", [])
        lines = []
        for msg in messages:
            role_label = "警员" if msg.type == "human" else f"{self.name}"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)

    # ── 防线管理 ─────────────────────────────────────────

    def _update_defense(self, delta: int) -> int:
        """
        更新防线分数并同步到数据库。
        返回更新后的防线值。
        """
        if delta == 0:
            return self.defense_score
        new_score = DBHelper.update_defense_score(
            self.session_id, self.suspect_id, delta
        )
        self.defense_score = new_score
        return new_score

    # ── 矛盾检测 ─────────────────────────────────────────

    def _detect_contradiction(
        self, current_response: str
    ) -> dict:
        """
        使用 LLM 对比历史对话与当前回答，检测逻辑矛盾。

        返回:
          {
            "has_contradiction": bool,
            "contradiction_reason": str,
            "contradiction_quote_old": str,
            "contradiction_quote_new": str,
            "defense_penalty": int
          }
        """
        history_text = self._get_chat_history_text()
        if not history_text.strip():
            # 没有历史对话，无法检测矛盾
            return {
                "has_contradiction": False,
                "contradiction_reason": "",
                "contradiction_quote_old": "",
                "contradiction_quote_new": "",
                "defense_penalty": 0,
            }

        prompt = CONTRADICTION_DETECTION_PROMPT.format(
            history=history_text,
            current_response=current_response,
        )

        try:
            response = self.llm.invoke(prompt)
            result = json.loads(response.content.strip().replace("```json", "").replace("```", ""))
            return result
        except (json.JSONDecodeError, Exception):
            # 解析失败时视为无矛盾
            return {
                "has_contradiction": False,
                "contradiction_reason": "",
                "contradiction_quote_old": "",
                "contradiction_quote_new": "",
                "defense_penalty": 0,
            }

    # ── 核心对话方法 ─────────────────────────────────────

    def set_confrontation(self, evidence_name: Optional[str]) -> None:
        """
        设置当前对质证物。
        当玩家出示证物时调用此方法，下一轮 respond 会对质生效。
        """
        self.current_confrontation_item = evidence_name

    def respond(self, player_input: str) -> dict:
        """
        核心方法：接收玩家输入，返回嫌疑人回复。

        参数:
          player_input: 玩家输入的对话文本

        返回:
          {
            "reply": str,              # 嫌疑人的回答文本
            "defense_delta": int,      # 防线变化值（正增负减）
            "contradiction_detected": bool,  # 是否发现矛盾
            "contradiction_reason": str,     # 矛盾原因
            "is_broken": bool          # 防线是否崩溃 (< 10)
          }
        """
        # Step 1: 将玩家输入写入数据库
        DBHelper.add_message(
            self.session_id, "player", player_input, self.suspect_id
        )

        # Step 2: 构建 System Prompt
        chat_history_text = self._get_chat_history_text()
        system_prompt = build_suspect_prompt(
            name=self.name,
            role=self.role,
            alibi=self.alibi,
            hidden_truth=self.hidden_truth,
            weakness_item=self.weakness_item,
            weakness_description=self.weakness_description,
            defense_score=self.defense_score,
            chat_history_text=chat_history_text,
            current_confrontation_item=self.current_confrontation_item,
        )

        # Step 3: 调用 LLM 生成回复
        try:
            response = self.llm.invoke(
                [
                    ("system", system_prompt),
                    ("human", player_input),
                ]
            )
            reply = response.content.strip()
        except Exception as e:
            reply = f"(嫌疑人陷入沉默，似乎受到了什么干扰...) [LLM Error: {str(e)}]"

        # Step 4: 将嫌疑人回复写入数据库
        DBHelper.add_message(
            self.session_id, "suspect", reply, self.suspect_id
        )

        # Step 5: 将对话加入内存窗口
        self.memory.chat_memory.add_user_message(player_input)
        self.memory.chat_memory.add_ai_message(reply)

        # Step 6: 矛盾检测（防线 > 0 时才检测）
        defense_delta = 0
        contradiction_detected = False
        contradiction_reason = ""

        if self.defense_score > 0:
            contradiction_result = self._detect_contradiction(reply)
            if contradiction_result.get("has_contradiction"):
                contradiction_detected = True
                contradiction_reason = contradiction_result.get(
                    "contradiction_reason", ""
                )
                penalty = contradiction_result.get("defense_penalty", 15)
                defense_delta = -penalty

                # 记录谎言到数据库
                DBHelper.add_lie(
                    self.session_id,
                    self.suspect_id,
                    statement=reply,
                    contradiction=contradiction_reason,
                    defense_penalty=penalty,
                )

        # Step 7: 出示弱点证物时额外扣分
        if self.current_confrontation_item:
            defense_delta -= 30  # 出示物证直接 -30
            self.current_confrontation_item = None  # 对质一次后重置

        # Step 8: 更新防线
        if defense_delta != 0:
            self._update_defense(defense_delta)

        # Step 9: 检查是否崩溃
        is_broken = self.defense_score < 10

        return {
            "reply": reply,
            "defense_delta": defense_delta,
            "contradiction_detected": contradiction_detected,
            "contradiction_reason": contradiction_reason,
            "defense_score": self.defense_score,
            "is_broken": is_broken,
        }