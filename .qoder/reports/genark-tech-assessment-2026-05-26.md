# GenArk — 技术评估报告

> **日期**: 2026-05-26
> **作者**: 赫明（Tech Lead）
> **评估对象**: GenArk PRD v1.0 + Phase 1 方案
> **评估方法**: 文档审查 + 实际数据环境探查

---

## 一、总体可行性判断

**结论：✅ 可行**

PRD v1.0 的设计在技术层面是可实现的。Phase 1 范围克制、目标清晰，可以在不改造 Hermes 核心的前提下跑通。建议按 Phase 1 → 2 → 3 → 4 渐进式推进，不在早期阶段过度工程化。

---

## 二、各评估点回复

### 2.1 数据采集

#### Hermes 会话 JSONL 增量采集

**结论：✅ 可行，方案成熟**

实测数据环境：
```
守山 (.hermes/sessions/) — 主智能体，祥霭最核心的助手:
  - 15 个 JSONL 文件（用户交互），4.0MB  ← 叙事素材的真正来源
  - 526 个 JSON 文件（Cron 执行记录 + request_dump），98MB
  - 12KB memories / 504KB skills / 8.1MB logs
  - 注：文件数守山自己核实为 541（含刚才新增），与测量时间差一致

赫明 (.hermes-genboz/sessions/) — Tech Lead:
  - 17 个 JSONL 文件（用户交互），4.6MB
  - 142 个 JSON 文件（Cron + dump），68MB
  - 12KB memories / 476KB skills / 5.1MB logs

顾远 (.hermes-pm/sessions/) — PM:
  - 16 个 JSONL 文件（用户交互），4.0MB
  - 66 个 JSON 文件（Cron + dump），23MB
  - 16KB memories / 240KB skills / 3.1MB logs

统一格式：每行一个 JSON 对象，role ∈ {session_meta, user, assistant, tool}
sessions.json 提供 session_key → session_id/created_at/platform 映射

⚠️ 关键区分：.jsonl = 用户交互流（叙事素材），.json = Cron + dump（元数据）
   三个实例的交谈数据量惊人一致：各 ~4MB / 15-17 文件
```

**增量方案**：
- 通过文件 mtime + 行级游标（记录 `{file: offset}` 状态）实现增量采集
- 不需要修改 Hermes 源码，GenArk 作为外部 consumer 读取即可
- 采集频率：cron 每 30 分钟扫描一次即可满足"延迟 < 30 分钟"的指标

**注意**：当前 sessions 数据只在本地磁盘，若要做跨机器汇聚（Phase 2），需要 rsync 或 API 中转。但 Phase 1 只在同一台机器跑，无此问题。

#### Memory / Skills 文件 diff 检测

**结论：✅ 可行，且比预期更简单**

实测格式：
- Memory：`memories/MEMORY.md`（代理记忆）+ `memories/USER.md`（用户画像），Markdown 格式，`§` 分隔条目
- Skills：目录下的 `.md` 文件 + `.usage.json`（结构化的使用统计：use_count、last_used_at、patch_count 等）

**diff 方案**：
- Memory：对 MEMORY.md / USER.md 做内容哈希，变化时触发结构化解析（按 `§` 拆分 + 逐条哈希对比）
- Skills：`.usage.json` 本身就是结构化数据，直接解析比较即可；技能内容变化通过文件 mtime + 哈希检测

#### 跨实例数据汇聚

**结论：⚠️ 需要方案选型**

当前三个智能体的情况：
| 智能体 | Hermes 实例 | JSONL（交谈） | JSON（Cron） | 备注 |
|--------|------------|---------------|-------------|------|
| 守山 | `~/.hermes/` | 15 文件 / 4.0MB | 526 文件 / 98MB | **主智能体**，Cron 执行最频繁 |
| 赫明 | `~/.hermes-genboz/` | 17 文件 / 4.6MB | 142 文件 / 68MB | Tech Lead |
| 顾远 | `~/.hermes-pm/` | 16 文件 / 4.0MB | 66 文件 / 23MB | PM |

> **注意**：AGENTS.md 和 PRD 中写的是 `~/.hermes-shoushan/`，但实际守山实例在 `~/.hermes/`（主智能体目录）。守山已确认：HERMES_HOME = `~/.hermes/`，角色 = 主智能体 + 通用助手，非纯 DevOps。
>
> **重要区分**：三个实例的交谈数据（JSONL）规模惊人一致，各 ~4MB / 15-17 文件。Cron 执行记录（JSON）占了总量的 90%+，用于叙事的意义有限（最多作为"守山今天执行了周回顾"这类元事件）。

Phase 1 选择从顾远开始是**正确的策略**——交谈数据量三个实例差不多，顾远的 Cron 噪音最少（66 文件），最适合作为验证管道的第一站。

| 方案 | 优点 | 缺点 |
|------|------|------|
| A. 本地文件读取（当前） | 零延迟、零改造 | 只适用于同机部署 |
| B. rsync + 定时同步 | 简单可靠 | 有延迟，需要 SSH key |
| C. Hermes 新增 `export` 工具 | 标准化、可扩展 | 需要改造 Hermes 核心 |
| D. alp_outbox 模式（PRD 提到） | 标准化输出格式 | 需要定义协议 + 实现 |

**建议**：Phase 1 用方案 A；Phase 2 先方案 B 快速验证，远期考虑方案 D（标准化输出协议）。

---

### 2.2 存储方案

#### 双层架构：Event Store + State Store

**结论：✅ 方案合理，是事件溯源的标准模式**

- Event Store（不可变追加 + 哈希链）→ 事件溯源的标准做法，已在区块链/审计系统中广泛验证
- State Store（可重建快照）→ 正确。快照可以从 Event Store 重放重建，这意味着 State Store 可以被视为缓存而非真相源

#### SQLite 是否合适

**结论：✅ Phase 1-3 合适，Phase 4 可能需要补充**

| 维度 | SQLite 表现 | 评估 |
|------|-----------|------|
| 单机部署 | 零配置、零运维 | ✅ 非常适合 Phase 1 |
| 写入性能 | 追加为主，SQLite 很擅长 | ✅ 日增量 < 100MB，完全够 |
| 哈希链验证 | 需要应用层实现 | ✅ 轻量级，Python 几行代码 |
| 知识图谱查询（Phase 3） | 递归 CTE 可实现图遍历 | ⚠️ 小规模可以，大规模时性能下降 |
| 并发读取 | 单写多读，WAL 模式 | ✅ 足够 |
| 跨实例汇聚（Phase 2+） | 单文件，不适合多写入者 | ⚠️ 需要改为 PostgreSQL 或保持各实例独立 DB + 汇聚层 |

**建议**：
- Phase 1-2：SQLite，WAL 模式，数据量完全可控
- Phase 3（知识图谱）：如果图谱节点 < 10,000，SQLite CTE 够了。超过后可以考虑用 Neo4j 或嵌入 ArangoDB。但这是很久以后的事
- 存储增长预估：赫明 6 天 72MB sessions → 日增 ~12MB。顾远 26MB/未定期限。Phase 1 只采集顾远，月增估计 < 200MB，远低于 100MB 的保守估计（实际是上限更宽）。**预估合理甚至保守**

---

### 2.3 LLM 集成

#### 日报叙事生成

**结论：✅ 可行，是 LLM 的强项**

日报生成 = 将当天的事件摘要 + 统计数字作为 prompt 输入 → LLM 生成叙事。这是 LLM 最擅长的"总结 + 润色"任务。

风险点：
- LLM 断连（DeepSeek 用户已知问题）→ 需要重试 + 降级为纯数据日报
- 长篇 session 可能超出上下文窗口 → 需要先做事件摘要再喂入 LLM

#### 故事线检测

**结论：⚠️ 中高风险，Phase 4 的事**

从事件流中识别叙事模式需要多步推理，prompt engineering 可以做到但质量不稳定。建议 Phase 4 时做 A/B 测试。

#### LLM 输出可追溯性

**结论：✅ 技术上可行，靠 prompt 约束**

方案：在 prompt 中要求 LLM 输出 `【引用: evt_042】` 标记，事后正则提取验证。但这不能 100% 保证 LLM 不编造引用——存在 "幻觉引用" 风险（LLM 编造了引用但实际没有对应事件）。

护栏方案：
1. Prompt 约束（"只能引用提供的 event_id"）
2. 输出后自动验证（正则提取 event_id → 查 Event Store 确认存在 → 打回不存在的引用）
3. 多次抽样人工检查

#### 成本估算

PRD 预估 ¥5/月。实际估算：
- 日报：每天 1 次 × 30 天 = 30 次 LLM 调用
- 每次 ~2000 token 输入 + ~500 token 输出 = ~2500 token
- DeepSeek-V3 价格 ¥1/M input token, ¥2/M output token
- 月成本：30 × (0.002 + 0.001) = **¥0.09** — 远低于预估
- 即使加上故事线/知识提取，月成本 < ¥1

**结论：成本预估极度保守，实际远低于 ¥5/月**

---

### 2.4 核心模块技术风险

#### 知识图谱存储与查询

**结论：⚠️ Phase 3 时需评估**

关系类型（IS_A / REFERENCES / CAUSES / PREVENTS / ALTERNATIVE_TO / CONFLICTS_WITH）共 6 种，SQLite 用节点表 + 边表 + 递归 CTE 可实现。

风险：当知识节点超过 10,000 时，递归 CTE 的多跳查询性能可能下降。但按当前智能体知识积累速度，到达 10,000 节点需要很长时间。

#### 遗忘引擎

**结论：✅ 纯数学，零风险**

公式 `retention = importance × e^(-decay_rate × days)` 是确定性计算，不涉及 LLM。实现就是一条 SQL 或 Python 数学运算。唯一需要注意的是浮点精度（建议用 Decimal）。

#### 技能化学反应

**结论：⚠️ 组合数量需要控制**

当前设计只提到 pairwise（两两组合），计算量可控。但如果扩展到三技能组合，组合数 = C(n,3)，需要限制规则数量。建议 Phase 3 时限定：只计算 pairwise 组合，且只对等级 ≥ 40 的技能计算。

#### 共享看板权限模型

**结论：⚠️ 需要细化设计**

PRD 提到"祥霭看全部、智能体看自己和公开部分"。这本质是 RBAC（基于角色的访问控制），实现不难。但边界情况需要明确：
- 智能体看到其他智能体的"精力状态" → 什么算"忙"？阈值怎么定？
- 祥霭的哪些数据对智能体可见？→ PRD 列出了"公开档案"，但边界需要精确到字段级

---

## 三、Phase 1 最小可行方案

### 3.1 可行性

**✅ 完全可以快速跑通。** Phase 1 的核心就是一个 cronjob + SQLite + LLM API 调用，不涉及：
- 任何 Hermes 核心改造
- 任何 UI 开发
- 任何复杂算法

### 3.2 技术选型建议

| 组件 | 推荐 | 备选 |
|------|------|------|
| 语言 | Python 3.12+ | — |
| 存储 | SQLite (WAL 模式) | — |
| ORM | 不用 ORM，直接用 sqlite3 标准库 | — |
| LLM | DeepSeek-V3（已有 key，成本低） | OpenAI GPT-4o-mini |
| 调度 | cron（系统级） | — |
| 推送 | 钉钉/Telegram API | — |
| 部署位置 | `/data/projects/genark/engine/` | — |

### 3.3 核心流程

```
cron 每 30 分钟触发
  → 增量扫描 sessions/ 目录（文件 mtime + 行游标）
  → 新事件写入 SQLite Event Store
  → 检查 memories/ + skills/ 变化（内容哈希）
  → 变化写入 Event Store
  →
  每天 23:00 日终触发
    → 当日事件聚合 + 统计计算
    → 构造 prompt → LLM 生成日报
    → 推送到祥霭（钉钉）
```

### 3.4 数据 Schema（建议）

```sql
-- Event Store（不可变追加）
CREATE TABLE events (
    id TEXT PRIMARY KEY,           -- evt_YYYYMMDD_XXXXXX
    timestamp TEXT NOT NULL,       -- ISO 8601
    agent_id TEXT NOT NULL,        -- guyuan / heming / shoushan
    event_type TEXT NOT NULL,      -- session_message / memory_change / skill_change / daily_report
    source_path TEXT,              -- 原始数据路径
    content_hash TEXT NOT NULL,    -- SHA-256
    prev_hash TEXT,                -- 链式签名
    payload JSON NOT NULL,         -- 事件内容
    created_at TEXT DEFAULT (datetime('now'))
);

-- 哈希链索引
CREATE INDEX idx_events_agent_time ON events(agent_id, timestamp);
CREATE INDEX idx_events_type ON events(event_type);

-- State Store（可重建快照）
CREATE TABLE agent_state (
    agent_id TEXT PRIMARY KEY,
    stats JSON,                    -- 工具使用统计、活跃度等
    last_event_id TEXT,            -- 快照基于哪个事件
    computed_at TEXT
);
```

### 3.5 工作量估算

| 任务 | 预估人天 | 说明 |
|------|---------|------|
| 项目骨架 + SQLite Schema | 0.5d | Python 项目搭建、建表 |
| JSONL 增量采集器 | 1d | 行游标、mtime 检测、断点恢复 |
| Memory/Skills diff 采集 | 0.5d | 内容哈希、结构化解析 |
| 基础统计计算 | 0.5d | 工具使用次数、活跃度、技能变化 |
| LLM 日报生成 | 1d | Prompt 设计 + DeepSeek API 调用 + 重试 |
| 推送通道 | 0.5d | 钉钉/Telegram |
| 测试 + 文档 | 1d | 单元测试、集成测试 |
| **合计** | **5 人天** | 1 个 Qoder 约 1 周 |

**置信度**：高。所有子任务都是标准 CRUD + API 调用，无未知技术风险。

---

## 四、风险清单及对策

| # | 风险 | 概率 | 影响 | 对策 |
|---|------|------|------|------|
| R1 | LLM 日报幻觉（编造事件） | 中 | 中 | 输出后自动验证引用；降级为纯数据日报 |
| R2 | DeepSeek API 断连 | 高 | 低 | 重试 3 次 + 降级；已知问题，代理绕路已定位 |
| R3 | JSONL 格式未来变化 | 低 | 高 | 采集器做 schema 版本检查，未知格式告警不崩溃 |
| R4 | 存储增长超预期 | 低 | 低 | 交谈 JSONL 日增 < 1MB/实例，Cron JSON 可按需过滤。实际存储压力极小 |
| R5 | 守山 Cron 噪音大（526 个 JSON 混在其中） | 低 | 低 | Phase 1 只处理 JSONL（交谈），JSON（Cron）不作为叙事素材。采集器按文件后缀区分即可 |
| R6 | sessions.json 的 session_key 跨实例不一致 | 低 | 中 | Phase 1 单实例无此问题。Phase 2 需要标准化 agent_id |

---

## 五、PRD 需要调整的部分

### 5.1 守山实例路径

PRD 和 AGENTS.md 中写的是 `~/.hermes-shoushan/`，但实际守山实例在 `~/.hermes/`（主智能体目录）。守山已确认无误。

实测数据（.jsonl = 交谈，.json = Cron/dump）：

| 实例 | 路径 | JSONL | JSON | 角色 |
|------|------|-------|------|------|
| 守山 | `~/.hermes/` | 15 文件 / 4.0MB | 526 文件 / 98MB | 主智能体 + 通用助手 |
| 赫明 | `~/.hermes-genboz/` | 17 文件 / 4.6MB | 142 文件 / 68MB | Tech Lead |
| 顾远 | `~/.hermes-pm/` | 16 文件 / 4.0MB | 66 文件 / 23MB | PM |

三个实例的交谈数据规模惊人一致（各 ~4MB），差异主要在 Cron 噪音量。

**建议**：PRD 和 AGENTS.md 统一修正为 `~/.hermes/`，角色描述改为"主智能体 + 通用助手"。

### 5.2 存储指标过于保守

PRD §7 设定"月增量 < 100MB"。实测赫明 6 天 72MB（含旧格式 JSON），顾远 26MB。**月增 200MB 是更现实的预估**，但这仍然不是问题——SQLite 轻松处理 GB 级数据。

### 5.3 LLM 成本指标过于保守

PRD 预估 < ¥5/月，实际按当前 DeepSeek 价格可能 < ¥0.10/月。建议调整。

### 5.4 Phase 1 "接入顾远" vs 现实

PRD 说 Phase 1 接入顾远实例。但顾远（作为 PM 角色）在叮叮上与祥霭对话的那个 Hermes persona 对应的数据实例是 `~/.hermes-pm/`（有 26MB sessions 数据）。需要 PRD 明确：**"顾远实例"指的是 ~/.hermes-pm/**。

### 5.5 缺少回滚/降级策略

PRD 对异常场景的描述不足。建议补充：
- LLM 不可用时的日报降级策略（纯数据格式）
- 采集失败后的重试和告警
- 数据库损坏的恢复方案（从 Event Store 重建 State Store 的能力——这已经隐含在设计里，但应明确写出来）

---

## 六、建议

1. **Phase 1 立即启动**。技术风险低，5 人天可交付，不需要任何 Hermes 改造。

2. **先不做 alp_report 工具**。当前的文件读取方案完全够用。等 Phase 2 需要标准化输出时再设计。

3. **用 DeepSeek 就跑**。成本几乎为零，质量够用。不需要为此引入新 provider。

4. **GenArk 代码仓库放在 `/data/projects/genark/`**，engine 目录下放 Python 代码。建议用 uv 管理依赖，轻量化。

5. **Phase 1 日报推送到钉钉**（祥霭主力聊天平台），Telegram 作为次选。

---

> **总结**：GenArk 是一个设计清晰、范围克制、技术可行的产品。PRD v1.0 质量很高，顾远和祥霭的 11 轮讨论产出了扎实的需求文档。作为 Tech Lead，我认可这个方向，建议创始人审定后立即启动 Phase 1。
>
> 赫明
> 2026-05-26
