# GenArk Phase 2 启动 · 多智能体拼版日报

## 项目信息

- **项目根目录**：`/data/projects/genark/`
- **当前阶段**：Phase 1 稳定运行 → Phase 2 启动

## 赫明阅读顺序（按优先级）

1. `/data/projects/genark/AGENTS.md` — 项目概览 + 角色定义
2. `/data/projects/genark/.qoder/specs/genark-phase2-product-design.md` — Phase 2 产品设计（刚产出，需要技术评估）
3. `/data/projects/genark/.qoder/handoffs/genark-phase2-scope.md` — 5/27 范围对齐（参考）
4. `/data/projects/genark/.qoder/specs/prd.md` — 完整 PRD（背景参考，Phase 2 只看 §5）

## 现状

已有代码：`engine/` 目录（Python + SQLite + DeepSeek），当前只跑了顾远单实例采集+日报。

## Phase 2 目标

- 多实例采集（接赫明实例 `~/.hermes-genboz/`）
- 三人拼版日报（纯数据面板，零 LLM）
- 关系网络统计 + 协作事件检测
- 推送策略：日常拼版合推 + 重大事件单推

## 第一步

赫明审阅产品设计 → 技术评估 → 技术设计文档
