# GenArk — 智能体生命平台 · 开发指南

> **产品代号**: GenArk（生成方舟）
> **版本**: v1.5.0
> **创建日期**: 2026-05-26
> **当前阶段**: Phase 4b — 因果关系链已上线

---

## 项目概述

GenArk 是一个智能体世界的观察与成长系统。它记录多个 AI 智能体的完整生命轨迹，向创始人祥霭提供叙事化的日报与故事线，并赋予智能体自我认知与自主学习的能力。

## 角色定义

| 角色 | 实例 | 名称 | 职责 |
|------|------|------|------|
| 创始人 | 人类 | **黄祥霭** | 所有产品决策，唯一决策者 |
| 产品经理 | 本实例 | **顾远** | PRD 维护、产品架构设计 |
| Tech Lead | `~/.hermes/profiles/heming` | **赫明** | 技术架构、代码实现 |
| 主智能体 | `~/.hermes/` | **守山** | 主智能体 + 通用助手，GenArk 三方信息枢纽 |
| 祥霭分身 | `~/.hermes/profiles/xiangai` | **祥霭分身** | 祥霭的 AI 操作代理人，接入 GenArk 采集管道的第四个 Agent |

## 真相源

```
.qoder/
├── specs/
│   ├── prd.md                        ← 产品需求真相源（当前 v1.4）
│   ├── genark-phase3-knowledge-architecture.md  ← Phase 3 知识层架构
│   └── genark-query-api-design.md    ← Query CLI 产品设计
├── reports/                          ← Tech Lead → PM 审计报告
├── decisions/                        ← 产品战略决策
└── handoffs/                         ← PM → Tech Lead 交接文件
```

## 当前状态

**阶段**: Phase 4b — 因果关系链
- Phase 2 稳定运行：采集 cron ×4（含祥霭分身） + 拼版日报 cron ×1
- Phase 3 知识层：187 条 learnings 全量审核归档，FTS5 全文索引，自动提取（cron 23:30），自动归档（cron 10:30）
- Phase 4b 因果链：`learning_relations` 表 + `genark query relations` CLI + 日报关联面板
- 种子数据：19 条关系（7 因果 + 4 泛化 + 8 同根），含跨 Agent 关联
- `genark query` CLI：8 个子命令（agent/learnings/daily/recent/decisions/me/inject/relations）

**Next**: 自动关联建议（FTS5 相似度 → 建议 related_to → 人工确认）。等因果链面板运行几天后评估。

## 核心文档

| 文档 | 路径 | 用途 |
|------|------|------|
| PRD | `.qoder/specs/prd.md` | 产品需求真相源（v1.4） |
| Phase 2 运维交接 | `.qoder/handoffs/ops-handoff-phase2-2026-06-04.md` | 赫明 → 守山 部署交接 |
| Phase 3 PM handoff | `.qoder/handoffs/pm-handoff-phase3-2026-06-06.md` | 顾远 → 赫明 知识层架构 |
| Phase 3 技术评估 | `.qoder/reports/genark-phase3-tech-assessment-2026-06-06.md` | 赫明技术评估报告 |
| Phase 3 架构文档 | `.qoder/specs/genark-phase3-knowledge-architecture.md` | 知识层架构全貌 |
| Phase 3 DDL | `engine/bin/migrate-phase3.sql` | learnings 三表建表脚本 |
| 读写规则草案 | `.qoder/specs/read-write-rules-draft.md` | 会议产出，全文见下方 |
| Query API 设计 | `.qoder/specs/genark-query-api-design.md` | `genark query` CLI 产品设计 |

## Key Rules

1. GenArk 是"旁观者"——观察 Hermes 智能体但不干预它们运行
2. PRD 是唯一真相源，先更新 PRD 再做任何事
3. PM 定义 WHAT，Tech Lead 定义 HOW
4. 先汇报计划 → 等创始人确认 → 再执行

---

## 知识层读写规则

> 来源: 2026-06-06 六轮会议 Round 4 结论
> 定位: 分布式 Envelope 的权限层——谁往哪写、谁能读、什么条件下可以改

### 所有权矩阵

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

### 禁止写入清单

| 谁 | 禁止写 |
|:--:|------|
| 赫明 | PRD、AGENTS.md、INFRA.md、其他 Agent 的 Memory/Skill、PM handoff |
| 顾远 | 业务代码、AGENTS.md/INFRA.md、运维配置 |
| 守山 | 业务代码（GenArk 除外）、PRD、产品方向决策 |
| 守山（GenArk） | PRD、产品方向决策 |

### GenArk 采集引擎读写规则

| 操作 | Phase 2-3 | Phase 4（达标后） |
|------|:---:|:---:|
| 采集会话 JSONL | ✅ 只读 | ✅ 只读 |
| 采集 Memory/Skill 变更 | ✅ 只读 | ✅ 只读 |
| 写入 Agent Memory | ❌ | ✅（learnings→approved→自动写入） |
| 写入 Agent Skill | ❌ | ✅（pattern→Skill 自动创建） |
| 写入 AGENTS.md | ❌ | ❌（永久人工，守山维护） |

> **Phase 4 触发条件**：learnings 连续 30 天 FP<5% + 去重准确率 >90% + 祥霭确认信任
