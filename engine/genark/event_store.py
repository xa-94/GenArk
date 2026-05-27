"""Event Store — 不可变追加写入 + 哈希链"""

import hashlib
import json
from datetime import datetime
from contextlib import contextmanager

from .db import get_conn, _open_conn


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _next_event_id(agent_id: str, conn) -> str:
    today = datetime.now().strftime("%Y%m%d")
    cur = conn.execute(
        "SELECT id FROM events WHERE agent_id = ? AND id LIKE ? ORDER BY id DESC LIMIT 1",
        (agent_id, f"evt_{today}_%"),
    )
    row = cur.fetchone()
    if row:
        last_seq = int(row["id"].rsplit("_", 1)[-1])
        seq = last_seq + 1
    else:
        seq = 1
    return f"evt_{today}_{seq:06d}"


def append_event(
    agent_id: str,
    event_type: str,
    payload: dict,
    timestamp: str | None = None,
    source_path: str | None = None,
    conn=None,
) -> str:
    """追加一条事件，返回 event_id。如提供 conn 则使用外部事务，否则自管理。"""
    own_conn = conn is None
    if own_conn:
        conn = _open_conn()

    try:
        ts = timestamp or datetime.now().isoformat()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        content_hash = _hash(payload_json)
        event_id = _next_event_id(agent_id, conn)

        prev_hash = None
        row = conn.execute(
            "SELECT content_hash FROM events WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        if row:
            prev_hash = row["content_hash"]

        conn.execute(
            """INSERT INTO events (id, timestamp, agent_id, event_type, source_path,
               content_hash, prev_hash, payload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, ts, agent_id, event_type, source_path, content_hash, prev_hash, payload_json),
        )

        if own_conn:
            conn.commit()

        return event_id
    finally:
        if own_conn:
            conn.close()


def verify_chain(agent_id: str) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, content_hash, prev_hash, payload FROM events WHERE agent_id = ? ORDER BY id",
            (agent_id,),
        ).fetchall()

        errors = []
        prev_hash = None
        for r in rows:
            payload_json = json.dumps(json.loads(r["payload"]), ensure_ascii=False, sort_keys=True)
            expected_hash = _hash(payload_json)
            if expected_hash != r["content_hash"]:
                errors.append(f"{r['id']}: hash mismatch")
            if r["prev_hash"] != prev_hash:
                errors.append(f"{r['id']}: chain break (expected={prev_hash}, got={r['prev_hash']})")
            prev_hash = r["content_hash"]

        return {
            "agent_id": agent_id,
            "total_events": len(rows),
            "valid": len(errors) == 0,
            "errors": errors,
        }
