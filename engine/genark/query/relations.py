"""genark query relations — 查询 learning 因果关系链"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "genark.db"


def cmd_query_relations(args):
    """查询 learning 因果关系链"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    learning_id = args.id
    depth = getattr(args, 'depth', 2)

    if learning_id:
        # 展开指定 learning 的因果链
        chain = _trace_relations(c, learning_id, depth)
        _print_chain(chain)
    else:
        # 概览
        _print_overview(c)

    conn.close()


def _trace_relations(c, learning_id: int, max_depth: int) -> list:
    """追溯因果关系链（双向 BFS）"""
    visited = set()
    chain = []

    # 获取目标 learning
    c.execute("SELECT id, substr(content, 1, 120) as summary, source_type, created_by FROM learnings WHERE id=?", (learning_id,))
    target = c.fetchone()
    if not target:
        print(f"❌ Learning #{learning_id} 不存在")
        return []

    chain.append({
        'id': target['id'],
        'summary': target['summary'],
        'type': target['source_type'],
        'creator': target['created_by'],
        'depth': 0,
        'relations': [],
    })
    visited.add(learning_id)

    # BFS 最多 max_depth 层
    frontier = [(learning_id, 0)]
    while frontier:
        cur_id, cur_depth = frontier.pop(0)
        if cur_depth >= max_depth:
            continue

        c.execute("""
            SELECT lr.relation_type, lr.source_id, lr.target_id,
                   l.id, substr(l.content, 1, 100) as summary, l.source_type, l.created_by
            FROM learning_relations lr
            JOIN learnings l ON (CASE WHEN lr.source_id = ? THEN lr.target_id ELSE lr.source_id END) = l.id
            WHERE (lr.source_id = ? OR lr.target_id = ?)
        """, (cur_id, cur_id, cur_id))

        for row in c.fetchall():
            other_id = row['source_id'] if row['target_id'] == cur_id else row['target_id']
            if other_id in visited:
                continue
            visited.add(other_id)

            # 确定方向：cur_id → other_id 的方向
            if row['source_id'] == cur_id:
                direction = f"→ {row['relation_type']} →"
            else:
                direction = f"← {row['relation_type']} ←"

            chain.append({
                'id': row['id'],
                'summary': row['summary'],
                'type': row['source_type'],
                'creator': row['created_by'],
                'depth': cur_depth + 1,
                'direction': direction,
            })
            frontier.append((row['id'], cur_depth + 1))

    return chain


def _print_chain(chain: list):
    """打印因果链"""
    if not chain:
        return

    target = chain[0]
    print(f"\n🔗 #{target['id']} [{target['type']}] ({target['creator']})")
    print(f"   {target['summary']}")
    print()

    for node in chain[1:]:
        indent = "  " * node['depth']
        print(f"{indent}{node.get('direction', '')} #{node['id']} [{node['type']}] ({node['creator']})")
        print(f"{indent}   {node['summary']}")
        print()


def _print_overview(c):
    """概览：关系网络统计"""
    c.execute("SELECT COUNT(*) FROM learning_relations")
    total = c.fetchone()[0]
    c.execute("SELECT relation_type, COUNT(*) FROM learning_relations GROUP BY relation_type")
    by_type = c.fetchall()

    print(f"\n📊 因果关系网络: {total} 条关系")
    for r in by_type:
        label = {'caused_by': '因果', 'generalizes': '泛化', 'same_root': '同根', 'contradicts': '矛盾'}
        print(f"   {label.get(r[0], r[0])}: {r[1]}")

    # 最多连接的 learnings
    c.execute("""
        SELECT l.id, substr(l.content, 1, 80) as summary, COUNT(*) as cnt
        FROM (
            SELECT source_id as lid FROM learning_relations
            UNION ALL
            SELECT target_id as lid FROM learning_relations
        ) lr
        JOIN learnings l ON lr.lid = l.id
        GROUP BY l.id
        ORDER BY cnt DESC
        LIMIT 5
    """)
    print("\n🔗 连接最多的 learnings (枢纽节点):")
    for r in c.fetchall():
        print(f"   #{r[0]} (×{r[2]}): {r[1][:80]}")
