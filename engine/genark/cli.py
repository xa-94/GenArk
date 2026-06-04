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

from .db import init_db, get_conn, rebuild_state_store
from .collector import collect, check_storage
from .memory_watcher import watch_memories, watch_skills
from .event_store import verify_chain
from .reporter import generate_report, save_report
from .pusher import push_report, push_text
from .composer import compose_daily
from .relations import compute_relations, format_relations
from .cross_verify import verify_cross_mentions
from .major_events import detect_major_events, build_major_event_message
from .config import AGENT_INSTANCES


def cmd_init(_args):
    init_db()
    print("✅ 数据库已初始化")


def cmd_collect(args):
    # A3: 存储空间检查
    storage = check_storage(args.agent)
    if not storage["ok"]:
        msg = f"⚠️ {args.agent} 存储空间不足：剩余 {storage['free_mb']}MB < 阈值 {storage['threshold_mb']}MB，暂停采集"
        print(msg)
        push_text(msg)
        return

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

    # A3: 存储空间检查
    storage = check_storage(agent_id)
    if not storage["ok"]:
        msg = f"⚠️ {agent_id} 存储空间不足：剩余 {storage['free_mb']}MB < 阈值 {storage['threshold_mb']}MB，暂停日报生成"
        print(msg)
        push_text(msg)
        return

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


def cmd_rebuild_state(_args):
    rebuild_state_store()
    print("✅ State Store 已重建（events 表保留），请重新运行 collect 恢复状态")


def cmd_check_storage(args):
    storage = check_storage(args.agent)
    status = "✅" if storage["ok"] else "⚠️"
    print(f"{status} 存储空间：{storage['free_mb']}MB 可用（阈值 {storage['threshold_mb']}MB）")
    if not storage["ok"]:
        push_text(f"存储空间告警：{storage['free_mb']}MB < {storage['threshold_mb']}MB")


def cmd_daily_all(args):
    """拼版日报：生成 + 推送 + 重大事件"""
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    agents = args.agents.split(",") if args.agents else None
    do_push = not args.no_push

    # A3: 存储空间检查
    storage = check_storage()
    if not storage["ok"]:
        msg = f"⚠️ 存储空间不足：剩余 {storage['free_mb']}MB < 阈值 {storage['threshold_mb']}MB"
        print(msg)
        push_text(msg)
        return

    composed = compose_daily(agents=agents, date=date, push=do_push)
    print(f"✅ 拼版日报已{'推送' if do_push else '生成'}（{date}，{len(composed['agents'])} 人，{composed['intersections']} 条交汇）")
    print()
    print(composed["narrative"])

    # ── 重大事件检测 ──
    if not agents:
        agents = ["guyuan", "heming"]

    all_major = {}
    from .reporter import generate_report as _gen_report
    for agent_id in agents:
        # 获取 stats（已由 compose_daily 生成过，直接从 DB 读）
        with get_conn() as conn:
            row = conn.execute(
                "SELECT stats_json FROM daily_reports WHERE agent_id = ? AND report_date = ? ORDER BY created_at DESC LIMIT 1",
                (agent_id, date),
            ).fetchone()
        if not row:
            continue
        import json as _json
        stats = _json.loads(row["stats_json"])
        events = detect_major_events(agent_id, stats)
        if events:
            all_major[agent_id] = events

    if all_major:
        msg = build_major_event_message(all_major)
        if msg:
            print(f"\n⚡ 重大事件：")
            print(msg)
            if do_push:
                push_text(msg)


def cmd_relations(args):
    """关系网络查看"""
    agents = args.agents.split(",") if args.agents else None
    rel = compute_relations(agents=agents, weeks=args.weeks)
    print(format_relations(rel))
    import json
    print(f"\n📋 详细数据：{json.dumps(rel, indent=2, ensure_ascii=False)}")


def cmd_verify_cross(_args):
    """交叉验证 @ 消息一致性"""
    result = verify_cross_mentions(
        agents=["guyuan", "heming"],
        days=7,
    )
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n{'✅' if result['verdict'] == '可行' else '⚠️'} 结论：{result['verdict']}")


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

    sub.add_parser("rebuild-state", help="数据库损坏一键重建（保留 events 表）")

    p = sub.add_parser("check-storage", help="检查存储空间")
    p.add_argument("--agent", default="guyuan", choices=list(AGENT_INSTANCES.keys()))

    p = sub.add_parser("daily-all", help="拼版日报（生成 + 推送 + 重大事件）")
    p.add_argument("--date", help="日期 YYYY-MM-DD（默认今天）")
    p.add_argument("--agents", help="智能体列表，逗号分隔（默认 guyuan,heming）")
    p.add_argument("--no-push", action="store_true", help="仅生成不推送（调试用）")

    p = sub.add_parser("relations", help="关系网络统计")
    p.add_argument("--agents", help="智能体列表，逗号分隔")
    p.add_argument("--weeks", type=int, default=4, help="统计周数（默认 4）")

    sub.add_parser("verify-cross-mentions", help="交叉验证 @ 消息一致性")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "collect": cmd_collect,
        "daily": cmd_daily,
        "verify-chain": cmd_verify,
        "status": cmd_status,
        "rebuild-state": cmd_rebuild_state,
        "check-storage": cmd_check_storage,
        "daily-all": cmd_daily_all,
        "relations": cmd_relations,
        "verify-cross-mentions": cmd_verify_cross,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
