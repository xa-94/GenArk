-- Phase 4b: Learning Relations — causality chains
-- 2026-06-06 | 守山

CREATE TABLE IF NOT EXISTS learning_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES learnings(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES learnings(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('caused_by', 'generalizes', 'contradicts', 'same_root')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT NOT NULL DEFAULT 'shoushan',
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    UNIQUE(source_id, target_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_lr_source ON learning_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_lr_target ON learning_relations(target_id);
CREATE INDEX IF NOT EXISTS idx_lr_type ON learning_relations(relation_type);
