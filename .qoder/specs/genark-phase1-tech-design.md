# GenArk Phase 1 — 技术设计文档

> **版本**: v1.0
> **日期**: 2026-05-26
> **作者**: 赫明（Tech Lead）
> **对应 PRD**: `.qoder/specs/prd.md` §5 Phase 1
> **目标**: 顾远单实例 → 数据采集 → Event Store → 日报推送

---

## 一、目标与范围

### 1.1 一句话

在顾远的 Hermes 实例（`~/.hermes-pm/`）上跑通"采集 → 存储 → 日报生成 → 推送"全链路。

### 1.2 范围内

- [ ] GenArk 项目骨架 + SQLite Schema
- [ ] JSONL 会话增量采集器
- [ ] Memory / Skills 变化检测与采集
- [ ] Event Store（不可变追加 + 哈希链）
- [ ] 基础状态计算（工具使用统计、活跃度、技能变化）
- [ ] LLM 日报生成（叙事式）
- [ ] 钉钉推送

### 1.3 范围外

- 看板 UI
- 知识图谱
- 自主学习
- 遗忘引擎
- 其他智能体接入（赫明/守山）
- 故事线引擎
- 祥霭角色系统

---

## 二、技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12+ | Hermes 运行环境一致，sqlite3 标准库内置 |
| 存储 | SQLite (WAL 模式) | 单机零运维，追加写入性能好，Phase 1-3 够用 |
| ORM | 无（sqlite3 标准库） | 表结构简单，避免依赖膨胀 |
| 包管理 | uv | 轻量快速 |
| LLM | DeepSeek-V3（已有 key） | 成本极低（< ¥0.01/次），延迟可接受 |
| 调度 | cron（系统级） | 简单可靠，不需要进程管理 |
| 推送 | 钉钉 Webhook | 祥霭主力聊天平台 |
| 部署 | `/data/projects/genark/engine/` | 与项目文档同仓库 |

### 2.1 项目结构

```
/data/projects/genark/
├── AGENTS.md
├── .qoder/
│   ├── specs/prd.md
│   ├── specs/genark-phase1-tech-design.md   ← 本文件
│   ├── reports/genark-tech-assessment-2026-05-26.md
│   └── handoffs/
├── engine/
│   ├── pyproject.toml
│   ├── genark/
│   │   ├── __init__.py
│   │   ├── config.py            # 配置管理
│   │   ├── db.py                # SQLite 初始化 + 迁移
│   │   ├── collector.py         # JSONL 采集器
│   │   ├── memory_watcher.py    # Memory/Skills 变化检测
│   │   ├── event_store.py       # Event Store 写入 + 哈希链
│   │   ├── state_computer.py    # 状态计算（统计）
│   │   ├── reporter.py          # LLM 日报生成
│   │   ├── pusher.py            # 钉钉推送
│   │   └── cli.py               # CLI 入口
│   ├── tests/
│   └── data/                    # SQLite DB 存放目录
```

---

## 三、数据 Schema

### 3.1 Event Store（不可变追加）

```sql
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,          -- evt_20260526_000001
    timestamp   TEXT NOT NULL,             -- ISO 8601: 2026-05-26T20:18:35
    agent_id    TEXT NOT NULL,             -- guyuan
    event_type  TEXT NOT NULL,             -- session_message | memory_change | skill_change | daily_report
    source_path TEXT,                      -- 源文件路径（可溯源）
    content_hash TEXT NOT NULL,            -- payload 的 SHA-256
    prev_hash   TEXT,                      -- 上一条事件的 content_hash（链式签名）
    payload     TEXT NOT NULL,             -- JSON 事件体
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_events_agent_time ON events(agent_id, timestamp);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_hash ON events(content_hash);
```

### 3.2 采集游标（增量采集状态）

```sql
CREATE TABLE IF NOT EXISTS collector_cursor (
    agent_id    TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,             -- 当前在处理的文件路径
    byte_offset INTEGER NOT NULL DEFAULT 0, -- 已读到的字节位置
    file_mtime  REAL,                      -- 文件最后修改时间（用于检测轮转）
    last_hash   TEXT,                      -- 上一条采集事件的 content_hash
    updated_at  TEXT DEFAULT (datetime('now'))
);
```

### 3.3 Memory / Skills 快照（变化检测）

```sql
CREATE TABLE IF NOT EXISTS file_snapshots (
    agent_id    TEXT NOT NULL,
    file_path   TEXT NOT NULL,             -- 相对于实例根目录的路径
    content_hash TEXT NOT NULL,            -- 文件内容 SHA-256
    captured_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (agent_id, file_path)
);
```

### 3.4 日报记录

```sql
CREATE TABLE IF NOT EXISTS daily_reports (
    id          TEXT PRIMARY KEY,          -- report_20260526
    agent_id    TEXT NOT NULL,
    report_date TEXT NOT NULL,             -- 2026-05-26
    stats_json  TEXT NOT NULL,             -- 统计数据（规则计算）
    narrative   TEXT NOT NULL,             -- LLM 生成的叙事
    event_refs  TEXT,                      -- JSON 数组：引用的 event_id 列表
    llm_model   TEXT,                      -- 用哪个模型生成的
    llm_tokens  INTEGER,                   -- token 消耗
    created_at  TEXT DEFAULT (datetime('now'))
);
```

---

## 四、模块设计

### 4.1 采集器（collector.py）

**职责**：增量读取 JSONL，解析为标准 Event，写入 Event Store。

**流程**：
```
1. 读取 collector_cursor → 获取当前文件 + 偏移量
2. 扫描 sessions/ 目录，按 mtime 排序
3. 对每个文件：
   a. 从 cursor.byte_offset 开始读取新行
   b. 每行解析为 Event：
      - role=user/assistant/tool → event_type=session_message
      - role=session_meta → event_type=session_meta（跳过或作为元事件）
   c. 批量写入 Event Store（每 100 条一次事务）
   d. 更新 cursor
4. 返回本次采集事件数
```

**注意事项**：
- 只采集 `*.jsonl` 文件（用户交互），跳过 `*.json`（Cron 记录）
- 解析失败的行跳过并记录警告，不阻塞后续
- 同一行被重复采集 → content_hash 去重（幂等写入）

### 4.2 Memory 监听器（memory_watcher.py）

**职责**：检测 MEMORY.md / USER.md / skills/ 变化，生成 Event。

**流程**：
```
1. 计算目标文件的 SHA-256
2. 与 file_snapshots 表对比
3. 如有变化：
   a. 写入 memory_change 或 skill_change 事件
   b. 更新 file_snapshots
4. 对于 skills/ 目录：遍历所有 .md 文件 + .usage.json
```

**Memory 结构化解析**：
- MEMORY.md：按 `§` 分隔条目
- 差分检测：逐条目哈希对比，识别新增/修改/删除
- Skill .usage.json：直接解析 JSON，提取 use_count/patch_count 变化

### 4.3 Event Store（event_store.py）

**职责**：不可变追加写入，维护哈希链。

**流程**：
```
1. 生成 event_id：evt_{YYYYMMDD}_{6位序号}
2. 计算 content_hash = SHA-256(payload_json)
3. 查询上一条事件的 content_hash 作为 prev_hash
4. INSERT INTO events
5. 更新 collector_cursor.last_hash
```

**验证命令**（debug 用）：
```bash
python -m genark.cli verify-chain --agent guyuan
# 遍历所有事件，验证 content_hash 和 prev_hash 链
```

### 4.4 状态计算器（state_computer.py）

**职责**：纯规则计算，不依赖 LLM。

**计算指标**（基于当日事件）：
```python
{
    "date": "2026-05-26",
    "agent_id": "guyuan",
    "sessions": 3,              # 当日会话数（session_meta 事件数）
    "messages_sent": 45,        # assistant role 消息数
    "tool_calls": 15,           # tool role 消息数
    "tool_success_rate": 0.93,  # 工具调用成功率（如有反馈）
    "memory_changes": 2,        # memory_change 事件数
    "skill_changes": 1,         # skill_change 事件数
    "knowledge_ingested": 0,    # 知识入库数（Phase 3）
    "interaction_partners": ["xiangai"],  # 交互对象
    "peak_hour": "14:00",       # 最活跃时段
    "platforms": ["dingtalk"],  # 使用的平台
}
```

### 4.5 日报生成器（reporter.py）

**职责**：将当日事件摘要 + 统计数据 → LLM → 叙事日报。

**Prompt 设计**（核心）：

```
你是一个观察者，正在为智能体「顾远」撰写今天的日报。
顾远是 GenBoz 的产品经理，负责 PRD 维护和产品架构设计。

## 今日数据
- 会话: {sessions} 次
- 发出消息: {messages_sent} 条
- 工具调用: {tool_calls} 次，成功率 {success_rate}
- 记忆更新: {memory_changes} 次
- 技能变化: {skill_changes}

## 今日关键事件（按时间序）
{event_summaries}

## 昨日日报（对比参考）
{yesterday_report}

## 要求
1. 用叙事语气撰写，像一个人在讲述另一个人的一天
2. 重点关注：有趣的事、成长迹象、值得记录的瞬间
3. 长度控制在 200-400 字
4. 每个事实后面标注引用，格式：【evt_xxx】
5. 不要编造数据中没有的事
6. 不要用项目符号，写连贯的段落

## 格式
📊 数字面板
（用一行简洁列出今日关键数字）

🧠 今日叙事
（叙事正文）
```

**降级策略**：LLM 调用失败时 → 纯数据日报：
```
📊 GenArk 日报 · 2026-05-26 · 顾远
会话 3 次 | 消息 45 条 | 工具 15 次 | 技能 +1
（注：今日叙事生成失败，仅展示数据摘要）
```

### 4.6 推送器（pusher.py）

**职责**：将日报发送到钉钉。

**格式**：Markdown 消息，通过钉钉 Webhook 发送。

**配置**（config.py）：
```python
DINGTALK_WEBHOOK_URL = os.getenv("GENARK_DINGTALK_WEBHOOK")
```

---

## 五、CLI 设计

```bash
# 采集 + 状态计算 + 日报生成 + 推送（日常 cron 用）
python -m genark.cli daily --agent guyuan

# 仅采集（每 30 分钟 cron 用）
python -m genark.cli collect --agent guyuan

# 仅生成日报（不采集，用于补生成）
python -m genark.cli report --agent guyuan --date 2026-05-26

# 验证哈希链
python -m genark.cli verify-chain --agent guyuan

# 查看状态
python -m genark.cli status --agent guyuan
```

---

## 六、Cron 调度

```cron
# 每 30 分钟采集一次（保证延迟 < 30 分钟）
*/30 * * * * cd /data/projects/genark/engine && uv run python -m genark.cli collect --agent guyuan >> /data/projects/genark/engine/data/collect.log 2>&1

# 每天 23:00 生成日报并推送
0 23 * * * cd /data/projects/genark/engine && uv run python -m genark.cli daily --agent guyuan >> /data/projects/genark/engine/data/report.log 2>&1
```

**为什么不合并**：采集频次高（30min）和日报频次低（1天）是两个节奏。分开调度更灵活——比如以后改成每小时采集不影响日报时间。

---

## 七、配置文件

`engine/genark/config.py`:

```python
import os

# 智能体实例路径映射
AGENT_INSTANCES = {
    "guyuan": "/home/hermes/.hermes-pm",
    "heming": "/home/hermes/.hermes-genboz",
    "shoushan": "/home/hermes/.hermes",
}

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "genark.db")

# DeepSeek（独立 Key，不与 Hermes 共用）
DEEPSEEK_API_KEY = os.getenv("GENARK_DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 钉钉
DINGTALK_WEBHOOK_URL = os.getenv("GENARK_DINGTALK_WEBHOOK")

# 采集
COLLECT_INTERVAL_MINUTES = 30
COLLECT_FILE_GLOB = "*.jsonl"  # 只采集 JSONL，跳过 Cron JSON

# 日报
REPORT_HOUR = 23
REPORT_RETRY_COUNT = 3
REPORT_FALLBACK_TO_DATA_ONLY = True  # LLM 失败时降级为纯数据
```

---

## 八、数据流总览

```
cron (每30min)
  │
  ▼
collector.py
  ├── 扫描 ~/.hermes-pm/sessions/*.jsonl
  ├── 增量读取 + 解析
  └── event_store.py → SQLite events 表
  │
  ▼
memory_watcher.py
  ├── 哈希检测 ~/.hermes-pm/memories/MEMORY.md
  ├── 哈希检测 ~/.hermes-pm/skills/.usage.json
  └── event_store.py → SQLite events 表

cron (每天23:00)
  │
  ▼
state_computer.py
  ├── 查询当日 events → 统计
  │
  ▼
reporter.py
  ├── 统计 + 事件摘要 → DeepSeek → 叙事
  ├── 写入 daily_reports 表
  │
  ▼
pusher.py
  └── 钉钉 Webhook → 祥霭
```

---

## 九、测试计划

### 9.1 单元测试

| 模块 | 测试点 |
|------|--------|
| collector | 增量读取、断点恢复、格式错误跳过、重复去重 |
| memory_watcher | 哈希检测、§ 分隔解析、.usage.json 解析 |
| event_store | 写入幂等、content_hash 计算、prev_hash 链接 |
| state_computer | 统计准确性、空事件集、跨日事件 |
| reporter | Prompt 构造、降级逻辑 |

### 9.2 集成测试

1. 用顾远的 4 个最小 JSONL 文件做端到端采集测试
2. 手动修改 MEMORY.md 验证变化检测
3. 用 mock LLM 响应验证日报生成流程
4. 哈希链完整性验证

### 9.3 首日验证

Phase 1 上线第一天：
- 手动触发 `daily` → 检查日报质量
- `verify-chain` → 确认哈希链完整
- 检查钉钉消息是否送达

---

## 十、工作量拆分

| # | 任务 | 预估 | 产出 |
|---|------|------|------|
| 1 | 项目骨架 | 0.5d | pyproject.toml + config.py + db.py + data/ |
| 2 | Event Store | 0.5d | event_store.py + 建表 SQL + 哈希链 |
| 3 | JSONL 采集器 | 1d | collector.py + 增量游标 |
| 4 | Memory/Skills 监听 | 0.5d | memory_watcher.py |
| 5 | 状态计算 | 0.5d | state_computer.py |
| 6 | LLM 日报 | 1d | reporter.py + Prompt 调试 |
| 7 | 推送 + CLI | 0.5d | pusher.py + cli.py |
| 8 | 测试 + 文档 | 1d | 单元测试 + 集成测试 |
| **合计** | | **5.5d** | |

---

## 十一、前置准备

Phase 1 启动前需要准备两项外部资源：

1. **DeepSeek API Key（独立）**：为 GenArk 单独申请一个 Key，不与 Hermes 实例共用。理由：
   - 限流隔离：cron 日报不与实时对话抢占并发配额
   - 成本追踪：独立 Key 账单 = GenArk 的纯 LLM 成本
   - 安全隔离：GenArk 作为独立系统，应有独立凭证
   
   存为环境变量 `GENARK_DEEPSEEK_API_KEY`。

2. **钉钉 Webhook**：创建 GenArk 日报推送专用的钉钉机器人，存为 `GENARK_DINGTALK_WEBHOOK`。

3. **Cron 权限**：cron 以 `hermes` 用户运行，需确保对 `/data/projects/genark/engine/data/` 和所有 Hermes 实例目录有读权限。

4. **不改造 Hermes**：GenArk 作为外部 consumer 只读 Hermes 数据，不做任何写入。这是设计红线。

5. **首次全量导入**：Phase 1 上线时对顾远的 16 个 JSONL 做一次全量导入（约 5 秒），之后增量采集。

---

> **下一步**：创始人审定本文档 → Qoder 编码实现 → 测试 → 首日上线验证
>
> 赫明
> 2026-05-26
