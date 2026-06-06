"""GenArk Phase 4 — 自动 learnings 提取器

从当天 Agent 会话事件中识别值得记录的教训，去重后入库。
"""
import json
import httpx
from .db import get_conn
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

# 提取阈值
MIN_EVENTS = 50          # 当天事件 < 此值则跳过
MIN_CONTENT_LEN = 30     # content 最短字数
MIN_CONFIDENCE = 0.7     # 最低置信度
JACCARD_THRESHOLD = 0.7  # 去重相似度阈值
MAX_LEARNINGS = 10       # 单次最多提取数
EVENTS_PER_AGENT = 30    # 每个 Agent 最多参与提取的事件数
PAYLOAD_PREVIEW = 300    # payload 截取长度

SYSTEM_PROMPT = """\
你是 GenArk 的知识提取器。从以下 Agent 会话事件中识别值得记录的教训（learnings）。

输出 JSON 数组（不是 markdown 代码块！直接输出 JSON），每条包含：
- source_type: "bug_fix" / "correction" / "pattern"
- content: 一句话描述（50-200字，必须有具体路径/命令/角色名/错误信息等硬信号）
- category: 分类（python/devops/genark/teamwork/hermes/...）
- confidence: 0.0-1.0（你对此条质量的自信度）

规则：
- 只提取具体可执行的教训，不提取泛泛而谈
- 有错误码/路径/命令/工具名 → 优先提取
- 同一问题的多次出现 → 只提取最清晰的一条
- 最多 10 条
- 没有值得提取的内容 → 返回 []
"""


def extract_learnings(date_str: str) -> dict:
    """从 events 表读当天事件，调 LLM 提取，去重，入库。

    Returns:
        {"extracted": int, "filtered": int, "total_events": int}
    """
    # 1. 读当天事件
    events = _fetch_events(date_str)
    total = len(events)
    if total < MIN_EVENTS:
        print(f"[extract] 当天事件仅 {total} 条（<{MIN_EVENTS}），跳过")
        return {"extracted": 0, "filtered": 0, "total_events": total}

    # 2. 压缩为 LLM 文本
    summary = _build_events_summary(events)

    # 3. 调 LLM
    raw = _call_deepseek(summary)
    if raw is None:
        return {"extracted": 0, "filtered": 0, "total_events": total}

    candidates = _parse_llm_response(raw)

    # 4. 过滤 + 去重 + 入库
    filtered = 0
    extracted = 0
    for item in candidates:
        content = item.get("content", "")
        confidence = item.get("confidence", 0)

        # 长度过滤
        if len(content) < MIN_CONTENT_LEN:
            filtered += 1
            continue

        # 置信度过滤
        if confidence < MIN_CONFIDENCE:
            filtered += 1
            continue

        # 去重
        if _is_duplicate(content):
            filtered += 1
            continue

        # 入库
        _insert_learning(item)
        extracted += 1

    return {"extracted": extracted, "filtered": filtered, "total_events": total}


# ── 内部函数 ──────────────────────────────────────────────


def _fetch_events(date_str: str) -> list[dict]:
    """读取当天 session_message 类型事件。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, timestamp, agent_id, event_type, payload
               FROM events
               WHERE event_type = 'session_message' AND date(timestamp) = ?
               ORDER BY timestamp""",
            (date_str,),
        ).fetchall()
    return [dict(r) for r in rows]


def _build_events_summary(events: list[dict]) -> str:
    """将事件列表压缩为适合 LLM 的文本。

    按 agent_id 分组，每人最多 EVENTS_PER_AGENT 条事件。
    """
    # 分组
    by_agent: dict[str, list[dict]] = {}
    for ev in events:
        by_agent.setdefault(ev["agent_id"], []).append(ev)

    lines: list[str] = []
    for agent_id, agent_events in sorted(by_agent.items()):
        lines.append(f"\n## Agent: {agent_id}")
        for ev in agent_events[:EVENTS_PER_AGENT]:
            payload_preview = (ev.get("payload", "") or "")[:PAYLOAD_PREVIEW]
            lines.append(
                f"- [{ev['timestamp']}] type={ev['event_type']} payload={payload_preview}"
            )
        if len(agent_events) > EVENTS_PER_AGENT:
            lines.append(f"- ... 还有 {len(agent_events) - EVENTS_PER_AGENT} 条事件")

    return "\n".join(lines)


def _call_deepseek(events_text: str) -> str | None:
    """调用 DeepSeek API 提取 learnings。"""
    if not DEEPSEEK_API_KEY:
        print("[extract] GENARK_DEEPSEEK_API_KEY 未配置，跳过")
        return None

    prompt = f"""以下是 {events_text.count("## Agent:")} 个 Agent 的当天会话事件：

{events_text}

请提取值得记录的教训。"""

    try:
        resp = httpx.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        return body["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[extract] DeepSeek API 调用失败: {e}")
        return None


def _parse_llm_response(raw: str) -> list[dict]:
    """解析 LLM 返回的 JSON 数组。"""
    text = raw.strip()

    # 尝试去除 markdown 代码块围栏
    if text.startswith("```"):
        # 去掉 ```json 或 ``` 开头和 ``` 结尾
        first_nl = text.index("\n")
        last_backtick = text.rfind("```")
        if last_backtick > first_nl:
            text = text[first_nl:last_backtick].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # 降级：尝试从文本中找 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    print(f"[extract] 无法解析 LLM 返回: {raw[:200]}")
    return []


def _jaccard_similarity(a: str, b: str) -> float:
    """计算两个文本的 Jaccard 相似度。

    分词：按非字母数字字符分割，取长度 >= 2 的词。
    """
    import re

    def tokenize(s: str) -> set[str]:
        tokens = re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", s.lower())
        return {t for t in tokens if len(t) >= 2}

    set_a = tokenize(a)
    set_b = tokenize(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _is_duplicate(content: str) -> bool:
    """检查是否与已有 approved learnings 重复。

    优先用 FTS5 找候选 + Jaccard 精排，FTS5 不存在时降级全表扫描。
    """
    with get_conn() as conn:
        # 尝试 FTS5 候选
        candidates = _fts5_candidates(conn, content)
        if candidates is not None:
            for r in candidates:
                if _jaccard_similarity(content, r["content"]) > JACCARD_THRESHOLD:
                    return True
            return False

        # 降级：全表 Jaccard 扫描
        rows = conn.execute(
            "SELECT content FROM learnings WHERE status = 'approved'"
        ).fetchall()
        for r in rows:
            if _jaccard_similarity(content, r["content"]) > JACCARD_THRESHOLD:
                return True
        return False


def _fts5_candidates(conn, content: str) -> list | None:
    """用 FTS5 搜索与 content 相似的候选 learnings。

    返回最多 20 条候选，如果 FTS5 表不存在则返回 None。
    """
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learnings_fts'"
        ).fetchone()
        if not exists:
            return None

        # FTS5 MATCH 搜索，按 BM25 排序取前 20 条
        rows = conn.execute(
            """SELECT l.content
               FROM learnings l
               JOIN learnings_fts fts ON l.id = fts.rowid
               WHERE learnings_fts MATCH ? AND l.status = 'approved'
               ORDER BY rank LIMIT 20""",
            (content,),
        ).fetchall()
        return rows
    except Exception:
        return None


def _insert_learning(item: dict) -> None:
    """写入 learnings 表，status='pending'。"""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO learnings (source_type, content, category, confidence, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (
                item.get("source_type", "pattern"),
                item["content"],
                item.get("category", ""),
                item.get("confidence", 0.5),
                "system",
            ),
        )
