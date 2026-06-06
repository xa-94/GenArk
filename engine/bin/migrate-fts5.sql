-- GenArk Phase 4 — FTS5 全文搜索迁移
-- 用途: 为 learnings 表建立 FTS5 全文索引，支持中文分词 + BM25 排序
-- 幂等: IF NOT EXISTS + 安全 rebuild，重复执行安全

-- 1. 创建 FTS5 虚拟表（simple tokenizer：中文逐字 + 英文分词）
CREATE VIRTUAL TABLE IF NOT EXISTS learnings_fts USING fts5(
    content,
    category,
    source_type,
    content='learnings',
    content_rowid='id'
);

-- 2. 初始填充：rebuild 已有 learnings
INSERT INTO learnings_fts(learnings_fts) VALUES('rebuild');

-- 3. 触发器：INSERT 自动同步
CREATE TRIGGER IF NOT EXISTS learnings_ai AFTER INSERT ON learnings BEGIN
    INSERT INTO learnings_fts(rowid, content, category, source_type)
    VALUES (new.id, new.content, new.category, new.source_type);
END;

-- 4. 触发器：DELETE 自动同步
CREATE TRIGGER IF NOT EXISTS learnings_ad AFTER DELETE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, content, category, source_type)
    VALUES('delete', old.id, old.content, old.category, old.source_type);
END;

-- 5. 触发器：UPDATE 自动同步
CREATE TRIGGER IF NOT EXISTS learnings_au AFTER UPDATE ON learnings BEGIN
    INSERT INTO learnings_fts(learnings_fts, rowid, content, category, source_type)
    VALUES('delete', old.id, old.content, old.category, old.source_type);
    INSERT INTO learnings_fts(rowid, content, category, source_type)
    VALUES (new.id, new.content, new.category, new.source_type);
END;
