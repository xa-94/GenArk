# 团队知识层读写规则表（草案）

> 来源: 2026-06-06 六轮会议 Round 4 结论
> 状态: 顾远草案 → 待守山审核 → 审核通过后写入各项目 AGENTS.md 末尾
> 定位: 分布式 Envelope 的"权限层"——谁往哪写、谁能读、什么条件下可以改

---

## 知识层所有权矩阵

| 层 | 写权限 | 读权限 | 增改规则 |
|----|:------:|:------:|------|
| **PRD** | 顾远 | 全员 | 顾远维护，祥霭确认后生效 |
| **AGENTS.md** | 守山 | 全员 | 守山唯一写入，他人通过看板 comment 提议 |
| **INFRA.md** | 守山 | 全员 | 守山唯一维护 |
| **Memory** | 各 Agent 自写 | 本 Agent + GenArk 采集只读 | 各 Agent 主观记录，不互写 |
| **Skill** | 各 Agent 自建/自改 | 本 Agent + GenArk 采集只读 | 踩坑后自行补，他人可提议 |
| **ROLE.yaml** | 顾远（初版）→ 守山（更新） | 全员 + GenArk 采集 | 提议→顾远审核→祥霭确认→守山更新 |
| **handoff** | 顾远（PM→TL）/ 赫明（TL→Ops） | 全员 | YAML frontmatter 四必填字段 |
| **看板** | 全员（各自 claim/comment/complete） | 全员 | 状态机约束，不跨角色 |
| **决策日志** | 守山 | 全员 | 守山维护，append-only |
| **learnings** | 系统 + 人工（A类:赫明 / B类:守山） | 审核者 + 日报 | status=pending→approved/rejected |

---

## 禁止写入清单

| 谁 | 禁止写 |
|:--:|------|
| 赫明 | PRD、AGENTS.md、INFRA.md、其他 Agent 的 Memory/Skill、PM handoff |
| 顾远 | 业务代码、AGENTS.md/INFRA.md、运维配置 |
| 守山 | 业务代码、PRD、产品方向决策 |

---

## GenArk 采集引擎读写规则

| 操作 | Phase 2-3 | Phase 4（达标后） |
|------|:---:|:---:|
| 采集会话 JSONL | ✅ 只读 | ✅ 只读 |
| 采集 Memory/Skill 变更 | ✅ 只读 | ✅ 只读 |
| 写入 Agent Memory | ❌ | ✅（learnings→approved→自动写入） |
| 写入 Agent Skill | ❌ | ✅（pattern→Skill 自动创建） |
| 写入 AGENTS.md | ❌ | ❌（永久人工，守山维护） |

> **Phase 4 触发条件**：learnings 连续 30 天 FP<5% + 去重准确率 >90% + 祥霭确认信任

---

## 规则生效流程

1. 顾远出草案（本文件）
2. 守山逐项审核，标注"同意/修改建议/驳回"
3. 修改后由顾远确认
4. 祥霭确认终版
5. 守山写入各项目 AGENTS.md 末尾
