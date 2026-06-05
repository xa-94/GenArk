"""关系网络：跨智能体 @ 频次统计 + 趋势曲线"""

from datetime import datetime, timedelta

from .db import get_conn


def compute_relations(agents: list[str] | None = None, weeks: int = 4) -> dict:
    """计算智能体间关系统计 + 趋势。

    纯规则，零 LLM。
    """
    if agents is None:
        agents = ["guyuan", "heming", "shoushan"]

    since = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
    placeholders = ",".join("?" * len(agents))

    with get_conn() as conn:
        # 按周统计 @ 频次
        rows = conn.execute(
            f"""SELECT 
                    strftime('%Y-%W', timestamp) as week,
                    agent_id,
                    COUNT(*) as cnt
                FROM events
                WHERE agent_id IN ({placeholders})
                AND event_type = 'session_message'
                AND json_extract(payload, '$.role') = 'user'
                AND json_extract(payload, '$.content') LIKE '%@%'
                AND date(timestamp) >= ?
                GROUP BY week, agent_id
                ORDER BY week""",
            (*agents, since),
        ).fetchall()

        # 按 agent 整理周数据
        weekly: dict[str, list[int]] = {a: [0] * weeks for a in agents}
        week_labels = []
        for r in rows:
            agent = r["agent_id"]
            week = r["week"]
            if week not in week_labels:
                week_labels.append(week)
            idx = week_labels.index(week) if week in week_labels else -1
            if 0 <= idx < weeks:
                weekly[agent][idx] = r["cnt"]

        # 总 @ 次数 & 趋势判定
        pairs = {}
        for agent in agents:
            total = sum(weekly[agent])
            w = weekly[agent]
            # 趋势：比较前半段 vs 后半段
            mid = weeks // 2
            first_half = sum(w[:mid])
            second_half = sum(w[mid:])
            if second_half > first_half * 1.2:
                trend = "rising"
            elif first_half > second_half * 1.2:
                trend = "declining"
            else:
                trend = "stable"

            pairs[agent] = {
                "total_mentions": total,
                "trend": trend,
                "weekly": w,
                "trend_icon": {"rising": "↗", "declining": "↘", "stable": "→"}[trend],
                "bar": _trend_bar(w),
            }

        return {
            "agents": agents,
            "weeks": weeks,
            "week_labels": week_labels,
            "pairs": pairs,
        }


def _trend_bar(values: list[int], max_width: int = 12) -> str:
    """Unicode 迷你趋势柱状图"""
    if not values or max(values) == 0:
        return "▁" * len(values)
    bars = "▁▂▃▄▅▆▇█"
    normalized = [int(v / max(values) * (len(bars) - 1)) for v in values]
    return "".join(bars[min(n, len(bars) - 1)] for n in normalized)


def format_relations(relations: dict) -> str:
    """格式化关系面板为文本"""
    lines = ["👥 关系面板（最近 {} 周）".format(relations["weeks"]), ""]
    name_map = {"guyuan": "顾远", "heming": "赫明", "shoushan": "守山"}

    for agent_id, data in relations["pairs"].items():
        name = name_map.get(agent_id, agent_id)
        lines.append(
            f"{name} 被 @ {data['total_mentions']} 次 "
            f"· 趋势 {data['trend_icon']} "
            f"· 周频次: {data['bar']}"
        )

    return "\n".join(lines)
