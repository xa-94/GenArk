"""状态计算器 — 纯规则计算，不依赖 LLM"""

import json
from datetime import datetime

from .db import get_conn


def _is_tool_failure(content: str) -> bool:
    """结构化判定工具调用是否失败。"""
    if not content:
        return False
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        # 非 JSON 输出，回退到保守的字符串匹配
        return "error" in content.lower() or "fail" in content.lower()

    if not isinstance(data, dict):
        return False

    # 显式 success: false
    if data.get("success") is False:
        return True

    # 有 error 字段且值非空（排除 "error": null），且没有 success: true
    if data.get("error") and data.get("success") is not True:
        return True

    # 终端工具：exit_code != 0
    if "exit_code" in data and data["exit_code"] != 0:
        return True

    return False


def compute_daily_stats(agent_id: str, date: str | None = None) -> dict:
    """计算指定日期的智能体状态统计"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, event_type, payload, timestamp
               FROM events
               WHERE agent_id = ? AND date(timestamp) = ?
               ORDER BY timestamp""",
            (agent_id, date),
        ).fetchall()

        session_files = set()
        message_count = 0
        tool_count = 0
        tool_success = 0
        tool_fail = 0
        roles = {"user": 0, "assistant": 0, "tool": 0}

        for r in rows:
            payload = json.loads(r["payload"])
            if r["event_type"] == "session_message":
                src = payload.get("source_file", "")
                if src:
                    session_files.add(src)
                role = payload.get("role", "")
                if role in roles:
                    roles[role] += 1
                message_count += 1
                if role == "tool":
                    tool_count += 1
                    content = payload.get("content", "")
                    if _is_tool_failure(content):
                        tool_fail += 1
                    else:
                        tool_success += 1

        memory_changes = sum(1 for r in rows if r["event_type"] == "memory_change")
        skill_changes = sum(1 for r in rows if r["event_type"] == "skill_change")

        hours = [0] * 24
        for r in rows:
            ts = r["timestamp"]
            try:
                h = int(ts[11:13])
                if 0 <= h < 24:
                    hours[h] += 1
            except (ValueError, IndexError):
                pass
        peak_hour = hours.index(max(hours)) if any(hours) else 0

        total_tool = tool_success + tool_fail
        success_rate = round(tool_success / total_tool, 2) if total_tool > 0 else 1.0

        return {
            "date": date,
            "agent_id": agent_id,
            "sessions": len(session_files),
            "messages_sent": roles.get("assistant", 0),
            "total_events": len(rows),
            "tool_calls": tool_count,
            "tool_success_rate": success_rate,
            "memory_changes": memory_changes,
            "skill_changes": skill_changes,
            "peak_hour": f"{peak_hour:02d}:00",
            "roles": roles,
        }


def get_event_summaries(agent_id: str, date: str, max_items: int = 30) -> list[dict]:
    """获取当天事件摘要列表"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, event_type, payload, timestamp
               FROM events
               WHERE agent_id = ? AND date(timestamp) = ?
               ORDER BY timestamp
               LIMIT ?""",
            (agent_id, date, max_items),
        ).fetchall()

        summaries = []
        for r in rows:
            payload = json.loads(r["payload"])
            if r["event_type"] == "session_message":
                role = payload.get("role", "?")
                tool = payload.get("tool_name", "")
                content = payload.get("content", "")
                summaries.append({
                    "event_id": r["id"],
                    "time": r["timestamp"][11:16] if r["timestamp"] else "?",
                    "type": f"tool:{tool}" if tool else f"msg:{role}",
                    "summary": content[:150],
                })
            elif r["event_type"] == "memory_change":
                summaries.append({
                    "event_id": r["id"],
                    "time": r["timestamp"][11:16] if r["timestamp"] else "?",
                    "type": "memory",
                    "summary": f"记忆已更新：{payload.get('file', '?')}（{payload.get('entry_count', 0)}条）",
                })
            elif r["event_type"] == "skill_change":
                summaries.append({
                    "event_id": r["id"],
                    "time": r["timestamp"][11:16] if r["timestamp"] else "?",
                    "type": "skill",
                    "summary": f"技能面板已更新：共 {payload.get('total_skills', 0)} 项技能",
                })

        return summaries
