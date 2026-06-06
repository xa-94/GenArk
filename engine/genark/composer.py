"""拼版日报：多智能体日报组装 + 交汇小节检测 + 关系趋势 + 推送"""

import json
from datetime import datetime, timedelta

from .db import get_conn
from .reporter import generate_report, save_report
from .pusher import push_composed
from .relations import compute_relations


def detect_intersections(agents: list[str], date: str) -> list[dict]:
    """检测同日跨智能体的 @ 交互事件。

    从 events 表查 role=user 且 content 含 @ 的消息，
    按时间排序，每条消息作为一个交汇点。
    """
    if len(agents) < 2:
        return []

    placeholders = ",".join("?" * len(agents))
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT id, agent_id, timestamp, json_extract(payload, '$.content') as content
                FROM events
                WHERE agent_id IN ({placeholders})
                AND event_type = 'session_message'
                AND json_extract(payload, '$.role') = 'user'
                AND json_extract(payload, '$.content') LIKE '%@%'
                AND date(timestamp) = ?
                ORDER BY timestamp""",
            (*agents, date),
        ).fetchall()

    intersections = []
    for r in rows:
        content = r["content"] or ""
        import re
        mentioned = re.findall(r"@(\S+)", content)
        intersections.append({
            "event_id": r["id"],
            "time": r["timestamp"][11:16] if r["timestamp"] else "?",
            "source_agent": r["agent_id"],
            "content": content[:200],
            "mentions": mentioned,
        })

    return intersections


def _check_intersection_quality(
    agents: list[str], date: str
) -> dict:
    """快速检查当日交汇数据质量。

    对比各 agent 的 @ 消息数。如果只有一个 agent 有 @ 而另一个没有，
    说明数据不对称，交汇不可靠。

    Returns:
        {"reliable": bool, "reason": str, "counts": dict}
    """
    if len(agents) < 2:
        return {"reliable": False, "reason": "单人模式", "counts": {}}

    placeholders = ",".join("?" * len(agents))
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT agent_id, COUNT(*) as cnt
                FROM events
                WHERE agent_id IN ({placeholders})
                AND event_type = 'session_message'
                AND json_extract(payload, '$.role') = 'user'
                AND json_extract(payload, '$.content') LIKE '%@%'
                AND date(timestamp) = ?
                GROUP BY agent_id""",
            (*agents, date),
        ).fetchall()

    counts = {r["agent_id"]: r["cnt"] for r in rows}

    # 如果所有 agent 都没有 @ → 无交汇，不是不可靠
    if sum(counts.values()) == 0:
        return {"reliable": True, "reason": "今日无交汇", "counts": counts}

    # 如果只有一方有 @ → 数据不对称
    active = [a for a, c in counts.items() if c > 0]
    if len(active) == 1:
        return {
            "reliable": False,
            "reason": f"仅 {active[0]} 侧有 @ 信号",
            "counts": counts,
        }

    return {"reliable": True, "reason": "双方均有 @ 信号", "counts": counts}


def compose_daily(
    agents: list[str] | None = None,
    date: str | None = None,
    push: bool = True,
) -> dict:
    """生成拼版日报。

    流程：
    1. 为每个 agent 生成独立日报（如已存在则跳过）
    2. 检测交汇事件 + 质量门禁
    3. 计算关系趋势
    4. 组装拼版文档
    5. 推送到钉钉（可选）
    """
    if agents is None:
        agents = ["guyuan", "heming", "shoushan", "xiangai"]
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # 1. 生成各 agent 日报 + 采集
    reports = []
    for agent_id in agents:
        from .collector import collect
        from .memory_watcher import watch_memories, watch_skills

        # 采集当日新数据
        collect(agent_id)
        watch_memories(agent_id)
        watch_skills(agent_id)

        report = generate_report(agent_id, date)
        save_report(report)
        reports.append(report)

    # 2. 交汇检测 + 质量门禁
    intersections = detect_intersections(agents, date)
    quality = _check_intersection_quality(agents, date)

    # 3. 关系趋势
    relations = compute_relations(agents, weeks=4)

    # 4. 组装
    composed = _assemble(reports, intersections, quality, relations, date)

    # 5. 推送
    if push:
        push_composed(composed)

    return composed


def _build_learnings_panel(date: str) -> str | None:
    """构建 learnings 面板文本（Phase 3 日报 2.0）。

    展示：当日新增 / 待审核数 / 最近 3 条标题。
    如果 learnings 表不存在或无数据，返回 None（不显示）。
    """
    try:
        with get_conn() as conn:
            # 检查表是否存在
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='learnings'"
            ).fetchone()
            if not exists:
                return None

            # 当日新增
            today_new = conn.execute(
                "SELECT COUNT(*) FROM learnings WHERE date(created_at) = ?",
                (date,),
            ).fetchone()[0]

            # 待审核数
            pending = conn.execute(
                "SELECT COUNT(*) FROM learnings WHERE status = 'pending'"
            ).fetchone()[0]

            # 全部为零则跳过
            if today_new == 0 and pending == 0:
                return None

            # 最近 3 条
            recent = conn.execute(
                """SELECT id, source_type, content, category
                   FROM learnings
                   WHERE status = 'pending'
                   ORDER BY created_at DESC
                   LIMIT 3"""
            ).fetchall()

            lines = ["🧠 知识沉淀"]
            lines.append(f"   当日新增 {today_new} · 待审核 {pending}")

            if recent:
                lines.append("   最近入库：")
                type_icon = {
                    "bug_fix": "🐛",
                    "correction": "✏️",
                    "pattern": "📐",
                    "convention": "📋",
                }
                for r in recent:
                    icon = type_icon.get(r["source_type"], "📌")
                    cat = f" [{r['category']}]" if r["category"] else ""
                    content = r["content"][:80].replace("\n", " ")
                    lines.append(f"   {icon} #{r['id']}{cat} {content}...")

            return "\n".join(lines)

    except Exception:
        # 表不存在或其他异常 → 静默跳过，不影响日报主流程
        return None


def _assemble(
    reports: list[dict],
    intersections: list[dict],
    quality: dict,
    relations: dict,
    date: str,
) -> dict:
    """组装拼版日报文本"""
    agent_names = {
        "guyuan": ("顾远", "PM"),
        "heming": ("赫明", "Tech Lead"),
        "shoushan": ("守山", "主智能体"),
    }

    lines = [f"📊 GenArk 日报 · {date}", "═" * 35]

    for i, r in enumerate(reports):
        aid = r["agent_id"]
        name, role = agent_names.get(aid, (aid, ""))
        stats = r["stats"]

        if i > 0:
            lines.append("─" * 35)

        lines.append(f"\n👤 {name}（{role}）")
        lines.append(
            f"📊 会话 {stats['sessions']} · "
            f"消息 {stats['messages_sent']} · "
            f"工具 {stats['tool_calls']} · "
            f"成功率 {int(stats['tool_success_rate'] * 100)}%"
        )
        lines.append(f"🧠 {r['narrative']}")

    # ── 交汇小节（带质量门禁）──
    if intersections and quality["reliable"]:
        lines.append("═" * 35)
        lines.append("🔗 今日交汇\n")
        for ix in intersections[:5]:  # 最多 5 条
            name = agent_names.get(ix["source_agent"], (ix["source_agent"], ""))[0]
            lines.append(
                f"→ {ix['time']} {name}侧：{ix['content'][:120]}"
                f"【{ix['event_id']}】"
            )
    elif intersections and not quality["reliable"]:
        lines.append("═" * 35)
        lines.append(f"🔗 今日交汇")
        lines.append(f"（检测到 {len(intersections)} 条互动信号，但数据不对称——"
                     f"{quality['reason']}，细节暂略）")
    # else: 无交汇 → 不显示交汇小节

    # ── 关系趋势 ──
    if relations and relations.get("pairs"):
        lines.append("═" * 35)
        lines.append("📈 关系趋势（近 4 周）")
        name_map = {"guyuan": "顾远", "heming": "赫明", "shoushan": "守山", "xiangai": "祥霭分身"}
        for agent_id, data in relations["pairs"].items():
            name = name_map.get(agent_id, agent_id)
            lines.append(
                f"{name} 被 @ {data['total_mentions']} 次 "
                f"· 趋势 {data['trend_icon']} "
                f"· {data['bar']}"
            )

    # ── Learnings 面板（Phase 3 日报 2.0）──
    learnings_panel = _build_learnings_panel(date)
    if learnings_panel:
        lines.append("═" * 35)
        lines.append(learnings_panel)

    narrative = "\n".join(lines)

    return {
        "date": date,
        "agents": [r["agent_id"] for r in reports],
        "narrative": narrative,
        "intersections": len(intersections),
        "reports": [r["id"] for r in reports],
    }
