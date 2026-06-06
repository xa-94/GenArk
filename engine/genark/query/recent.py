"""query recent [--days N] — 最近团队动态"""

import json
from datetime import datetime, timedelta

from ..db import get_conn

AGENT_DISPLAY = {
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
    "xiangai": "祥霭分身",
}


def cmd_query_recent(args):
    days = args.days
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    try:
        with get_conn() as conn:
            print(c("1;36", f"最近 {days} 天团队动态:"))
            print()

            for date in dates:
                next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

                reports = conn.execute(
                    """SELECT agent_id, stats_json FROM daily_reports
                       WHERE report_date = ? ORDER BY agent_id""",
                    (date,),
                ).fetchall()

                learn_count = conn.execute(
                    """SELECT COUNT(*) as cnt FROM learnings
                       WHERE created_at >= ? AND created_at < ?""",
                    (date, next_date),
                ).fetchone()["cnt"]

                if not reports and not learn_count:
                    print(f"{date}: 无数据")
                    continue

                parts = []
                for r in reports:
                    name = AGENT_DISPLAY.get(r["agent_id"], r["agent_id"])
                    try:
                        stats = json.loads(r["stats_json"])
                        s = stats.get("sessions", 0)
                        m = stats.get("messages_sent", 0)
                        parts.append(f"{name} {s}会话({m}msg)")
                    except (json.JSONDecodeError, KeyError):
                        parts.append(f"{name} (数据异常)")

                line = f"{date}: {' · '.join(parts)}" if parts else f"{date}:"
                if learn_count:
                    line += f"\n  新增 {learn_count} learnings"
                print(line)

    except Exception as e:
        print(f"查询失败：{e}")
