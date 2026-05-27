"""JSONL 增量采集器"""

import json
import os
import glob
from datetime import datetime

from .config import agent_sessions_dir, COLLECT_FILE_GLOB
from .db import get_conn, _open_conn
from .event_store import append_event


def collect(agent_id: str, conn=None) -> dict:
    """增量采集 JSONL 会话文件"""
    own_conn = conn is None
    if own_conn:
        conn = _open_conn()

    try:
        sessions_dir = agent_sessions_dir(agent_id)
        pattern = os.path.join(sessions_dir, COLLECT_FILE_GLOB)
        files = sorted(glob.glob(pattern), key=os.path.getmtime)

        cur = conn.execute(
            "SELECT source_path, byte_offset FROM collector_cursor WHERE agent_id = ?",
            (agent_id,),
        )
        cursor_row = cur.fetchone()
        current_file = cursor_row["source_path"] if cursor_row else None
        byte_offset = cursor_row["byte_offset"] if cursor_row else 0

        new_events = 0
        files_scanned = 0
        found_current = (current_file is None)

        for filepath in files:
            if not found_current:
                if filepath == current_file:
                    found_current = True
                else:
                    continue

            files_scanned += 1
            file_size = os.path.getsize(filepath)
            if filepath == current_file and byte_offset >= file_size:
                continue

            with open(filepath, "r") as f:
                if filepath == current_file:
                    f.seek(byte_offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    role = msg.get("role", "")
                    if role == "session_meta":
                        continue

                    ts = msg.get("timestamp") or datetime.now().isoformat()
                    tool_name = msg.get("name") if role == "tool" else None

                    payload = {
                        "role": role,
                        "content": str(msg.get("content", ""))[:2000],
                        "tool_name": tool_name,
                        "raw_timestamp": ts,
                        "source_file": os.path.basename(filepath),
                    }
                    append_event(
                        agent_id=agent_id,
                        event_type="session_message",
                        payload=payload,
                        timestamp=ts,
                        source_path=filepath,
                        conn=conn,
                    )
                    new_events += 1

                byte_offset = f.tell()

            file_mtime = os.path.getmtime(filepath)
            conn.execute(
                """INSERT OR REPLACE INTO collector_cursor (agent_id, source_path, byte_offset, file_mtime, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (agent_id, filepath, byte_offset, file_mtime),
            )

        if own_conn:
            conn.commit()

        return {"new_events": new_events, "files_scanned": files_scanned}
    finally:
        if own_conn:
            conn.close()
