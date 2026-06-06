-- GenArk Phase 3 — 知识层架构迁移
-- 来源: .qoder/reports/genark-phase3-tech-assessment-2026-06-06.md §4.1
-- 日期: 2026-06-06
-- 执行: 守山
-- 用途: 为 learnings 闭环建立三张核心表
-- 幂等: CREATE TABLE IF NOT EXISTS，重复执行安全

-- learnings 主表：存储 Agent 行为 pattern、correction、bug_fix、convention
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('bug_fix', 'correction', 'pattern', 'convention')),
    source_ref TEXT,           -- 关联 events.id 或 handoff 路径
    content TEXT NOT NULL,     -- learning 正文
    category TEXT,             -- 分类标签
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    confidence REAL,           -- 0.0-1.0
    created_by TEXT NOT NULL,  -- heming / shoushan / guyuan / system
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewed_by TEXT
);

-- learning_embeddings：向量索引表（Phase 3 建表但暂不填充）
CREATE TABLE IF NOT EXISTS learning_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    embedding BLOB,            -- Phase 3 建表但暂不填充
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- learning_consumptions：学习消费追踪表
CREATE TABLE IF NOT EXISTS learning_consumptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    consumed_by TEXT NOT NULL, -- heming / shoushan / guyuan
    action TEXT NOT NULL,      -- view / apply / reject
    context TEXT,              -- 消费场景描述
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
