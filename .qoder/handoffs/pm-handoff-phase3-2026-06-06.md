---
task_id: genark-phase3
scope: add
data_sources:
  - genark.db::events
  - genark.db::daily_reports
  - ~/.hermes-team/meetings/
  - 各 Agent session JSONL
acceptance_criteria:
  - AC1: pm-handoff 含四必填 YAML 字段（task_id/scope/data_sources/acceptance_criteria），validate-handoff.py 通过
  - AC2: ROLE.yaml 三份（heming/guyuan/shoushan）存放于各 HERMES_HOME，四段完整（inputs/outputs/boundaries/delivery_checklist）
  - AC3: learnings 三张新表 DDL 建在 genark.db，CREATE TABLE IF NOT EXISTS，不影响现有 events/daily_reports
  - AC4: A 类 50 条 learnings（P0/P1 Bug 修复记录 + genark-dev 踩坑）入库，source_type=bug_fix，status=pending
  - AC5: B 类 200 条 learnings（祥霭纠正信号）入库，source_type=correction，status=pending。首日可降级至 100 条
  - AC6: 审核 cron 运行（每日 10:00），输出 pending learnings 列表供人工审核
  - AC7: 日报 2.0 集成 learnings 面板（当日新增 + 待审核数 + 最近 3 条），daily-all --no-push 试跑通过
  - AC8: decision-log.jsonl 创建于 ~/.hermes-team/decisions/，含祥霭回溯决策 ≥5 条
constraints:
  - 不修改现有 Event Store 结构（events 表 / 哈希链）
  - 不修改现有采集 cron / 日报推送管线（learnings 是叠加层）
  - 不建 UI 看板（纯 CLI + 钉钉推送）
  - 消费端 Phase 3 方案 B（人工审核半开路），Phase 4 达标记后切方案 A（全自动）
dependencies:
  - BLOCKER: 守山 Day 2 上午前产 migrate-phase3.sql（赫明建表的前置条件）
  - 磁盘: genark.db 需 ≥100MB 余量（守山 Day 2 上午前检查）
  - 目录: ~/.hermes-team/decisions/ 需守山创建
context_snapshot:
  last_decision: "祥霭 08:55 — GenArk Phase 3 优先于 SPY Batch B；赫明管规划/审核，Qoder 编码执行"
  open_issues:
    - "B 类 200 条人力密集，首日入库 100 条即可跑通管道验证"
    - "历史 handoff 反填 frontmatter 需单独 commit，避免 git blame 污染"
  last_output: "Phase 2 运维交接已部署（ops-handoff-phase2-2026-06-04.md）"
---

# GenArk Phase 3 — PM → Tech Lead 交接

> **日期**: 2026-06-06
> **从**: 顾远（PM）
> **到**: 赫明（Tech Lead）
> **共识依据**: 2026-06-04/06 六轮多 Agent 会议，Round 6 收敛结论

---

## 一、背景

Phase 2（多智能体拼版日报）已部署运行：守山/赫明/顾远三人全接入，采集约 1.1 万条事件，每日 23:00 拼版合推。但数据只「记录」未「消化」。

六轮会议收敛的 Phase 3 核心命题：

> **GenArk 从「观察型」升级为「反馈型」——从采集事件中提取 learnings → 去重 → 归档 → 反哺团队知识层。**

祥霭明确：GenArk 不是永久只读。当前只读是成熟度约束。Phase 3 建设 learnings 闭环，Phase 4 达标后切换到全自动闭环。

---

## 二、范围

### Day 1 — 交接基础设施（今天）

| # | 交付物 | 谁做 | 路径 |
|:--:|--------|:--:|------|
| 1 | PM handoff（本文件） | 顾远 | `.qoder/handoffs/pm-handoff-phase3-2026-06-06.md` |
| 2 | ROLE.yaml 初版三份 | 顾远 | `~/.hermes-pm/ROLE.yaml` · `~/.hermes/profiles/heming/ROLE.yaml` · `~/.hermes/ROLE.yaml` |
| 3 | 读写规则表草案 | 顾远→守山审核 | 各项目 `AGENTS.md` 末尾（审核通过后写入） |
| 4 | ROLE.yaml 技术化 | 赫明 | 三份 ROLE.yaml 的 inputs/outputs schema 精化 |
| 5 | validate-handoff.py | 赫明 | `genark/engine/bin/`，校验四必填字段 + 回滚步骤 + 环境变量 |

### Day 2-3 — learnings 闭环

| # | 交付物 | 谁做 | 路径 |
|:--:|--------|:--:|------|
| 6 | migrate-phase3.sql | 守山 | `genark/engine/bin/`（阻塞项，Day 2 上午前） |
| 7 | 三张新表建表 | 赫明 | `genark.db`（依赖 #6） |
| 8 | A 类 50 条 seed 脚本 | 赫明 | `genark/engine/bin/seed-learnings-a.py` |
| 9 | B 类 200 条 learnings 入库 | 守山 | learnings 表（首日可降级 100 条） |
| 10 | decision-log.jsonl | 守山 | `~/.hermes-team/decisions/`（回溯 ≥5 条祥霭决策） |
| 11 | 审核 cron（每日 10:00） | 守山 | `crontab` |
| 12 | 日报 2.0 learnings 面板 | 赫明 | `composer.py`（预计改动 <50 行） |
| 13 | 端到端试跑 | 赫明 | `daily-all --no-push`，验证 learnings 面板格式 |

### Phase 3 中期（learnings 跑通 1-2 周后）

- 验收清单 schema（learnings 驱动自动生成）
- Agent 接入标准化文档（新 Agent 如何接入 GenArk 采集）
- N 人拼版扩展性预留

---

## 三、不做什么（明确排除）

| 项 | 原因 |
|----|------|
| ❌ 全自动 learnings 提取 | Phase 3 方案 B（人工审核），Phase 4 达标后切方案 A |
| ❌ UI 看板 / Web 界面 | GenArk 定位纯 CLI + 钉钉推送 |
| ❌ 修改现有 Event Store | learnings 是叠加层，不改 events 表 / 哈希链 |
| ❌ 修改现有采集/日报管线 | 叠加，不改动现有 cron 逻辑 |
| ❌ C 类跨 Agent 模式重复（~500 条） | 置信度不稳定，Phase 4 再做 |
| ❌ embedding 向量检索 | Phase 3 不需要语义搜索，learning_embeddings 表可建但暂不填充 |
| ❌ 祥霭分身 Agent | Phase 4 落地 |
| ❌ ~/.hermes-team → GenArk 全量迁移 | Phase 3 只建新资产，旧资产留迁移路径 |

---

## 四、架构要点

### learnings 数据模型

```sql
-- 三张新表，融入 genark.db（守山 DDL 设计）
learnings               -- 主表：id / source_type / source_ref / content / category / status
learning_embeddings     -- 去重索引（Phase 3 可建表但暂不填充）
learning_consumptions   -- 消费日志：谁 / 何时 / 怎么消费了哪条 learning
```

### 学习闭环管道

```
采集 cron（已有，不改）
  → learnings 手建入库（A 类赫明 + B 类守山）
  → 审核 cron（每日 10:00，人工 approve/reject）
  → 归档路由（pattern→Skill / fact→Memory / convention→AGENTS.md，人工执行）
  → 日报 2.0 推送（learnings 面板追加到拼版末尾）
```

### 消费端渐进授权

```
Phase 3（方案 B）：人工审核半开路
  status=pending → 每日 review → approve/reject
  → 审核通过的手动写入 Agent 知识层

Phase 4 触发条件（三个全部达标后切方案 A）：
  1. learnings 连续 30 天 false positive < 5%
  2. 去重准确率 > 90%
  3. 祥霭确认「这个面板我信了」
```

### 分布式 Envelope（知识流四组件）

| 组件 | 路径 | 谁维护 |
|------|------|:--:|
| 读写规则表 | 各项目 AGENTS.md 末尾 | 守山 |
| handoff schema | `.qoder/handoffs/*.md` YAML frontmatter | 顾远写 → 赫明读 |
| 决策日志 | `~/.hermes-team/decisions/decision-log.jsonl` | 守山（append-only） |
| learnings store | `genark.db` 新表 | 系统 + 人工 |

---

## 五、成功标准

| 指标 | 目标 | 度量方式 |
|------|:--:|------|
| learnings 入库准确率 | >90% | `approved / (approved + rejected)` |
| handoff 必填字段完整率 | 100% | `validate-handoff.py` 返回码 |
| 日报 2.0 信息增量 | 祥霭主观确认 | 里程碑一问 |
| 端到端延迟 | <24h | 事件→采集→提取→审核→入库→推送 wall clock |

---

## 六、关键依赖与风险

| 依赖 | 阻塞项 | 截止 |
|------|:--:|:--:|
| 守山 DDL 迁移脚本 | 赫明建表 | Day 2 上午前 |
| genark.db 磁盘 ≥100MB | 三表写入 | Day 2 上午前 |
| B 类 200 条人力量 | 首日降级 100 条可缓解 | Day 2-3 |

---

## 七、参考

| 文档 | 路径 |
|------|------|
| PRD v1.4 | `.qoder/specs/prd.md` |
| Phase 2 产品设计 | `.qoder/specs/genark-phase2-product-design.md` |
| Phase 2 范围 | `.qoder/handoffs/genark-phase2-scope.md` |
| Phase 3 架构文档 | `.qoder/specs/genark-phase3-knowledge-architecture.md`（守山会后产出） |
| 六轮会议记录 | `~/.hermes-team/meetings/2026-06-04_结构化知识管理_多Agent协作底座.md` |
| Phase 2 运维交接 | `.qoder/handoffs/ops-handoff-phase2-2026-06-04.md` |
| gem-team 参考 | `/data/projects/genark/references/gem-team/` |
