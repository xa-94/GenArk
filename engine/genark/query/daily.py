"""query daily [--date YYYY-MM-DD] — 查看日报"""

import json
from datetime import datetime

from ..db import get_conn

AGENT_DISPLAY = {
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
    "xiangai": "祥霭分身",
}


def cmd_query_daily(args):
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    try:
        with get_conn() as conn:
            reports = conn.execute(
                """SELECT agent_id, stats_json, narrative FROM daily_reports
                   WHERE report_date = ? ORDER BY agent_id""",
                (date,),
            ).fetchall()

            # 当日 learnings 新增数
            learn_new = conn.execute(
                """SELECT COUNT(*) as cnt FROM learnings
                   WHERE created_at >= ? AND created_at < ?""",
                (date, _next_day(date)),
            ).fetchone()["cnt"]

            learn_pending = conn.execute(
                """SELECT COUNT(*) as cnt FROM learnings
                   WHERE status = 'pending'
                   AND created_at >= ? AND created_at < ?""",
                (date, _next_day(date)),
            ).fetchone()["cnt"]

    except Exception as e:
        print(f"查询失败：{e}")
        return

    if not reports:
        print(f"{date} 无日报记录")
        return

    print(c("1;36", f"GenArk 日报 · {date}"))
    print()

    for r in reports:
        name = AGENT_DISPLAY.get(r["agent_id"], r["agent_id"])
        try:
            stats = json.loads(r["stats_json"])
            sessions = stats.get("sessions", 0)
            messages = stats.get("messages_sent", 0)
            tools = stats.get("tool_calls", 0)
            rate = stats.get("tool_success_rate", 0)
            line = f"  {name}: 会话 {sessions} · 消息 {messages}"
            if tools:
                line += f" · 工具 {tools} ({rate:.0%})"
            print(line)
        except (json.JSONDecodeError, KeyError):
            print(f"  {name}: 数据解析异常")

    print()
    print(f"  知识沉淀: 新增 {learn_new} · 待审核 {learn_pending}")


def _next_day(date_str):
    """返回 date_str 的下一天 YYYY-MM-DD"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    from datetime import timedelta
    return (d + timedelta(days=1)).strftime("%Y-%m-%d")
