#!/usr/bin/env python3
"""GenArk Phase 3 — learnings 审核预筛

三级评定策略：
  第1轮：Jaccard 去重（相似度>70% → 保留第1条，其余 REJECT）
  第2轮：硬信号评分（路径/数字/角色名 → APPROVE；太短/太泛 → REJECT）
  第3轮：动作词放宽（禁止/必须/不要/原则/否则/避免/如 → 评分≥2 → APPROVE）

安全原则：宁保守不漏。边界案例留 PENDING 等祥霭拍板。

用法: uv run python bin/review-screen.py [--dry-run]
"""
import sqlite3
import sys
from collections import Counter

DB_PATH = "/data/projects/genark/engine/data/genark.db"
DRY_RUN = "--dry-run" in sys.argv


def word_set(text):
    return set(
        w.strip(".,;:()[]\u201c\u201d\u2018\u2019")
        for w in text.lower().split()
        if len(w.strip(".,;:()[]\u201c\u201d\u2018\u2019")) >= 2
    )


def similarity(a, b):
    wa, wb = word_set(a), word_set(b)
    if not wa or not wb:
        return 0
    return len(wa & wb) / len(wa | wb)


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT * FROM learnings WHERE status='pending' ORDER BY created_at"
).fetchall()

print(f"待审核 learnings: {len(rows)} 条\n")

# ── 第1轮：去重 ──
dup_ids = set()
dup_pairs = []
for i in range(len(rows)):
    for j in range(i + 1, len(rows)):
        sim = similarity(rows[i]["content"], rows[j]["content"])
        if sim > 0.7:
            dup_ids.add(rows[j]["id"])
            dup_pairs.append((rows[i]["id"], rows[j]["id"], sim))

print(f"[第1轮] 去重: 发现 {len(dup_pairs)} 对重复 (Jaccard>70%)")
for a, b, sim in dup_pairs:
    print(f"  #{a} ≈ #{b} (sim={sim:.2f}) → REJECT #{b}")

# ── 第2轮：硬信号评分 ──
approved, rejected, pending = [], [], []
vague_words = ["注意", "建议", "可以考虑", "视情况", "尽量", "应该", "好的实践"]

for r in rows:
    rid, content, stype, cby = r["id"], r["content"], r["source_type"], r["created_by"]
    if rid in dup_ids:
        rejected.append(rid)
        continue
    if len(content) < 30:
        rejected.append(rid)
        continue
    vague_count = sum(1 for w in vague_words if w in content)
    if vague_count >= 3 and len(content) < 150:
        rejected.append(rid)
        continue

    has_specific = any(
        [
            "/" in content and any(c.isalpha() for c in content.split("/")[0]),
            any(c.isdigit() for c in content),
            any(
                name in content
                for name in ["heming", "guyuan", "shoushan", "顾远", "赫明", "守山", "祥霭"]
            ),
        ]
    )
    if 50 <= len(content) <= 300 and has_specific:
        approved.append(rid)
    elif stype == "correction" and has_specific:
        approved.append(rid)
    else:
        pending.append(rid)

print(f"\n[第2轮] 硬信号评分: APPROVED={len(approved)} REJECTED={len(rejected)} PENDING={len(pending)}")

# ── 第3轮：动作词放宽 ──
still_pending = []
round3_approved = 0
for r in rows:
    if r["id"] not in pending:
        continue
    content = r["content"]
    has_action = any(
        kw in content
        for kw in ["禁止", "必须", "不", "不要", "用", "先", "前", "后", "改", "检查", "确认", "验证"]
    )
    has_rule = any(
        kw in content for kw in ["原则", "规则", "流程", "规范", "格式", "模式", "方法"]
    )
    has_why = any(
        kw in content
        for kw in ["因为", "否则", "避免", "防止", "导致", "造成", "原因", "根因"]
    )
    has_example = any(
        kw in content for kw in ["如", "比如", "例如", "实例"]
    )
    score = sum([has_action, has_rule, has_why, has_example])
    if score >= 2:
        approved.append(r["id"])
        round3_approved += 1
    elif score == 1 and len(content) >= 50:
        approved.append(r["id"])
        round3_approved += 1
    elif len(content) < 30:
        rejected.append(r["id"])
    else:
        still_pending.append(r["id"])

print(f"\n[第3轮] 动作词放宽: +{round3_approved} APPROVED → 最终 PENDING={len(still_pending)}")

# ── 汇总 ──
print(f"\n{'='*50}")
print(f"汇总: APPROVED={len(approved)}  REJECTED={len(rejected)}  PENDING={len(still_pending)}")
print(f"{'='*50}")

# 详细列表
pending_details = [r for r in rows if r["id"] in still_pending]
if pending_details:
    print(f"\n🟡 PENDING ({len(pending_details)} 条) — 需祥霭拍板:")
    for r in pending_details:
        print(f"  #{r['id']} [{r['created_by']}] {r['content'][:80]}...")

rejected_details = [r for r in rows if r["id"] in rejected]
if rejected_details:
    print(f"\n🔴 REJECTED ({len(rejected_details)} 条):")
    for r in rejected_details:
        print(f"  #{r['id']} [{r['created_by']}] {r['content'][:80]}...")

if DRY_RUN:
    print("\n⚠️  DRY RUN — 未写入数据库。去掉 --dry-run 执行实际更新。")
else:
    for rid in approved:
        conn.execute(
            "UPDATE learnings SET status='approved', reviewed_at=datetime('now'), reviewed_by='shoushan' WHERE id=?",
            (rid,),
        )
    for rid in rejected:
        conn.execute(
            "UPDATE learnings SET status='rejected', reviewed_at=datetime('now'), reviewed_by='shoushan' WHERE id=?",
            (rid,),
        )
    conn.commit()
    actual_approved = conn.execute(
        "SELECT COUNT(*) FROM learnings WHERE status='approved'"
    ).fetchone()[0]
    actual_rejected = conn.execute(
        "SELECT COUNT(*) FROM learnings WHERE status='rejected'"
    ).fetchone()[0]
    actual_pending = len(still_pending)
    print(f"\n✅ 已写入 | APPROVED={actual_approved} REJECTED={actual_rejected} PENDING={actual_pending}")

conn.close()
