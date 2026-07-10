-- ============================================================
-- 审讯室风云 — SQLite 数据库建表脚本
-- 对应技术文档 第七章：后端架构与数据模型设计
-- 成员 A 制定，全员基于此 Schema 进行解耦开发
-- ============================================================

-- 1. 游戏会话表（案件基本状态）
CREATE TABLE IF NOT EXISTS case_session (
    session_id          TEXT PRIMARY KEY,
    case_style          TEXT,              -- 剧本风格：manor / steampunk
    case_name           TEXT,              -- 案件名称
    current_action_points INT DEFAULT 10,  -- 剩余行动点数
    current_suspect_id  TEXT,              -- 当前正在审讯的嫌疑人 ID
    phase               TEXT DEFAULT 'investigation',  -- 游戏阶段: investigation / interrogation / verdict
    need_approval       INT DEFAULT 0,     -- 人机协同拦截标记 (Human-in-the-loop)
    is_completed        INT DEFAULT 0,     -- 案件是否已结案
    created_at          TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at          TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 2. 嫌疑人状态表
CREATE TABLE IF NOT EXISTS suspect_status (
    session_id      TEXT NOT NULL,
    suspect_id      TEXT NOT NULL,
    name            TEXT,                  -- 嫌疑人姓名
    role            TEXT,                  -- 身份：管家 / 富商 / 法医
    avatar          TEXT,                  -- 头像图片路径
    defense_score   INT DEFAULT 100,       -- 实时心理防线 (0-100)
    expression_state TEXT DEFAULT 'calm',  -- 表情状态: calm / nervous / broken
    profile_json    TEXT,                  -- 完整人设 JSON (hidden_truth, alibi, weakness 等)
    is_arrested     INT DEFAULT 0,         -- 是否已被逮捕
    is_released     INT DEFAULT 0,         -- 是否已被保释
    PRIMARY KEY (session_id, suspect_id)
);

-- 3. 证物清单表
CREATE TABLE IF NOT EXISTS evidence_inventory (
    session_id          TEXT NOT NULL,
    evidence_id         TEXT NOT NULL,
    name                TEXT,              -- 证物名称
    description         TEXT,              -- 证物描述
    category            TEXT DEFAULT 'physical',  -- 类别: weapon / document / forensic / testimony
    related_suspect_id  TEXT,              -- 关联嫌疑人（弱点指向）
    is_discovered       INT DEFAULT 0,     -- 是否已被玩家搜查获得
    is_analyzed         INT DEFAULT 0,     -- 法医化验是否完成
    analysis_result     TEXT,              -- 化验结果文本
    analysis_pending    INT DEFAULT 0,     -- 是否已送检但未出结果
    PRIMARY KEY (session_id, evidence_id)
);

-- 4. 对话历史表（用于记忆窗口 & 前后端状态同步）
CREATE TABLE IF NOT EXISTS chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    suspect_id  TEXT,                      -- 当前对话对象
    role        TEXT NOT NULL,             -- player / suspect / system
    content     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 5. 法医异步任务队列表
CREATE TABLE IF NOT EXISTS forensic_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    evidence_id     TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',  -- pending / processing / completed
    result          TEXT,                    -- 化验结果
    created_at      TEXT DEFAULT (datetime('now', 'localtime')),
    completed_at    TEXT
);

-- 6. 谎言追踪表（记忆一致性检测）
CREATE TABLE IF NOT EXISTS lie_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    suspect_id      TEXT NOT NULL,
    statement       TEXT,                    -- 嫌疑人声称的内容
    contradiction   TEXT,                    -- 与之矛盾的事实或前文
    evidence_id     TEXT,                    -- 指向矛盾的证物
    is_exposed      INT DEFAULT 0,           -- 是否已被玩家揭穿
    defense_penalty INT DEFAULT 0,           -- 揭穿后扣减的防线值
    created_at      TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 索引：加速查询
CREATE INDEX IF NOT EXISTS idx_chat_session   ON chat_history(session_id, suspect_id);
CREATE INDEX IF NOT EXISTS idx_evidence_session ON evidence_inventory(session_id);
CREATE INDEX IF NOT EXISTS idx_forensic_status ON forensic_queue(session_id, status);
CREATE INDEX IF NOT EXISTS idx_lie_suspect     ON lie_ledger(session_id, suspect_id);
