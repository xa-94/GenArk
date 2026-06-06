# GenArk Phase 3 运维交接单

> **日期**: 2026-06-06
> **交付人**: 赫明（Tech Lead）
> **接收人**: 守山（主智能体 / 运维主持人）
> **代码基线**: T3 交付（DDL 已执行 / seed 已入库 / composer.py 已改）

---

## 一、变更概要

Phase 3 learnings 闭环建设——在 genark.db 中新增三张表 + A 类 50 条 learnings 入库 + 日报 2.0 learnings 面板。

| 变更 | 说明 |
|------|------|
| 新表 `learnings` | 知识沉淀主表（id/source_type/content/category/status/confidence/created_by） |
| 新表 `learning_embeddings` | 向量索引（Phase 3 建表但暂不填充） |
| 新表 `learning_consumptions` | 学习消费追踪 |
| `engine/bin/seed-learnings-a.py` | A 类 50 条 seed 脚本（幂等，重复执行 0 新增） |
| `engine/bin/migrate-phase3.sql` | DDL 迁移脚本（守山产出，赫明执行） |
| `engine/genark/composer.py` | 追加 `_build_learnings_panel()` — 日报 2.0 末尾 learnings 区块 |
| `engine/bin/validate-handoff.py` | PM handoff 四必填字段校验工具（T2 产出） |

---

## 二、环境现状

### 数据库

```
路径: /data/projects/genark/engine/data/genark.db
大小: ~16MB
磁盘: 866GB 可用
新表: learnings (50 条) / learning_embeddings (0) / learning_consumptions (0)
现有表: events / daily_reports / collector_cursor / file_snapshots — 未修改
```

### 文件

```
engine/genark/composer.py       ← 新增 _build_learnings_panel()
engine/bin/migrate-phase3.sql   ← 已执行（幂等：CREATE TABLE IF NOT EXISTS）
engine/bin/seed-learnings-a.py  ← 幂等 seed 脚本
engine/bin/validate-handoff.py  ← PM handoff 校验
.qoder/reports/genark-phase3-tech-assessment-2026-06-06.md
.qoder/handoffs/pm-handoff-phase3-2026-06-06.md
```

### ROLE.yaml

```
~/.hermes/profiles/heming/ROLE.yaml  ← v1.0.0（5项 checklist）
~/.hermes-pm/ROLE.yaml              ← v1.0.0（4项 checklist）
~/.hermes/ROLE.yaml                 ← v1.0.0（5项 checklist）
```

---

## 三、待守山执行（Day 2）

以下 4 项属于守山 Day 2 交付范围，T5 交接后执行：

| # | 事项 | 路径/命令 | 优先级 |
|---|------|----------|:--:|
| 1 | B 类 learnings 入库（100 条） | learnings 表（source_type=correction） | 🔴 |
| 2 | decision-log.jsonl | `~/.hermes-team/decisions/decision-log.jsonl`（append-only，≥5 条祥霭决策） | 🔴 |
| 3 | 审核 cron 配置 | `crontab -e` 添加每日 10:00 审核任务 | 🔴 |
| 4 | AGENTS.md 同步 | 版本号 + Phase 3 进行中状态（已完成：v1.2.0 / 读写规则表已写入） | 🟡 |

---

## 四、验证命令

```bash
cd /data/projects/genark/engine

# 1. 验证三张新表存在
python -c "
import sqlite3
conn = sqlite3.connect('data/genark.db')
for t in ['learnings','learning_embeddings','learning_consumptions']:
    c = conn.execute('SELECT COUNT(*) FROM sqlite_master WHERE type=\"table\" AND name=?',(t,)).fetchone()[0]
    print(f'{t}: {\"✅\" if c else \"❌\"} ({c})')
conn.close()
"

# 2. 验证 A 类 learnings 数量
python -c "
import sqlite3
conn = sqlite3.connect('data/genark.db')
c = conn.execute('SELECT COUNT(*) FROM learnings WHERE created_by=\"heming\"').fetchone()[0]
print(f'A类 learnings: {c}/50')
conn.close()
"

# 3. 日报 2.0 试跑（不推送）
/home/hermes/.local/bin/uv run python -m genark.cli daily-all --no-push --date $(date +%Y-%m-%d) 2>&1 | grep -A 5 "知识沉淀"

# 4. 哈希链验证（三人）
for agent in heming guyuan shoushan; do
  /home/hermes/.local/bin/uv run python -m genark.cli verify-chain --agent $agent
done

# 5. seed 脚本幂等测试
python engine/bin/seed-learnings-a.py
# 应输出: "0 条新增 / 50 条已存在跳过"
```

---

## 五、审核 cron 参考

```bash
# 每日 10:00 输出 pending learnings 列表
0 10 * * * /home/hermes/.local/bin/uv run python -c "
import sqlite3
conn = sqlite3.connect('/data/projects/genark/engine/data/genark.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(\"\"\"SELECT id, source_type, category, substr(content,1,100) as preview
    FROM learnings WHERE status='pending' ORDER BY created_at DESC\"\"\").fetchall()
print(f'待审核 learnings: {len(rows)} 条')
for r in rows[:20]:
    print(f'  #{r[\"id\"]} [{r[\"source_type\"]}] {r[\"category\"] or \"-\"}: {r[\"preview\"]}...')
conn.close()
" >> /data/projects/genark/engine/data/review.log 2>&1
```

---

## 六、回滚方案

Phase 3 不改动现有 Event Store / 采集 cron / 日报推送管线，回滚只需：

```bash
# 删除三张新表（不丢事件数据）
sqlite3 /data/projects/genark/engine/data/genark.db <<SQL
DROP TABLE IF EXISTS learnings;
DROP TABLE IF EXISTS learning_embeddings;
DROP TABLE IF EXISTS learning_consumptions;
SQL

# composer.py 回退到 Phase 2 版本
git checkout HEAD~1 -- engine/genark/composer.py
```

---

## 七、注意事项

1. **learnings 表不修改 events** — 三张新表是叠加层，不影响现有哈希链
2. **seed-learnings-a.py 幂等** — 按 content 去重，重复执行安全
3. **composer.py 降级保护** — learnings 表不存在时 `_build_learnings_panel()` 返回 None，不影响日报主流程
4. **B 类入库注意** — source_type 必须为 `correction`，created_by=`shoushan`，status=`pending`
5. **decision-log.jsonl 格式** — 每行一条 JSON：`{"timestamp":"2026-06-06T...","decision":"...","rationale":"...","context":"..."}`

---

> **交接确认**: 以上 7 节已覆盖八项运维交接要素（变更概要/环境现状/待执行清单/验证命令/cron 参考/回滚方案/注意事项）。守山按 §三 清单执行 Day 2 交付后，Phase 3 基础设施即完整。
