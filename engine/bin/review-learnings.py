#!/usr/bin/env python3
"""GenArk Phase 3 — 每日 learnings 审核列表

每天 10:00 输出 pending learnings 到 review.log。
Phase 3 人工审核，不自动 approve。
"""
import sqlite3
from datetime import datetime

DB_PATH = "/data/projects/genark/engine/data/genark.db"
LOG_PATH = "/data/projects/genark/engine/data/review.log"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT id, source_type, category, substr(content, 1, 120) as preview, created_by, created_at
    FROM learnings WHERE status='pending'
    ORDER BY created_at DESC
""").fetchall()

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
with open(LOG_PATH, "a") as f:
    f.write(f"\n=== {now} ===\n")
    f.write(f"待审核 learnings: {len(rows)} 条\n")
    for r in rows[:30]:
        f.write(f"  #{r['id']} [{r['source_type']}] {r['category'] or '-'} ({r['created_by']})\n")
        f.write(f"    {r['preview']}...\n")
    if len(rows) > 30:
        f.write(f"  ... 还有 {len(rows) - 30} 条\n")

conn.close()
