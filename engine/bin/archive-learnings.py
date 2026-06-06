#!/usr/bin/env python3
"""GenArk Phase 4 — learnings 归档消费

用法: uv run python bin/archive-learnings.py [--dry-run]
"""
import argparse, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

from genark.db import get_conn

AGENT_MAP = {"guyuan": "顾远", "heming": "赫明", "shoushan": "守山"}

def determine_agent(content: str, category: str) -> str | None:
    """根据 learnings 内容和分类判断应该推给哪个 Agent。"""
    text = (content + category).lower()
    if any(k in text for k in ["heming", "赫明", "tech lead", "编码", "qoder", "git diff", "spring", "vue"]):
        return "heming"
    if any(k in text for k in ["guyuan", "顾远", "pm", "handoff", "prd", "验收", "产品"]):
        return "guyuan"
    if any(k in text for k in ["shoushan", "守山", "部署", "运维", "cron", "genark", "看板"]):
        return "shoushan"
    return None  # 无法判断，推给守山（默认）

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with get_conn() as conn:
        # 读已审批但未消费的 learnings
        rows = conn.execute("""
            SELECT l.id, l.source_type, l.content, l.category, l.created_by
            FROM learnings l
            WHERE l.status = 'approved'
              AND l.id NOT IN (SELECT learning_id FROM learning_consumptions)
            ORDER BY l.id
        """).fetchall()

        if not rows:
            print("没有待消费的 learnings")
            return

        injections = {"heming": [], "guyuan": [], "shoushan": []}
        consumed = 0

        for r in rows:
            lid, stype, content, category, created_by = r
            target = determine_agent(content, category) or "shoushan"

            entry = {
                "id": lid,
                "type": stype,
                "content": content,
                "category": category,
            }
            injections[target].append(entry)

            if not args.dry_run:
                conn.execute("""
                    INSERT OR IGNORE INTO learning_consumptions (learning_id, consumed_by, action, context, created_at)
                    VALUES (?, ?, 'queued', ?, ?)
                """, (lid, target, f"auto-routed from {created_by}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            consumed += 1

        if not args.dry_run:
            conn.commit()

    # 输出注入文件
    out_dir = os.path.expanduser("~/.hermes/genark-injections")
    os.makedirs(out_dir, exist_ok=True)

    for agent_id, items in injections.items():
        if not items:
            continue
        name = AGENT_MAP.get(agent_id, agent_id)
        count = len(items)
        
        path = os.path.join(out_dir, f"{agent_id}-pending.json")
        payload = {
            "generated_at": datetime.now().isoformat(),
            "agent": agent_id,
            "count": count,
            "items": items,
        }
        with open(path, "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"  {name} ({agent_id}): {count} 条 → {path}")

    total = sum(len(v) for v in injections.values())
    label = "DRY RUN" if args.dry_run else "已消费"
    print(f"\n{'⚠️  ' if args.dry_run else '✅ '}{label}: {total} 条 learnings → {len([v for v in injections.values() if v])} 个 Agent")

if __name__ == "__main__":
    main()
