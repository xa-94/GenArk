"""query learnings <关键词> — 搜索 learnings（FTS5 全文搜索 + LIKE 降级）"""

from ..db import get_conn


def cmd_query_learnings(args):
    keyword = args.keyword
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    try:
        with get_conn() as conn:
            # 尝试 FTS5 搜索
            rows = _search_fts(conn, keyword)
            if rows is None:
                # FTS5 表不存在，降级到 LIKE
                rows = conn.execute(
                    """SELECT id, category, content FROM learnings
                       WHERE status = 'approved' AND content LIKE ?
                       ORDER BY id DESC LIMIT 20""",
                    (f"%{keyword}%",),
                ).fetchall()
    except Exception as e:
        print(f"查询失败：{e}")
        return

    if not rows:
        print("无匹配的 learnings")
        return

    print(c("1;36", f"找到 {len(rows)} 条相关 learnings:"))
    print()
    for r in rows:
        title = r["content"][:60].replace("\n", " ")
        print(f"  #{r['id']} [{r['category']}] {title}...")


def _search_fts(conn, keyword: str) -> list | None:
    """用 FTS5 搜索 learnings，纯中文关键词自动补 LIKE。

    如果 learnings_fts 表不存在，返回 None 表示降级。
    FTS5 的默认 tokenizer 对英文和技术词效果好，
    对纯中文连续字符可能匹配不全，此时用 LIKE 补充。
    """
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learnings_fts'"
        ).fetchone()
        if not exists:
            return None

        fts_rows = conn.execute(
            """SELECT l.id, l.category, l.content
               FROM learnings l
               JOIN learnings_fts fts ON l.id = fts.rowid
               WHERE learnings_fts MATCH ? AND l.status = 'approved'
               ORDER BY rank LIMIT 20""",
            (keyword,),
        ).fetchall()

        # 纯中文关键词：FTS5 默认 tokenizer 可能匹配不全，用 LIKE 补充
        if _is_pure_cjk(keyword):
            like_rows = conn.execute(
                """SELECT id, category, content FROM learnings
                   WHERE status = 'approved' AND content LIKE ?
                   ORDER BY id DESC""",
                (f"%{keyword}%",),
            ).fetchall()
            # 合并去重（按 id），FTS5 结果排前面
            seen = set()
            merged = []
            for r in fts_rows:
                if r["id"] not in seen:
                    merged.append(dict(r))
                    seen.add(r["id"])
            for r in like_rows:
                if r["id"] not in seen:
                    merged.append(dict(r))
                    seen.add(r["id"])
                if len(merged) >= 20:
                    break
            return merged

        return fts_rows
    except Exception:
        return None


def _is_pure_cjk(s: str) -> bool:
    """判断是否为纯中文（无 ASCII 字母）关键词。"""
    return not any(c.isascii() and c.isalpha() for c in s)
