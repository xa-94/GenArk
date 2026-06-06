"""query me — 自我审视"""

import json
import os
from datetime import datetime, timedelta

from ..db import get_conn

AGENT_DISPLAY = {
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
}

AGENT_ROLES = {
    "guyuan": "产品经理",
    "heming": "Tech Lead",
    "shoushan": "主智能体",
}


def _detect_agent():
    """从环境变量推断当前 Agent"""
    hermes_home = os.environ.get("HERMES_HOME", "")
    if "heming" in hermes_home:
        return "heming"
    if "guyuan" in hermes_home or "pm" in hermes_home:
        return "guyuan"
    return "shoushan"


def cmd_query_me(args):
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    name = _detect_agent()
    display_name = AGENT_DISPLAY.get(name, name)
    role = AGENT_ROLES.get(name, "未知角色")

    today = datetime.now()
    week_ago = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    try:
        with get_conn() as conn:
            # 本周事件统计
            row = conn.execute(
                """SELECT
                    COUNT(DISTINCT source_path) as sessions,
                    SUM(CASE WHEN event_type = 'session_message' THEN 1 ELSE 0 END) as messages,
                    SUM(CASE WHEN event_type = 'session_message'
                         AND json_extract(payload, '$.role') = 'tool' THEN 1 ELSE 0 END) as tool_calls
                FROM events
                WHERE agent_id = ? AND timestamp >= ?""",
                (name, week_ago),
            ).fetchone()

            sessions = row["sessions"] or 0
            messages = row["messages"] or 0
            tool_calls = row["tool_calls"] or 0
            tool_rate = "-"

            # learnings 贡献
            my_learnings = conn.execute(
                "SELECT COUNT(*) as cnt FROM learnings WHERE created_by = ?",
                (name,),
            ).fetchone()["cnt"]

            total_learnings = conn.execute(
                "SELECT COUNT(*) as cnt FROM learnings",
            ).fetchone()["cnt"]

            pct = f"{my_learnings * 100 // total_learnings}%" if total_learnings else "-"

            # 最近一周日报叙事摘要
            reports = conn.execute(
                """SELECT report_date, narrative FROM daily_reports
                   WHERE agent_id = ? AND report_date >= ?
                   ORDER BY report_date DESC LIMIT 7""",
                (name, week_ago),
            ).fetchall()

    except Exception as e:
        print(f"查询失败：{e}")
        return

    print(c("1;36", f"{display_name}（{role}）"))
    print()
    print(f"本周: 会话 {sessions} · 消息 {messages:,} · 工具 {tool_calls:,} ({tool_rate})")
    print(f"Learnings: {my_learnings} 条（贡献 {pct}）")

    if reports:
        print("最近产出:")
        for r in reports[:3]:
            narrative = r["narrative"][:60].replace("\n", " ")
            print(f"  {r['report_date']}: {narrative}...")
