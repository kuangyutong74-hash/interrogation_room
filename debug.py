# debug.py

# %% [markdown]
# ### 1. 导入库与加载环境变量
import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
# 导入 LangChain 的 Pydantic 输出解析器
from langchain_core.output_parsers import PydanticOutputParser

load_dotenv()

# %% [markdown]
# ### 2. 定义数据结构契约 (Schema) - 保持不变
class SuspectSchema(BaseModel):
    suspect_id: str = Field(description="嫌疑人唯一ID，如 suspect_a, suspect_b, suspect_c")
    name: str = Field(description="嫌疑人姓名")
    role: str = Field(description="嫌疑人身份或职业")
    alibi: str = Field(description="嫌疑人的公开不在场证明（其中包含逻辑漏洞）")
    hidden_truth: str = Field(description="嫌疑人隐瞒的真实去向或行为（必须与漏洞对应）")
    weakness_item: str = Field(description="能戳穿其不在场证明的物证ID（对应下面物证的 evidence_id）")

class EvidenceSchema(BaseModel):
    evidence_id: str = Field(description="物证唯一ID，如 evidence_1, evidence_2")
    name: str = Field(description="物证名称")
    description: str = Field(description="物证的详细物理描述，以及化验后能发现的线索（如指纹、血迹）")
    location_found: str = Field(description="搜查哪里可以获得此物证")

class CaseScriptSchema(BaseModel):
    case_name: str = Field(description="案件名称，要求有悬疑感")
    background: str = Field(description="案发现场整体背景，包含死者死因、死亡时间、尸体被发现的惨状")
    suspects: List[SuspectSchema] = Field(description="必须生成且仅生成3个嫌疑人，其中1人是真凶")
    evidences: List[EvidenceSchema] = Field(description="必须生成至少3件关键物证，其中必须包含指向真凶弱点的致命物证")

# %% [markdown]
# ### 3. 初始化 Pydantic 解析器并动态构建 Prompt
# 初始化解析器
parser = PydanticOutputParser(pydantic_object=CaseScriptSchema)

# 将解析器生成的格式说明注入到 System Prompt 中，强制 DeepSeek 配合
generator_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    你是一名天才侦探小说家，善于设计严密的逻辑闭环推理剧本。
    请根据用户指定的【剧本风格】，生成一套完整的谋杀案剧本。
    
    【核心逻辑约束】：
    1. 必须有3个嫌疑人，其中只有1个是真凶。
    2. 每个嫌疑人都有一个口头上的“不在场证明 (alibi)”。
    3. 必须生成对应的“物证 (evidences)”。
    4. 真凶的“不在场证明”必须与某件物证的物理特征或发现位置产生不可调和的逻辑冲突。
    5. 另外两个无辜嫌疑人的不在场证明必须是真实的，或者他们的漏洞与凶杀案无关。
    6. 所有的 id（suspect_id, evidence_id）必须严格对应，确保程序可以通过 weakness_item 检索到对应的物证。
    
    {format_instructions}
    """),
    ("human", "请生成一个【{theme}】风格的剧本。")
]).partial(format_instructions=parser.get_format_instructions()) # 注入格式约束

# %% [markdown]
# ### 4. 运行 DeepSeek 并通过 Parser 解析
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com",
    temperature=0.7
)

# 拼装 Chain：输入 -> 提示词 -> 语言模型 -> 解析器
generator_chain = generator_prompt | llm | parser

theme_test = "中世纪魔法庄园"
print(f"正在使用 DeepSeek 生成 【{theme_test}】 剧本...")
try:
    # 运行并自动解析为 CaseScriptSchema Pydantic 对象
    script_output = generator_chain.invoke({"theme": theme_test})
    
    # 打印转换成功的字典结构
    import json
    print(json.dumps(script_output.model_dump(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f"生成或解析失败，错误信息: {e}")
# %% [markdown]
# ### 5. 测试嫌疑人实时对话（动态语气注入版）

# 1. 模拟数据与防线值
sedric_profile = script_output.suspects[1] 

# 【你可以随意修改这个数值进行测试：100, 45, 25, 5】
current_defense = 100

# 2. 用 Python 进行数值逻辑判断，生成明确的“语气修饰词（Mood Modifier）”
if current_defense >= 80:
    mood_modifier = "你现在【极其冷静、傲慢】，态度强硬，坚信警官拿你没办法，语气生硬官僚，对提问不屑一顾。"
elif current_defense >= 50:
    mood_modifier = "你感到【有些压力】，不再像刚才那样傲慢。你开始试图用谎言搪塞，说话有些闪烁其词，避重就轻。"
elif current_defense >= 20:
    mood_modifier = "你现在【非常慌张】，额头开始冒冷汗。你发现警官似乎知道了什么，说话开始出现漏洞，吞吞吐吐。"
else:
    mood_modifier = "你已经【极度崩溃、语无伦次】！你极度心虚，双腿颤抖，说话开始口吃、结巴。你感觉自己马上就要坐牢了！"


# 3. 编写系统提示词，直接将计算好的语气修饰词注入进去
suspect_system_prompt = f"""
你正在扮演一名在《请出示证件》风格游戏中的嫌疑人。
你的角色名字是：{sedric_profile.name}
你的身份是：{sedric_profile.role}

【你的秘密（绝对不能主动说出）】：{sedric_profile.hidden_truth}
【你的不在场证明】：{sedric_profile.alibi}

【你当下的情绪与状态（必须严格遵守）】：
{mood_modifier}

【规则】：
请基于上述情绪，简短地（50字以内）回答警官的提问。
"""

# 4. 模拟玩家提问
player_question = "护卫长，昨晚深夜你真的没有离开过庄园大门吗？"

dialogue_prompt = ChatPromptTemplate.from_messages([
    ("system", suspect_system_prompt),
    ("human", "{question}")
])

# 呼叫 DeepSeek
dialogue_chain = dialogue_prompt | llm

reply = dialogue_chain.invoke({"question": player_question})
print(f"当前防线值: {current_defense}/100")
print(f"🕵️ 警官: {player_question}")
print(f"🛡️ {sedric_profile.name}: {reply.content}")

# %%
