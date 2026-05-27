"""Memory / Skills 变化监听器"""

import hashlib
import json
import os

from .config import agent_memories_dir, agent_skills_dir
from .db import get_conn, _open_conn
from .event_store import append_event


def _file_hash(filepath: str) -> str:
    if not os.path.exists(filepath):
        return ""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def watch_memories(agent_id: str, conn=None) -> list[str]:
    """检测 MEMORY.md / USER.md 变化"""
    own_conn = conn is None
    if own_conn:
        conn = _open_conn()

    try:
        memories_dir = agent_memories_dir(agent_id)
        changed = []
        for filename in ["MEMORY.md", "USER.md"]:
            filepath = os.path.join(memories_dir, filename)
            new_hash = _file_hash(filepath)

            cur = conn.execute(
                "SELECT content_hash FROM file_snapshots WHERE agent_id = ? AND file_path = ?",
                (agent_id, f"memories/{filename}"),
            )
            row = cur.fetchone()
            old_hash = row["content_hash"] if row else None

            if not new_hash:
                continue
            if new_hash == old_hash:
                continue

            with open(filepath, "r") as f:
                content = f.read()

            entries = [e.strip() for e in content.split("§") if e.strip()]
            snapshot = {
                "file": filename,
                "entry_count": len(entries),
                "total_chars": len(content),
                "first_entry": entries[0][:100] if entries else "",
                "last_entry": entries[-1][:100] if entries else "",
            }

            append_event(
                agent_id=agent_id,
                event_type="memory_change",
                payload=snapshot,
                source_path=filepath,
                conn=conn,
            )

            conn.execute(
                """INSERT OR REPLACE INTO file_snapshots (agent_id, file_path, content_hash, captured_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (agent_id, f"memories/{filename}", new_hash),
            )
            changed.append(filename)

        if own_conn:
            conn.commit()
        return changed
    finally:
        if own_conn:
            conn.close()


def watch_skills(agent_id: str, conn=None) -> dict:
    """检测 skills/.usage.json 变化"""
    own_conn = conn is None
    if own_conn:
        conn = _open_conn()

    try:
        skills_dir = agent_skills_dir(agent_id)
        usage_file = os.path.join(skills_dir, ".usage.json")
        new_hash = _file_hash(usage_file)

        if not new_hash:
            return {"changed": False, "new_count": 0}

        cur = conn.execute(
            "SELECT content_hash FROM file_snapshots WHERE agent_id = ? AND file_path = ?",
            (agent_id, "skills/.usage.json"),
        )
        row = cur.fetchone()
        if row and row["content_hash"] == new_hash:
            return {"changed": False, "new_count": 0}

        with open(usage_file, "r") as f:
            usage = json.load(f)

        snapshot = {
            "total_skills": len(usage),
            "skills": {
                name: {
                    "use_count": info.get("use_count", 0),
                    "state": info.get("state", "active"),
                }
                for name, info in usage.items()
            },
        }

        append_event(
            agent_id=agent_id,
            event_type="skill_change",
            payload=snapshot,
            source_path=usage_file,
            conn=conn,
        )

        conn.execute(
            """INSERT OR REPLACE INTO file_snapshots (agent_id, file_path, content_hash, captured_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (agent_id, "skills/.usage.json", new_hash),
        )

        if own_conn:
            conn.commit()
        return {"changed": True, "new_count": len(usage)}
    finally:
        if own_conn:
            conn.close()
