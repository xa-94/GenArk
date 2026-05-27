"""GenArk CLI"""

import argparse
import os
from datetime import datetime


def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()

from .db import init_db, get_conn
from .collector import collect
from .memory_watcher import watch_memories, watch_skills
from .event_store import verify_chain
from .reporter import generate_report, save_report
from .pusher import push_report
from .config import AGENT_INSTANCES


def cmd_init(_args):
    init_db()
    print("✅ 数据库已初始化")


def cmd_collect(args):
    result = collect(args.agent)
    print(f"✅ 采集完成：{result['new_events']} 条新事件，扫描 {result['files_scanned']} 个文件")

    mem = watch_memories(args.agent)
    if mem:
        print(f"📝 记忆变化：{', '.join(mem)}")

    skills = watch_skills(args.agent)
    if skills["changed"]:
        print(f"🔧 技能面板已更新：{skills['new_count']} 项")


def cmd_daily(args):
    agent_id = args.agent
    date = args.date or datetime.now().strftime("%Y-%m-%d")

    print("📡 采集数据...")
    result = collect(agent_id)
    print(f"   新增 {result['new_events']} 条事件")

    watch_memories(agent_id)
    watch_skills(agent_id)

    print("🧠 生成日报...")
    report = generate_report(agent_id, date)
    save_report(report)

    print("📤 推送日报...")
    ok = push_report(report)
    if ok:
        print(f"✅ 日报已推送到钉钉（{report['date']}）")
    else:
        print("❌ 推送失败，日报已保存到数据库")

    stats = report["stats"]
    print(f"\n📊 今日数据：会话 {stats['sessions']} | 消息 {stats['messages_sent']} | 工具 {stats['tool_calls']}")
    if report["llm_model"]:
        print(f"🤖 模型：{report['llm_model']} · tokens：{report['llm_tokens']}")


def cmd_verify(args):
    result = verify_chain(args.agent)
    if result["valid"]:
        print(f"✅ {result['agent_id']} 哈希链完整（{result['total_events']} 条事件）")
    else:
        print(f"❌ 哈希链异常：")
        for err in result["errors"]:
            print(f"   {err}")


def cmd_status(args):
    with get_conn() as conn:
        events = conn.execute(
            "SELECT COUNT(*) as c FROM events WHERE agent_id = ?", (args.agent,)
        ).fetchone()["c"]
        cursor = conn.execute(
            "SELECT * FROM collector_cursor WHERE agent_id = ?", (args.agent,)
        ).fetchone()
        reports = conn.execute(
            "SELECT COUNT(*) as c FROM daily_reports WHERE agent_id = ?", (args.agent,)
        ).fetchone()["c"]

        print(f"智能体：{args.agent}")
        print(f"事件总数：{events}")
        print(f"日报数量：{reports}")
        if cursor:
            print(f"采集进度：{cursor['source_path']} @ {cursor['byte_offset']} bytes")
        else:
            print("采集进度：尚未开始")


def main():
    parser = argparse.ArgumentParser(description="GenArk — 智能体生命平台")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="初始化数据库")

    p = sub.add_parser("collect", help="增量采集")
    p.add_argument("--agent", required=True, choices=list(AGENT_INSTANCES.keys()))

    p = sub.add_parser("daily", help="采集 + 日报生成 + 推送")
    p.add_argument("--agent", required=True, choices=list(AGENT_INSTANCES.keys()))
    p.add_argument("--date", help="日期 YYYY-MM-DD（默认今天）")

    p = sub.add_parser("verify-chain", help="验证哈希链")
    p.add_argument("--agent", required=True, choices=list(AGENT_INSTANCES.keys()))

    p = sub.add_parser("status", help="查看状态")
    p.add_argument("--agent", required=True, choices=list(AGENT_INSTANCES.keys()))

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "collect": cmd_collect,
        "daily": cmd_daily,
        "verify-chain": cmd_verify,
        "status": cmd_status,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
