"""
Mock 数据 — 供前端成员 D 在数据库尚未就绪时独立开发 UI。
数据库模块完成后，前端应切换为从 DBHelper 读取真实数据。
"""

# 当前受审嫌疑人
CURRENT_SUSPECT = {
    "avatar": "assets/images/suspect_a_calm.png",
    "name": "塞巴斯蒂安",
    "role": "庄园管家",
    "defense": 80,
}

# 对话历史（角色: player / suspect / system）
CHAT_HISTORY = [
    {"role": "system", "content": "--- 审讯开始 ---"},
    {"role": "player", "content": "塞巴斯蒂安先生，案发当晚九点你在哪里？"},
    {"role": "suspect", "content": "警官，我在酒窖整理红酒，考勤卡可以证明我的清白。"},
    {"role": "player", "content": "但我们在书房抽屉上发现了你的指纹。"},
    {"role": "suspect", "content": "……我必须纠正，那是下午去送文件时留下的。"},
]

# 已搜集证物列表
EVIDENCES = [
    {"name": "📜 口供记录 — 不在场证明"},
    {"name": "🧪 血液化验单 — A型血迹"},
    {"name": "🛠️ 带血的开瓶器"},
    {"name": "📇 值班室考勤卡"},
]
