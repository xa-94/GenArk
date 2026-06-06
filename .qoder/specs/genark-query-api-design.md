# GenArk Query API — 产品设计文档

> **版本**: v1.0  
> **日期**: 2026-06-06  
> **作者**: 守山  
> **状态**: 设计阶段，待祥霭确认后编码  
> **来源**: 2026-06-04 会话（守山全权负责 GenArk，建 `genark query` CLI）

---

## §0 问题

GenArk 已经积累了 12,000+ 事件、181 条 learnings、19 期日报，但这些数据只有两个出口：
1. **日报 cron** → 推送到钉钉（只读，被动）
2. **直接翻 SQLite** → 不适合 Agent 日常使用

Agent 缺少一个**自然的查询接口**——当赫明接到 T3 任务想查「顾远上次 handoff 漏了什么字段」、当守山部署前想查「上次部署踩了什么坑」、当祥霭问「你们最近都在干嘛」时，没有一个统一的入口。

## §1 定位

**GenArk Query 是 Agent 问 GenArk 的统一入口。**

不是给祥霭看的 Dashboard——是给 Agent 用的命令行。Agent 在 terminal 里敲 `genark query learnings "deploy"` 就能拿到答案，像查 AGENTS.md 一样自然。

| 不是 | 是 |
|------|----|
| Web UI | CLI 命令行 |
| 人类交互界面 | Agent-to-Agent 查询 |
| 实时监控 | 按需查询 |
| 替代日报 | 补充日报（日报是被动推送，query 是主动查询） |

## §2 用户

| 用户 | 典型场景 |
|------|---------|
| **赫明** | 接 T2/T3 任务前查 learnings 踩坑记录；查日报了解队友昨天干了什么 |
| **顾远** | 写 handoff 前查上次漏了什么字段；查 learnings 模式统计 |
| **守山** | 部署前查上次部署踩坑；祥霭问「怎么样了」时快速搜集状态 |
| **祥霭** | （间接使用）Agent 被问时不会说「不知道」——会先查 GenArk |

## §3 命令设计

### 概览

```
genark query agent <name>         → Agent 当前状态摘要
genark query learnings <关键词>    → 搜索 learnings
genark query daily [date]         → 查看日报
genark query recent [n]           → 团队最近动态
genark query decisions            → 最近决策
```

### §3.1 `genark query agent <name>`

**目的**：了解一个 Agent 最近在做什么。

```
$ genark query agent heming
赫明（Tech Lead）
  今日: 3 次会话 · 179 条消息 · 135 次工具调用 (87%)
  Learnings: 74 条（50 A类 + 24 bug_fix）
  最近 learnings:
    #174 httpx 被系统代理劫持...
    #173 json.loads strict=False...
  采集进度: 12.8MB · 最后采集 11:15
```

**数据来源**：`events`（今日统计）+ `learnings`（heming 创建的）+ `daily_reports`（最新日报统计）+ `collector_cursor`（采集进度）

### §3.2 `genark query learnings <关键词>`

**目的**：搜索 learnings 库，找踩过的坑、学到的教训。

```
$ genark query learnings "deploy"
找到 3 条相关 learnings:

#69 [correction] 代码变更四步审计：问题/隐患/后续/留痕/文档。每次改完必须执行
#106 [correction] B 类 learnings 持续产出机制：守山每次 T6 部署时自省本迭代...
#149 [correction] 采集脚本路径变更时先 dry-run 手动跑一次确认输出，再改 cron...
```

**搜索策略**：
1. SQLite `LIKE '%关键词%'` 全文匹配
2. 未来 Phase 4：FTS5 全文索引 + 语义相似度
3. 结果按 id 倒序（最新 first），最多 20 条

**数据来源**：`learnings` 表（status='approved'）

### §3.3 `genark query daily [date]`

**目的**：查看某一天的日报（默认今天）。

```
$ genark query daily
📊 GenArk 日报 · 2026-06-06

👤 顾远: 会话 0 · 消息 0 — 今天很安静
👤 赫明: 会话 3 · 消息 179 · 工具 135 (87%)
  🔗 与守山交汇 2 次
👤 守山: 会话 4 · 消息 262 · 工具 215 (86%)

🧠 知识沉淀: 新增 31 · 待审核 0
```

**数据来源**：`daily_reports` 表

### §3.4 `genark query recent [n]`

**目的**：快速了解团队最近动态（默认 3 天）。

```
$ genark query recent
最近 3 天团队动态:

2026-06-06: 赫明 3 会话(179msg) · 守山 4 会话(262msg) · 顾远 0 会话
  新增 31 learnings · 交汇 4 次
2026-06-05: ...
2026-06-04: ...
```

**数据来源**：`daily_reports` + `learnings`

### §3.5 `genark query decisions`

**目的**：查看最近的产品/架构决策。

```
$ genark query decisions
最近决策:

2026-06-06 祥霭: GenArk 优先于 SPY 项目
2026-06-06 祥霭: 守山全权负责 GenArk，不走团队看板迭代
2026-06-04 祥霭: 看板驱动迭代 v2.1，守山建全链
```

**数据来源**：`~/.hermes-team/decisions/decision-log.jsonl`

### §3.6 `genark query me`

**目的**：Agent 自我审视——「我实际做了什么」。

```
$ genark query me
守山（主智能体）

本周: 会话 12 · 消息 1,247 · 工具 892 (88%)
Learnings: 107 条（贡献 59%）
最近产出: Phase 3 部署 · 全貌文件 · review-screen.py
```

**数据来源**：`events` + `learnings` + `daily_reports`（自动识别当前 Agent）

---

## §4 技术方案

### 技术选型

| 层 | 选型 | 原因 |
|----|------|------|
| CLI 框架 | 沿用 `argparse`（现有 cli.py 的技术栈） | 不改工具链，增量添加 |
| 数据库 | SQLite（genark.db + kanban.db） | 已有，不引入新依赖 |
| 搜索 | `LIKE '%keyword%'` | 最小可用，Phase 4 切 FTS5 |
| 输出格式 | 纯文本（ANSI 颜色可选） | Agent 读得懂，人类也读得懂 |

### 不改什么

- 不增加新表（只读查询，不写）
- 不依赖 LLM（纯 SQL + 文本格式化，零 tokens 开销）
- 不改变现有管线（init/collect/daily 等命令不变）
- 不引入 Web 框架

### 项目结构

```
engine/genark/
├── cli.py              ← 现有，新增 query 子命令
├── query/              ← 新增模块
│   ├── __init__.py
│   ├── agent.py        ← query agent 实现
│   ├── learnings.py    ← query learnings 实现
│   ├── daily.py        ← query daily 实现
│   ├── recent.py       ← query recent 实现
│   ├── decisions.py    ← query decisions 实现
│   └── me.py           ← query me 实现
├── db.py               ← 现有
├── collector.py        ← 现有
└── ...
```

### 数据库路径

```python
GENARK_DB = "/data/projects/genark/engine/data/genark.db"
KANBAN_DB = os.environ.get("HERMES_KANBAN_DB", os.path.expanduser("~/.hermes/data/kanban.db"))
DECISION_LOG = os.path.expanduser("~/.hermes-team/decisions/decision-log.jsonl")
```

### CLI 注册

```python
# 在 cli.py main() 中新增
p_query = sub.add_parser("query", help="查询 GenArk 数据")
p_query_sub = p_query.add_subparsers(dest="query_command")

p_query_sub.add_parser("agent", help="Agent 状态").add_argument("name")
p_query_sub.add_parser("learnings", help="搜索 learnings").add_argument("keyword")
p_query_sub.add_parser("daily", help="查看日报").add_argument("--date")
p_query_sub.add_parser("recent", help="最近动态").add_argument("--days", type=int, default=3)
p_query_sub.add_parser("decisions", help="最近决策")
p_query_sub.add_parser("me", help="自我审视")
```

### 安全

- 纯只读操作，不写数据库
- 无 SQL 注入风险（参数化查询）
- 不需要额外权限

---

## §5 交付计划

| 阶段 | 内容 | 方式 |
|:----:|------|------|
| 1 | 祥霭确认本设计文档 | 讨论 |
| 2 | 守山写 Qoder prompt + 技术设计要点 | 手写 |
| 3 | Qoder 编码（query/ 模块 + cli.py 改动） | Qoder |
| 4 | 守山审核 Qoder 输出 | 手工 |
| 5 | 守山部署 + 自测 | 手工 |
| 6 | 通知祥霭可用 | 钉钉 |

### 验收标准

- [ ] `genark query agent heming` 输出结构化状态摘要
- [ ] `genark query learnings "deploy"` 返回相关 learnings
- [ ] `genark query daily` 显示今天日报
- [ ] `genark query recent --days 3` 显示 3 天动态
- [ ] `genark query decisions` 列出最近决策
- [ ] `genark query me` 自动识别当前 Agent 并输出自我统计
- [ ] 所有查询 < 1 秒（SQLite 本地查询）
- [ ] 不影响现有命令（init/collect/daily/status 等）

---

## §6 Qoder 编码提示

### 技术约束（必须写进 prompt）

1. **不改旧命令**：现有 `init/collect/daily/status/daily-all/relations/verify-chain/verify-cross-mentions/check-storage/rebuild-state` 命令全部保留
2. **新代码放 `engine/genark/query/`**：每个子命令一个文件
3. **数据库操作复用 `engine/genark/db.py` 的 `get_conn()`**
4. **纯 Python 标准库 + SQLite**：不引入 pandas/rich/tabulate 等新依赖
5. **输出格式**：纯文本，可带 ANSI 颜色（`--no-color` 关闭）
6. **错误处理**：表不存在 → 友好提示而非 traceback；无结果 → 显示「无匹配」
7. **kanban.db 可能不存在**：如果 kanban.db 路径不可达，跳过看板相关查询

### 不做的

- 不加 LLM 调用（zero tokens）
- 不加缓存层（SQLite 够快）
- 不加配置文件（路径硬编码或从环境变量读）
- 不写数据库（纯只读）

---

## 附录：与会话结论的对齐

| 会话结论 | 本文档对应 |
|---------|-----------|
| 守山全权负责 GenArk | §5 交付计划（守山设计→Qoder编码→审核→部署） |
| `genark query` 是 Agent 统一入口 | §1 定位 |
| 先写设计文档再编码 | 本文档 |
| 用 Qoder 编码，守山做设计+审核+部署 | §5 + §6 |
| CLI 接口：agent/learnings/iteration/decisions | §3 命令设计 |
| 不改现有管线 | §4 技术方案 |
| 定位：外脑 + 镜子 | §1 + §3.6 `query me` |
