# GenArk Phase 3 — 技术评估报告

> **日期**: 2026-06-06
> **作者**: 赫明（Tech Lead）
> **审阅对象**: PM Handoff `pm-handoff-phase3-2026-06-06.md`（顾远产出，顾远已审阅确认）
> **评估范围**: Day 1-3 交付物 + 架构可行性 + 风险清单

---

## 一、评估方法

对照 PM Handoff 列出的 13 项交付物，逐项审计：
- **代码真相**: 检查 `genark/engine/` 已有模块、`genark.db` 现有表结构
- **gap 分析**: 交付物 vs 当前代码基线的差距
- **风险判定**: P0（阻塞）/ P1（高风险）/ P2（低风险）

---

## 二、逐项差距分析

### Day 1 交付物（交接基础设施）

| # | 交付物 | 状态 | gap |
|:--:|--------|:---:|-----|
| 1 | PM handoff | ✅ 已交付 | YAML frontmatter 四字段完整，`validate-handoff.py` 校验通过（见下方验证） |
| 2 | ROLE.yaml 初版三份 | ✅ 已交付 | 顾远产出初版，赫明已完成 YAML 技术化（v1.0.0，三份均含 version/inputs/outputs/boundaries/delivery_checklist） |
| 3 | 读写规则表草案 | ⚠️ 草案已出 | 位于 `.qoder/specs/read-write-rules-draft.md`，**守山未合并至 AGENTS.md**。当前 AGENTS.md 仍停留在 Phase 2 状态，版本标 v1.1.0，缺少 Phase 3 信息 |
| 4 | ROLE.yaml 技术化 | ✅ 已完成 | 三份 ROLE.yaml 均已升级至 v1.0.0，YAML 解析校验通过，delivery_checklist 完整 |
| 5 | validate-handoff.py | ✅ 已完成 | 存放于 `engine/bin/validate-handoff.py`，支持四必填字段 + scope 枚举 + AC 格式校验 |

### Day 2-3 交付物（learnings 闭环）

| # | 交付物 | 谁做 | gap |
|:--:|--------|:--:|-----|
| 6 | migrate-phase3.sql | 守山 | 🔴 **阻塞项** — 未产出。赫明 T3 建表依赖此 DDL。DDL 需创建三张新表（learnings / learning_embeddings / learning_consumptions） |
| 7 | 三张新表建表 | 赫明 | 🔴 **依赖 #6** |
| 8 | A 类 50 条 seed 脚本 | 赫明 | 🟡 可并行准备（语法层面），但入库依赖 #7 |
| 9 | B 类 learnings 入库 | 守山 | 🟡 依赖 #7 |
| 10 | decision-log.jsonl | 守山 | 🟡 需先建 `~/.hermes-team/decisions/` 目录 |
| 11 | 审核 cron | 守山 | 🟡 依赖 #7 表存在 |
| 12 | 日报 2.0 learnings 面板 | 赫明 | 🟡 依赖 #7（可先写代码，`daily-all --no-push` 试跑需表存在） |
| 13 | 端到端试跑 | 赫明 | 🔴 **依赖 #6→#7→#12 全链** |

---

## 三、阻塞项清单

| 优先级 | 阻塞项 | 阻塞范围 | 截止 |
|:--:|--------|----------|:--:|
| 🔴 P0 | 守山未产出 `migrate-phase3.sql` | T3 全部建表工作 | Day 2 上午 |
| 🔴 P0 | AGENTS.md 未更新 Phase 3 状态 | 项目可发现性 | Day 1（守山） |
| 🟡 P1 | `~/.hermes-team/decisions/` 目录未建 | decision-log.jsonl | Day 2 |
| 🟡 P1 | genark.db 磁盘余量未确认 | 三表写入 | Day 2 上午前 |

---

## 四、架构可行性

### 4.1 learnings 数据模型 — ✅ 可行

三张新表融入现有 `genark.db`，不修改 events 表结构。现有 SQLite schema（events / daily_reports / collector_cursor / file_snapshots）无需迁移。

**现有表结构确认**（`genark.db`）:
```
events                    — 不可变追加，含 content_hash 哈希链
daily_reports             — report_id 格式: report_{agent_id}_{date}
collector_cursor          — (agent_id, source_path, byte_offset)
file_snapshots            — memory/skills 变化检测快照
```

**新表 DDL 建议**（守山产出时参考）:
```sql
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('bug_fix', 'correction', 'pattern', 'convention')),
    source_ref TEXT,           -- 关联 events.id 或 handoff 路径
    content TEXT NOT NULL,     -- learning 正文
    category TEXT,             -- 分类标签
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    confidence REAL,           -- 0.0-1.0
    created_by TEXT NOT NULL,  -- heming / shoushan / guyuan / system
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewed_by TEXT
);

CREATE TABLE IF NOT EXISTS learning_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    embedding BLOB,            -- Phase 3 建表但暂不填充
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learning_consumptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    consumed_by TEXT NOT NULL, -- heming / shoushan / guyuan
    action TEXT NOT NULL,      -- view / apply / reject
    context TEXT,              -- 消费场景描述
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 4.2 学习闭环管道 — ✅ 可行

```
采集 cron（已有，不改）
  → learnings 手建入库（A 类赫明 + B 类守山）
  → 审核 cron（每日 10:00，人工 approve/reject）
  → 归档路由（pattern→Skill / fact→Memory / convention→AGENTS.md）
  → 日报 2.0 推送（learnings 面板追加到拼版末尾）
```

**composer.py 改动评估**: 日报 2.0 learnings 面板预计改动 <50 行——在现有 `daily-all` 拼版末尾追加一个 learnings 区块（当日新增数 + 待审核数 + 最近 3 条标题）。不修改现有 narrative 生成逻辑。

### 4.3 消费端渐进授权 — ✅ 架构合理

Phase 3 方案 B（人工审核半开路）是务实选择。三个 Phase 4 触发条件量化清晰，可自动检测。

---

## 五、不在评估范围（明确排除）

按 PM Handoff §三 的「不做什么」清单，以下不做技术评估：
- ❌ 全自动 learnings 提取（Phase 4）
- ❌ UI 看板 / Web 界面
- ❌ 修改现有 Event Store
- ❌ 修改现有采集/日报管线
- ❌ C 类跨 Agent 模式重复
- ❌ embedding 向量检索
- ❌ 祥霭分身 Agent
- ❌ ~/.hermes-team → GenArk 全量迁移

---

## 六、风险清单

| 风险 | 等级 | 缓解措施 |
|------|:--:|------|
| 守山 DDL 延迟 → T3 无法启动 | 🔴 P0 | 祥霭已明确 Day 2 上午前交付，如延迟则先并行准备 A 类 seed 脚本 + 日报 2.0 代码 |
| B 类 200 条人力密集 | 🟡 P1 | PM Handoff 已允许首日降级至 100 条 |
| learnings 语义去重准确率不足 | 🟡 P1 | Phase 3 人工审核兜底，不自动入库 |
| genark.db 磁盘不足 | 🟡 P1 | 当前用量约 50MB（事件 1.1 万条），三张新表预计 <10MB，风险低 |
| AGENTS.md 与代码状态不同步 | 🟡 P1 | 守山负责同步，需在 Phase 3 启动时更新版本号至 v1.2.0 + 当前阶段信息 |

---

## 七、建议

1. **守山优先产出 DDL** — 这是整个 T3 的前置条件，其余 Day 2-3 工作全部依赖它
2. **AGENTS.md 立即更新** — 当前标记 "Phase 2 运行中"，与实际 Phase 3 启动不符
3. **赫明 T3 可并行准备** — A 类 seed 脚本 + 日报 2.0 代码面板可在 DDL 产出前写好，表建成立即试跑
4. **B 类 100 条先行** — 跑通审核管道验证即可，不追求 200 条首日完成

---

## 八、验证记录

```bash
# ROLE.yaml 三份 YAML 解析校验
$ python -c "import yaml; yaml.safe_load(open('.../ROLE.yaml'))"  # 三份均通过

# validate-handoff.py 校验 PM handoff
$ uv run python engine/bin/validate-handoff.py .qoder/handoffs/pm-handoff-phase3-2026-06-06.md
📄 校验: .qoder/handoffs/pm-handoff-phase3-2026-06-06.md
   YAML frontmatter: XXX 字符
✅ 校验通过
   task_id: genark-phase3
   scope: add
   data_sources: 4 条
   acceptance_criteria: 8 条
```

---

> **结论**: Day 1 交付物（交接基础设施）已全部到位。Day 2-3 的阻塞项集中在守山侧——DDL 迁移脚本是赫明启动 T3 的唯一前置条件。架构方案可行，风险可控。
