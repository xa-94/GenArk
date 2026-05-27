"""拼版日报：多智能体日报组装 + 交汇小节检测"""

import json
from datetime import datetime

from .db import get_conn
from .reporter import generate_report, save_report


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
        # 提取被 @ 的 bot 名
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


def compose_daily(
    agents: list[str] | None = None,
    date: str | None = None,
) -> dict:
    """生成拼版日报。

    流程：
    1. 为每个 agent 生成独立日报（如已存在则跳过）
    2. 检测交汇事件
    3. 组装拼版文档
    """
    if agents is None:
        agents = ["guyuan", "heming"]
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    reports = []
    for agent_id in agents:
        report = generate_report(agent_id, date)
        save_report(report)
        reports.append(report)

    intersections = detect_intersections(agents, date)

    composed = _assemble(reports, intersections, date)
    return composed


def _assemble(reports: list[dict], intersections: list[dict], date: str) -> dict:
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

    # 交汇小节
    if intersections:
        lines.append("═" * 35)
        lines.append("🔗 今日交汇\n")
        for ix in intersections[:5]:  # 最多 5 条
            name = agent_names.get(ix["source_agent"], (ix["source_agent"], ""))[0]
            lines.append(
                f"→ {ix['time']} {name}侧：{ix['content'][:120]}"
                f"【{ix['event_id']}】"
            )

    narrative = "\n".join(lines)

    return {
        "date": date,
        "agents": [r["agent_id"] for r in reports],
        "narrative": narrative,
        "intersections": len(intersections),
        "reports": [r["id"] for r in reports],
    }
