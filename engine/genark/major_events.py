"""重大事件检测 — 方案 C 的第二支柱。

纯规则判定，不调 LLM。在拼版日报推送完成后紧跟着推送。
检测四个阈值，触发任一即生成一句话叙事。
"""

from datetime import datetime

from .db import get_conn


# ── 阈值定义 ──

MAJOR_EVENT_THRESHOLDS = {
    "skill_surge": {
        "label": "技能快速成长",
        "test": lambda stats: stats.get("skill_changes", 0) >= 5,
        "template": "{name} 今日技能变化 +{delta} → 正在快速成长",
    },
    "new_skill": {
        "label": "新技能解锁",
        "test": lambda stats: stats.get("new_skills", 0) >= 1,
        "template": "{name} 解锁了新技能！",
    },
    "memory_burst": {
        "label": "记忆爆发",
        "test": lambda stats: stats.get("memory_changes", 0) >= 5,
        "template": "{name} 今天积累了 {delta} 条新记忆",
    },
    "tool_crash": {
        "label": "工具成功率骤降",
        "test": lambda stats: (
            stats.get("tool_calls", 0) >= 5
            and stats.get("tool_success_rate", 1.0) < 0.5
        ),
        "template": "⚠️ {name} 今日工具成功率骤降至 {rate:.0%}，需关注",
    },
}

AGENT_DISPLAY_NAMES = {
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
}


def detect_major_events(agent_id: str, stats: dict) -> list[dict]:
    """检测单个智能体当日的重大事件。

    Returns:
        [{event_type, label, narrative, template}, ...]
    """
    events = []
    for event_type, config in MAJOR_EVENT_THRESHOLDS.items():
        try:
            if config["test"](stats):
                narrative = _format_narrative(
                    agent_id, event_type, config, stats
                )
                events.append({
                    "event_type": event_type,
                    "label": config["label"],
                    "narrative": narrative,
                })
        except Exception:
            # 单个阈值判定失败不影响其他
            continue
    return events


def _format_narrative(
    agent_id: str, event_type: str, config: dict, stats: dict
) -> str:
    """根据模板生成一句话叙事。"""
    name = AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
    template = config["template"]

    if event_type == "skill_surge":
        return template.format(name=name, delta=stats["skill_changes"])
    elif event_type == "memory_burst":
        return template.format(name=name, delta=stats["memory_changes"])
    elif event_type == "tool_crash":
        return template.format(
            name=name, rate=stats["tool_success_rate"]
        )
    else:
        return template.format(name=name)


def build_major_event_message(
    events_by_agent: dict[str, list[dict]],
) -> str | None:
    """将各智能体的重大事件组装为一条推送消息。

    Returns:
        消息文本，如无重大事件返回 None
    """
    if not events_by_agent:
        return None

    lines = ["⚡ 重大事件"]
    for agent_id, events in events_by_agent.items():
        name = AGENT_DISPLAY_NAMES.get(agent_id, agent_id)
        for ev in events:
            lines.append(f"• {ev['narrative']}")

    return "\n".join(lines)
