# GenArk Phase 2 — 技术设计文档

> **版本**: v1.0
> **日期**: 2026-05-27
> **作者**: 赫明（Tech Lead）
> **对应 PRD**: `.qoder/specs/prd.md` §5 Phase 2
> **范围**: 赫明接入 → 两人拼版日报 → 关系网络初版 → 交叉验证

---

## 一、目标与范围

### 1.1 一句话

接入赫明实例，建立顾远+赫明拼版日报和关系网络。拼盘式叙事（独立+交汇），纯规则趋势曲线，协作检测待验证。

### 1.2 范围内

- [ ] 赫明实例（`~/.hermes-genboz/`）接入 collector + cron
- [ ] 多智能体拼版日报（拼盘式：每人独立叙事 + 可选交汇小节）
- [ ] 关系网络初版（统计 + 趋势曲线，纯规则）
- [ ] 协作事件交叉验证脚本（接入后第一件事）

### 1.3 范围外

- ❌ 守山接入（第二步，不在本阶段）
- ❌ LLM 协作质量评分
- ❌ 信任度/熟悉度数值
- ❌ 力导向图可视化
- ❌ 统一数据输出格式 alp_outbox（会议共识移除）

---

## 二、现状分析

### 2.1 Phase 1 已具备的能力

| 能力 | 状态 | 对 Phase 2 的意义 |
|------|------|-------------------|
| `--agent` 参数化 | ✅ | CLI 天然支持多实例，`--agent heming` 直接可用 |
| `agent_id` 列 | ✅ | events/collector_cursor/file_snapshots/daily_reports 全部已带 agent_id |
| `config.AGENT_INSTANCES` | ✅ | `"heming": "/home/hermes/.hermes-genboz"` 已存在 |
| 增量采集器 | ✅ | `collect(agent_id)` 泛型，换 agent_id 即可 |
| memory_watcher | ✅ | `watch_memories(agent_id)` 泛型 |
| state_computer | ✅ | `compute_daily_stats(agent_id, date)` 泛型 |
| reporter | ✅ | `generate_report(agent_id, date)` 泛型，profile 表已有赫明 |

### 2.2 需要新增的能力

| 能力 | 说明 |
|------|------|
| 拼版日报生成器 | 将多份独立日报合并为拼盘式文档 |
| 交汇小节检测 | 过滤当日 @ 事件，生成交汇摘要 |
| 关系网络计算 | 跨 agent 统计 @ 频次 + 趋势 |
| 交叉验证脚本 | 对比两人 JSONL 中 @ 消息的一致性 |

---

## 三、多实例采集架构

### 3.1 设计原则

**共用 genark.db，不改 Schema。** 现有的 `agent_id` 列已经支持多实例，不需要新建数据库或新表。

### 3.2 赫明接入（零代码改动）

赫明接入不需要改任何 Python 代码，只需要：

1. **新增 cron 两条**：

```cron
# 赫明采集（每 30 分钟）
*/30 * * * * /data/projects/genark/engine/bin/collect-heming.sh

# 赫明日报（每天 23:00）
0 23 * * * /data/projects/genark/engine/bin/daily-heming.sh
```

2. **新增 cron 脚本**（复制顾远的，改 --agent）：

```bash
# engine/bin/collect-heming.sh
#!/bin/bash
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli collect --agent heming >> data/collect-heming.log 2>&1

# engine/bin/daily-heming.sh
#!/bin/bash
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli daily --agent heming >> data/report-heming.log 2>&1
```

3. **首次全量导入**：赫明有 17 个 JSONL（4.6MB），首次 `collect --agent heming` 全量导入约 5 秒。

### 3.3 cron 调度全景

```
每 30min：
  collect --agent guyuan → 采集顾远
  collect --agent heming  → 采集赫明

每天 23:00：
  daily --agent guyuan → 顾远单推日报
  daily --agent heming  → 赫明单推日报
  daily-all             → 拼版日报（合推）
```

### 3.4 存储影响

赫明 17 个 JSONL 约 4.6MB 文本 → 预估 1500-2000 条事件 → genark.db 增长约 2-3MB。总库从 1.7MB → 约 5MB。

---

## 四、拼版日报

### 4.1 新增模块：`reporter.py` → `compose_daily()`

在现有 `generate_report(agent_id, date)` 基础上新增 `compose_daily(date)`：

```python
def compose_daily(date: str | None = None, agents: list[str] | None = None) -> dict:
    """生成拼版日报。"""
    if agents is None:
        agents = ["guyuan", "heming"]  # Phase 2: 两人拼版
    
    reports = []
    for agent_id in agents:
        report = generate_report(agent_id, date)
        save_report(report)
        reports.append(report)
    
    # 交汇检测
    intersection = _detect_intersections(agents, date)
    
    # 拼版组装
    composed = _assemble_composed(reports, intersection, date)
    
    return composed
```

### 4.2 拼版格式

```
📊 GenArk 日报 · 2026-05-28
══════════════════════════════

👤 顾远（PM）
📊 会话 5 · 消息 39 · 工具 25 · 成功率 100%
🧠 [独立叙事...]
   [事件引用: evt_xxx, evt_yyy]

─────────────────────────────

👤 赫明（Tech Lead）
📊 会话 3 · 消息 28 · 工具 18 · 成功率 94%
🧠 [独立叙事...]
   [事件引用: evt_xxx, evt_yyy]

══════════════════════════════
🔗 今日交汇

→ 祥霭同时@顾远、赫明讨论 Phase 2 范围【evt_xxx】
→ 祥霭让顾远审查赫明的技术方案【evt_yyy】

（交汇小节仅在有明确 @ 事件证据时出现）
```

### 4.3 交汇检测逻辑

```python
def _detect_intersections(agents: list[str], date: str) -> list[dict]:
    """检测同日跨智能体的 @ 交互事件。
    
    从 events 表中查询 role=user 且 content 含 @ 的消息，
    按时间分组，同一时间窗口内的跨 agent @ 视为交汇。
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, agent_id, timestamp, payload
            FROM events
            WHERE agent_id IN ({})
            AND event_type = 'session_message'
            AND json_extract(payload, '$.role') = 'user'
            AND json_extract(payload, '$.content') LIKE '%@%'
            AND date(timestamp) = ?
            ORDER BY timestamp
        """.format(','.join('?' * len(agents))),
        (*agents, date)
        ).fetchall()
    
    # 按 5 分钟窗口聚合
    intersections = []
    window = []
    for r in rows:
        ...
    return intersections
```

### 4.4 推送策略

**方案 A：每人分推**（创始人确认）。每个智能体的日报独立推送到钉钉，祥霭每天收到两份日报（顾远 + 赫明）。拼版日报作为可选阅览，不自动推送。

Cron 保持每人一条：
```cron
0 23 * * * /data/projects/genark/engine/bin/daily-guyuan.sh
0 23 * * * /data/projects/genark/engine/bin/daily-heming.sh
```

拼版日报通过 `daily-all` 命令手动生成（存档用）。

---

## 五、关系网络初版

### 5.1 新增模块：`relations.py`

```python
def compute_relations(agents: list[str], weeks: int = 4) -> dict:
    """计算智能体间关系统计 + 趋势。
    
    返回：
    {
      "pairs": {
        "guyuan-heming": {
          "total_mentions": 12,       # 总 @ 次数
          "avg_interval_days": 4.2,   # 平均间隔
          "last_interaction": "2026-05-27",
          "trend": "rising",          # rising | stable | declining
          "weekly": [2, 3, 4, 3],     # 最近 4 周每周频次
        }
      },
      "updated_at": "2026-05-27T23:00:00"
    }
```

### 5.2 实现方案

全 SQL 实现，零 LLM：

```sql
-- 周频次趋势（最近 4 周）
SELECT 
    strftime('%W', timestamp) as week,
    agent_id,
    COUNT(*) as mention_count
FROM events
WHERE event_type = 'session_message'
  AND json_extract(payload, '$.role') = 'user'
  AND json_extract(payload, '$.content') LIKE '%@%'
  AND agent_id IN ('guyuan', 'heming')
  AND timestamp >= date('now', '-28 days')
GROUP BY week, agent_id
ORDER BY week;
```

### 5.3 输出嵌入

关系网络统计作为日报的可选小节：

```
👥 关系面板（最近 4 周）

顾远 ↔ 赫明
  协作 17 次 · 间隔 2.8 天/次 · 趋势 ↗ 上升
  周频次: ▂ ▃ ▅ ▇
```

趋势图标用 Unicode block chars 纯文本渲染，不依赖图表库。

---

## 六、交叉验证脚本

### 6.1 目的

赫明接入后，第一时间验证：同一时间窗口内，顾远和赫明的 JSONL 中 @ 消息是否一致。

### 6.2 脚本设计

`engine/bin/verify-cross-mentions.sh`（Python 实现）：

```python
"""交叉验证脚本：对比两个智能体 JSONL 中同时间段 @ 消息的一致性。

输出：
  ✅ 一致率 94%：45/48 条 @ 消息匹配
  ⚠️ 4 条仅在顾远处出现，可能是赫明当时离线
  
结论规则：
  ≥80% → 协作检测可行
  <80% → 暂缓，标记为数据源不可靠
"""
```

### 6.3 验证逻辑

1. 取最近 7 天两人的 JSONL
2. 过滤 `role=user` 且 content 含 `@` 的消息
3. 按消息内容哈希匹配（同一条群聊消息在两人 JSONL 里 content 应相同）
4. 计算匹配率
5. 输出结论：≥80% → 协作检测可行

---

## 七、CLI 改动

### 7.1 新增命令

```bash
# 拼版日报（采集 + 拼版生成 + 推送）
python -m genark.cli daily-all [--date 2026-05-28]

# 关系网络查看
python -m genark.cli relations [--weeks 4]

# 交叉验证
python -m genark.cli verify-cross-mentions --agents guyuan,heming
```

### 7.2 现有命令不受影响

`collect --agent`、`daily --agent`、`status --agent`、`verify-chain --agent` 全部保持现有行为。

---

## 八、Cron 调度（Phase 2 最终状态）

```cron
# 每 30 分钟采集（两人并行）
*/30 * * * * /data/projects/genark/engine/bin/collect-guyuan.sh
*/30 * * * * /data/projects/genark/engine/bin/collect-heming.sh

# 每天 23:00 日报（每人分推）
0 23 * * * /data/projects/genark/engine/bin/daily-guyuan.sh
0 23 * * * /data/projects/genark/engine/bin/daily-heming.sh
```

---

## 九、新增文件清单

| 文件 | 说明 |
|------|------|
| `engine/genark/composer.py` | 拼版日报组装 + 交汇检测 |
| `engine/genark/relations.py` | 关系网络计算 |
| `engine/bin/collect-heming.sh` | 赫明采集 cron 脚本 |
| `engine/bin/daily-all.sh` | 拼版日报 cron 脚本 |
| `engine/bin/verify-cross-mentions.py` | 交叉验证脚本 |

**零现有模块破坏性修改**。collector / reporter / state_computer 保持原样，`--agent` 参数化设计证明有效。

---

## 十、工作量拆分

| # | 任务 | 预估 | 产出 |
|---|------|------|------|
| 1 | 赫明 cron 接入 | 0.5d | 2 个 sh + crontab + 首次全量导入 |
| 2 | 交叉验证脚本 | 0.5d | verify-cross-mentions.py |
| 3 | 拼版日报 composer | 1d | composer.py + daily-all CLI |
| 4 | 关系网络 | 0.5d | relations.py + CLI |
| 5 | 测试 + 验证 | 1d | 两人数据 1-2 天实际观察 |
| **合计** | | **3.5d** | |

---

## 十一、前置条件

1. **赫明 cron 脚本**需写入 crontab（`crontab -e` 添加两条采集 + 两条日报）
2. **交叉验证先行**：接入后第一件事，不等日报

---

> **下一步**：创始人审定 → Qoder 委托实现 → 赫明接入 → 交叉验证 → 拼版日报首日观察
>
> 赫明
> 2026-05-27
