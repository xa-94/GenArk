# GenArk — 智能体生命平台 · 开发指南

> **产品代号**: GenArk（生成方舟）
> **版本**: v1.1.0
> **创建日期**: 2026-05-26
> **当前阶段**: Phase 2 运行中 — 多智能体拼版日报已上线

---

## 项目概述

GenArk 是一个智能体世界的观察与成长系统。它记录多个 AI 智能体的完整生命轨迹，向创始人祥霭提供叙事化的日报与故事线，并赋予智能体自我认知与自主学习的能力。

## 角色定义

| 角色 | 实例 | 名称 | 职责 |
|------|------|------|------|
| 创始人 | 人类 | **黄祥霭** | 所有产品决策，唯一决策者 |
| 产品经理 | 本实例 | **顾远** | PRD 维护、产品架构设计 |
| Tech Lead | `~/.hermes/profiles/heming` | **赫明** | 技术架构、代码实现 |
| 主智能体 | `~/.hermes/` | **守山** | 主智能体 + 通用助手，祥霭最核心的伙伴 |

## 真相源

```
.qoder/
├── specs/
│   └── prd.md                        ← 产品需求真相源（当前 v1.1）
├── reports/                          ← Tech Lead → PM 审计报告
├── decisions/                        ← 产品战略决策
└── handoffs/                         ← PM → Tech Lead 交接文件
```

## 当前状态

**阶段**: Phase 2 运行中 ✅
- 采集 cron：2 条（顾远 + 赫明，每 30min）
- 日报 cron：1 条（拼版合推，23:00）
- 哈希链：heming 5955 条 / guyuan 2642 条，完整
- 关系网络 + 协作检测 + 推送策略均已集成

**Next**: Phase 3 待定

## 核心文档

| 文档 | 路径 | 用途 |
|------|------|------|
| PRD | `.qoder/specs/prd.md` | 产品需求真相源（v1.4） |
| Phase 2 产品设计 | `.qoder/specs/genark-phase2-product-design.md` | 多智能体全景视图设计 |
| Phase 2 范围 | `.qoder/handoffs/genark-phase2-scope.md` | 2026-05-27 范围对齐产出 |
| Phase 2 运维交接 | `.qoder/handoffs/ops-handoff-phase2-2026-06-04.md` | 赫明 → 守山 部署交接 |
| Phase 1 技术设计 | `.qoder/specs/genark-phase1-tech-design.md` | Phase 1 技术方案 |

## Key Rules

1. GenArk 是"旁观者"——观察 Hermes 智能体但不干预它们运行
2. PRD 是唯一真相源，先更新 PRD 再做任何事
3. PM 定义 WHAT，Tech Lead 定义 HOW
4. 先汇报计划 → 等创始人确认 → 再执行
