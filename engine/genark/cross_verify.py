"""交叉验证：对比两个智能体 JSONL 中同时间段 @ 消息的一致性。

Phase 2 接入赫明后第一件事。判定协作检测数据源是否可靠。
"""

import json
import hashlib
from datetime import datetime, timedelta

from .db import get_conn


def verify_cross_mentions(
    agents: list[str],
    days: int = 7,
    threshold: float = 0.8,
) -> dict:
    """对比两个智能体的 @ 消息一致性。

    返回：
    {
      "match_rate": 0.94,
      "total_guyuan": 48,
      "total_heming": 45,
      "matched": 44,
      "only_in_guyuan": 4,
      "only_in_heming": 1,
      "verdict": "可行",  # ≥80% → 可行
      "sample_mismatches": [...]  # 前 5 条不匹配样本
    }
    """
    agent_a, agent_b = agents[0], agents[1]
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    with get_conn() as conn:
        # 取两个 agent 的 @ 消息，按 content 哈希匹配
        rows_a = conn.execute(
            """SELECT id, timestamp, json_extract(payload, '$.content') as content
               FROM events
               WHERE agent_id = ? AND event_type = 'session_message'
               AND json_extract(payload, '$.role') = 'user'
               AND json_extract(payload, '$.content') LIKE '%@%'
               AND date(timestamp) >= ?""",
            (agent_a, since),
        ).fetchall()

        rows_b = conn.execute(
            """SELECT id, timestamp, json_extract(payload, '$.content') as content
               FROM events
               WHERE agent_id = ? AND event_type = 'session_message'
               AND json_extract(payload, '$.role') = 'user'
               AND json_extract(payload, '$.content') LIKE '%@%'
               AND date(timestamp) >= ?""",
            (agent_b, since),
        ).fetchall()

    # 按 content 哈希去重后匹配
    def hash_content(c: str) -> str:
        # 取前 200 字符哈希（同一条群聊消息可能因为截断不同而不同）
        return hashlib.md5(c[:200].encode()).hexdigest()[:12]

    hashes_a = {hash_content(r["content"]): r for r in rows_a}
    hashes_b = {hash_content(r["content"]): r for r in rows_b}

    matched = 0
    only_in_a = []
    only_in_b = []

    for h, r in hashes_a.items():
        if h in hashes_b:
            matched += 1
        else:
            only_in_a.append(r)

    for h, r in hashes_b.items():
        if h not in hashes_a:
            only_in_b.append(r)

    total_a = len(hashes_a)
    total_b = len(hashes_b)
    match_rate = matched / max(total_a, 1)

    return {
        "agents": agents,
        "days": days,
        "match_rate": round(match_rate, 3),
        f"total_{agent_a}": total_a,
        f"total_{agent_b}": total_b,
        "matched": matched,
        f"only_in_{agent_a}": len(only_in_a),
        f"only_in_{agent_b}": len(only_in_b),
        "verdict": "可行" if match_rate >= threshold else "不可靠（数据源不一致）",
        "sample_mismatches": [
            {"agent": agent_a, "content": r["content"][:150]}
            for r in only_in_a[:3]
        ] + [
            {"agent": agent_b, "content": r["content"][:150]}
            for r in only_in_b[:3]
        ],
    }
