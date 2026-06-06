"""query agent <name> — Agent 状态摘要"""

import json
from datetime import datetime

from ..db import get_conn

AGENT_ROLES = {
    "guyuan": "产品经理",
    "heming": "Tech Lead",
    "shoushan": "主智能体",
}

AGENT_DISPLAY = {
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
}


def cmd_query_agent(args):
    name = args.name
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    display_name = AGENT_DISPLAY.get(name, name)
    role = AGENT_ROLES.get(name, "未知角色")

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        with get_conn() as conn:
            # 今日事件统计
            row = conn.execute(
                """SELECT
                    COUNT(DISTINCT source_path) as sessions,
                    SUM(CASE WHEN event_type = 'session_message' THEN 1 ELSE 0 END) as messages,
                    SUM(CASE WHEN event_type = 'session_message'
                         AND json_extract(payload, '$.role') = 'tool' THEN 1 ELSE 0 END) as tool_calls
                FROM events
                WHERE agent_id = ? AND timestamp >= ?""",
                (name, today),
            ).fetchone()

            sessions = row["sessions"] or 0
            messages = row["messages"] or 0
            tool_calls = row["tool_calls"] or 0

            # learnings 统计
            learn_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM learnings WHERE created_by = ?",
                (name,),
            ).fetchone()
            learn_count = learn_row["cnt"]

            # 最近 5 条 learnings
            recent_learnings = conn.execute(
                """SELECT id, category, content FROM learnings
                   WHERE created_by = ? ORDER BY id DESC LIMIT 5""",
                (name,),
            ).fetchall()

            # 最新日报 stats
            report = conn.execute(
                """SELECT stats_json FROM daily_reports
                   WHERE agent_id = ? ORDER BY created_at DESC LIMIT 1""",
                (name,),
            ).fetchone()

            # 采集进度
            cursor = conn.execute(
                "SELECT updated_at FROM collector_cursor WHERE agent_id = ?",
                (name,),
            ).fetchone()

    except Exception as e:
        print(f"查询失败：{e}")
        return

    # 输出
    print(c("1;36", f"{display_name}（{role}）"))

    print(f"  今日: {sessions} 次会话 · {messages} 条消息 · {tool_calls} 次工具调用")

    if report:
        try:
            stats = json.loads(report["stats_json"])
            print(f"  日报最新: {stats.get('sessions', 0)} 会话 · "
                  f"{stats.get('messages_sent', 0)} 消息 · "
                  f"成功率 {stats.get('tool_success_rate', 0):.0%}")
        except (json.JSONDecodeError, KeyError):
            pass

    print(f"  Learnings: {learn_count} 条")

    if recent_learnings:
        print("  最近 learnings:")
        for l in recent_learnings:
            title = l["content"][:50].replace("\n", " ")
            print(f"    #{l['id']} [{l['category']}] {title}...")

    if cursor:
        updated = cursor["updated_at"] or ""
        time_part = updated[11:16] if len(updated) > 16 else updated
        print(f"  采集进度: 最后采集 {time_part}")
