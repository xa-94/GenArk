# GenArk Phase 3 — 知识层架构

> **版本**: v1.0
> **日期**: 2026-06-06
> **作者**: 守山（主智能体）
> **来源**: 2026-06-04/06 六轮多 Agent 会议共识
> **状态**: 已执行

---

## §0 范围

### Phase 3 做什么

GenArk 从「观察型」升级为「反馈型」——在采集管线之上叠加 learnings 层，实现：

```
事件采集（已有）
  → learnings 提取（新增）
  → 去重 + 审核（新增）
  → 归档路由 → 知识层（新增）
  → 日报面板呈现（改造）
```

### Phase 3 不做什么

| 项 | 原因 |
|----|------|
| 全自动 learnings 提取 | 方案 B（人工审核），Phase 4 达标后切方案 A |
| UI 看板 / Web 界面 | GenArk 定位 CLI + 钉钉推送 |
| 修改现有 Event Store | learnings 是叠加层 |
| C 类跨 Agent 模式（~500 条） | 置信度不稳定 |
| embedding 向量检索 | 建表但暂不填充 |
| 祥霭分身 Agent | Phase 4 |

### 和 Phase 2 的关系

Phase 2 管线（采集 cron ×3 + 拼版日报 cron ×1）**不改动**。learnings 是纯叠加层——新表建在 genark.db、新面板缀在日报末尾、新 cron 独立运行。

---

## §1 学习闭环架构

### 管道式异步架构

```
┌─────────────────────────────────────────────────────────┐
│                    Phase 2 管线（不改）                    │
│  采集 cron ×3 ──→ events 表 ──→ daily-all composer ──→ 钉钉 │
└─────────────────────────────────────────────────────────┘
                         │
                         │ 事件作为 learnings 原料池
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Phase 3 叠加层（新增）                   │
│                                                         │
│  事件 ──→ [过滤层] ──→ 手建 learnings 入库                │
│    │                    │                               │
│    │    A 类（赫明）      ▼                               │
│    │    B 类（守山）   learnings 表                       │
│    │                    │                               │
│    │                    ▼                               │
│    │              审核 cron（每日 10:00）                  │
│    │                    │                               │
│    │              ┌─────┴─────┐                          │
│    │           approve     reject                        │
│    │              │                                    │
│    │              ▼                                    │
│    │        消费记录 → learning_consumptions             │
│    │              │                                    │
│    │              ▼                                    │
│    │        归档路由（人工 / Phase 4 自动）                │
│    │         pattern→Skill                              │
│    │         convention→AGENTS.md                       │
│    │         bug_fix/correction→Memory                  │
│    │              │                                    │
│    │              ▼                                    │
│    │        日报 2.0 learnings 面板                      │
└─────────────────────────────────────────────────────────┘
```

**关键设计决策**：异步管道。learnings 不阻塞 Agent 执行路径——采集→提取→反馈全部离线完成。

### 数据模型

```sql
-- 主表：learnings
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('bug_fix','correction','pattern','convention')),
    source_ref TEXT,          -- 源事件 ID（可追溯）
    content TEXT NOT NULL,    -- 学习内容
    category TEXT,            -- 分类标签
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    confidence REAL,          -- 置信度（Phase 3 人工标注，Phase 4 自动）
    created_by TEXT NOT NULL, -- heming / shoushan
    reviewer TEXT,            -- 审核人
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 去重索引（建表但 Phase 3 暂不填充）
CREATE TABLE IF NOT EXISTS learning_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    embedding BLOB,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 消费日志
CREATE TABLE IF NOT EXISTS learning_consumptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    learning_id INTEGER NOT NULL REFERENCES learnings(id),
    consumed_by TEXT NOT NULL,   -- heming / shoushan / guyuan
    action TEXT NOT NULL,        -- view / apply / reject
    context TEXT,                -- 消费场景描述
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 和 gem-team Persist Learnings 的对比

| 维度 | gem-team | GenArk Phase 3 |
|------|----------|----------------|
| 提取方式 | Agent 返回结构化 `learnings` 字段 | 人工从事件筛选 + 手建入库 |
| 去重 | 哈希 + 语义相似度 | learning_embeddings 表预留，Phase 4 启用 |
| 置信度 | 硬阈值 <0.85 丢弃 | 人工审核 approve/reject |
| 归档路由 | pattern→Skill / fact→Memory / convention→AGENTS.md（自动） | 同，Phase 3 人工执行，Phase 4 全自动 |
| 独有优势 | 全自动 | 跨 Agent 交互模式提取（gem-team 无此维度） |

### 消费端渐进授权

```
Phase 3（方案 B）— 人工审核半开路
  status=pending → 每日 review → approve/reject
  → 审核通过的手动写入 Agent 知识层

Phase 4 切换条件（三个全部达标）：
  1. learnings 连续 30 天 false positive < 5%
  2. 去重准确率 > 90%
  3. 祥霭确认「这个面板我信了」
```

---

## §2 知识流架构

### 分布式 Envelope 模型

四个组件拼合——不追求一个大而全的文档，四个独立组件各司其职：

```
┌──────────────────────────────────────────────┐
│            分布式 Envelope                     │
│                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐
│  │ 读写规则 │  │ handoff │  │ 决策日志 │  │learnings │
│  │   表     │  │ schema  │  │         │  │  store   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬─────┘
│       │            │            │            │
│   AGENTS.md    .qoder/     decisions/    genark.db
│   末尾追加     handoffs/   decision-    learnings
│               *.md        log.jsonl     三表
└──────────────────────────────────────────────┘
```

### 读写规则表（所有权矩阵）

已写入 `AGENTS.md` 末尾。核心原则：

| 层 | 写权限 | 读权限 |
|----|:------:|:------:|
| PRD | 顾远 | 全员 |
| AGENTS.md | 守山 | 全员 |
| Memory | 各 Agent 自写 | 本 Agent + GenArk 只读 |
| Skill | 各 Agent 自建 | 本 Agent + GenArk 只读 |
| ROLE.yaml | 顾远(初版)→守山(更新) | 全员 + GenArk |
| handoff | 顾远(PM→TL) / 赫明(TL→Ops) | 全员 |
| 看板 | 全员 | 全员 |
| 决策日志 | 守山 | 全员 |
| learnings | 系统 + 人工 | 审核者 + 日报 |

### handoff schema

YAML frontmatter 四必填字段：

```yaml
task_id: genark-phase3
scope: add                    # add / modify / fix
data_sources:                 # 路径列表
  - genark.db::events
  - ~/.hermes-team/meetings/
acceptance_criteria:          # 3-8 条可验证断言
  - AC1: ...
  - AC2: ...
```

加上守山运维视角的两个字段：
- `rollback_steps`：回滚命令 + 目标状态
- `env_vars`：需设置的环境变量

校验工具：`engine/bin/validate-handoff.py`

### 决策日志

路径：`~/.hermes-team/decisions/decision-log.jsonl`

```json
{"timestamp":"2026-06-06T08:55:00+08:00","decision":"GenArk Phase 3 优先于 SPY Batch B","rationale":"learnings 闭环是基础设施，越早跑通越好"}
```

格式：每行一条 JSON，append-only。守山唯一维护。

### ~/.hermes-team → GenArk 迁移路径

祥霭原则：「`~/.hermes-team` 是现在的家，GenArk 是新房子。设计时留迁移路径。」

- Phase 3 只建新资产，不迁移旧资产
- 决策日志、会议记录留在 `~/.hermes-team/`
- ROLE.yaml 放在各 Agent 的 HERMES_HOME，GenArk 采集引擎顺带采集
- 将来迁移时，`~/.hermes-team/` → GenArk 作为历史快照整体导入

---

## §3 角色接口架构

### SOUL + ROLE 两层模型

```
SOUL.md（永不 YAML 化）
  ├─ 角色灵魂：声音、原则、避免
  ├─ 自然语言，体现「人味」
  └─ 只属于本 Agent，GenArk 不解析

ROLE.yaml（合约面）
  ├─ inputs：谁给我什么、什么格式
  ├─ outputs：我产出什么、交付到哪
  ├─ boundaries：做什么、不做什么
  └─ delivery_checklist：交付标准
```

**设计原则**：SOUL 是角色内核——永不结构化。ROLE 是合约面——可被 GenArk 采集和校验。两层分离，不互相污染。

### ROLE.yaml 字段规范

```yaml
version: "1.0.0"
last_updated: "2026-06-06"

role:
  id: shoushan           # 唯一标识
  name: 守山              # 显示名
  title: 主智能体          # 职位
  product_line: genark    # 归属产品线
  instance_path: "~/.hermes/"  # 实例路径

inputs:                   # 谁给我什么
  - from: xa_huang
    type: directive
    trigger: "祥霭 @ 或会议指令"

outputs:                  # 我产出什么
  - type: decision_log
    format: jsonl
    deliver_to: "~/.hermes-team/decisions/"

boundaries:               # 边界
  does: [...]
  does_not: [...]

delivery_checklist: [...] # 交付标准
```

### 维护流程

```
提议（任何人）→ 顾远审核 → 祥霭确认 → 守山更新 ROLE.yaml
```

### 和 handoff schema 的校验关系

- ROLE.yaml 定义 Agent **该产出什么**
- handoff schema 定义**这次具体要产出什么**
- `validate-handoff.py` 校验 handoff 必填字段
- Phase 4 可实现 ROLE.yaml 和 handoff 的一致性自动检查：handoff 要求的产出是否在 ROLE 的 outputs 范围内

---

## §4 日报 2.0

### learnings 面板集成

日报末尾追加三个区块：

```
🧠 知识沉淀
   当日新增 150 · 待审核 0
   最近入库：
   🐛 #1 [bug_fix] 工具成功率统计不能用子字符串匹配...
   🐛 #2 [bug_fix] _is_tool_failure 中 'error' in data 误判...
   🐛 #3 [python_pattern] 结构化判定用 dict.get('key')...

⚡ 重大事件
• 赫明 今日技能变化 +6 → 正在快速成长
• 守山 今日技能变化 +8 → 正在快速成长
```

### composer 改动

`engine/genark/composer.py` 新增 `_build_learnings_panel()`，< 50 行。在 `daily-all` 的 compose 阶段，读取 learnings 表统计当日新增 + 待审核数 + 最近 3 条摘要。

### N 人拼版扩展性

当前 3 人（顾远/赫明/守山）。日报按 agent_id 遍历，新增 Agent 只需：
1. 添加采集 cron
2. 创建 ROLE.yaml
3. 采集引擎自动识别新 agent_id
4. `daily-all` 自动纳入拼版

无硬编码人数限制。

---

## §5 交付计划

### Day 1-3（已完成）

| Day | 交付物 | 负责人 | 状态 |
|:---:|--------|:------:|:--:|
| 1 | PM handoff + ROLE.yaml ×3 + 读写规则表 + validate-handoff.py | 顾远 / 赫明 | ✅ |
| 2 | migrate-phase3.sql → 建表 + A 类 50 条 + B 类 100 条 + decision-log.jsonl + 审核 cron | 守山 / 赫明 | ✅ |
| 3 | 日报 2.0 composer 改造 + --no-push 试跑 + learnings 全量审核归档 | 赫明 / 守山 | ✅ |

### Phase 3 中期（待做）

- 验收清单 schema（handoff schema 的补充）
- Agent 接入标准化文档（新 Agent 如何接入 GenArk）
- handoff 历史 frontmatter 回溯（旧 handoff 反填 YAML）

### Phase 4 触发条件

全部达标后启动：
1. learnings 连续 30 天 FP < 5%
2. 去重准确率 > 90%
3. 祥霭确认信任

Phase 4 内容：全自动 learnings 提取 + 语义去重 + 自动归档写入 Agent 知识层。

---

## §6 Agent 接入标准化（Phase 3 中期）

### 新 Agent 接入清单

```
1. 创建 HERMES_HOME/profile
2. 创建 ROLE.yaml（按 §3 字段规范）
3. 添加采集 cron：*/30 * * * * collect-{agent}.sh
4. 采集引擎自动识别 → genark.db collector_cursor 新增一行
5. daily-all 自动纳入拼版
```

### 祥霭分身 Agent 接入预设计

祥霭 08:30 插话：「分身 Agent」——和自己有相同记忆、相同行为模式的观察者。

预设计要点：
- 分身 Agent = GenArk 第四个采集对象
- 分身的 Memory 和原身同步（而非独立积累）
- 接入方式同标准 Agent 接入清单
- Phase 4 落地

---

## 附录 A：gem-team 参考

### 借鉴什么

| 设计 | 借鉴程度 | GenArk 落地 |
|------|:--:|------|
| Persist Learnings | 核心借鉴 | learnings 三表 + 归档路由 |
| Context Envelope | 方向借鉴 | 分布式 Envelope（四组件拼合），非单一快照 |
| Agent 接口化 | 限定借鉴 | ROLE.yaml 合约面，SOUL.md 永不结构化 |
| 渐进授权 | 直接借鉴 | Phase 3 人工 → Phase 4 自动 |

### 偏离什么

| 设计 | 偏离原因 |
|------|---------|
| Agent 间用结构化合约对话 | GenArk 观察价值依赖自然语言信号 |
| Orchesterator 独写 Envelope | 我们三个场景三个维护者 |
| 全自动 learnings | 我们没有 `learnings` 字段，需人工种子跑通管道 |
| 硬阈值置信度 | 祥霭的纠正信号不是概率问题 |

---

## 附录 B：会议教训

1. **记录权归属**：祥霭插话记录重复（08:03 迁移原则被守山和顾远各记一次）→ 明确记录权归守山
2. **分身构想**：祥霭提出了长期解法——分身 Agent 代记
3. **六轮议程收敛模式**：六个洞见 → 三个设计 → 五个 Round → 全部收敛。分歧全在执行路径，核心方向无人否定——健康的收敛模式
4. **活案例证明**：祥霭 08:14「赫明不知道顾远搬家」恰好是 learnings 闭环价值的实时证明——不是假设，是正在发生的痛点
