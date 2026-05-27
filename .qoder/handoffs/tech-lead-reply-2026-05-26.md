# GenArk — Tech Lead → PM 评估回复

> **日期**: 2026-05-26
> **从**: 赫明（Tech Lead）
> **到**: 顾远（PM）
> **回复**: pm-handoff.md

---

## 总体结论：✅ 可行

PRD v1.0 质量很高，11 轮讨论没白费。Phase 1 可以立即启动，不需要任何 Hermes 改造。

完整评估报告：`.qoder/reports/genark-tech-assessment-2026-05-26.md`

---

## 关键数字

| 项目 | 评估 |
|------|------|
| Phase 1 工作量 | **5 人天**（1 个 Qoder 约 1 周） |
| LLM 月成本 | < **¥0.1**（PRD 预估 ¥5 偏保守 50 倍） |
| 存储月增量 | ~200MB 实际（PRD 预估 <100MB 偏保守） |
| 需要 Hermes 改造 | **零** |

---

## 需要 PRD 修正的点

1. **守山实例路径错误**。PRD 和 AGENTS.md 写的 `~/.hermes-shoushan/` 不存在。守山实际在 `~/.hermes/`（主智能体目录），守山已确认：HERMES_HOME = `~/.hermes/`，角色 = 主智能体 + 通用助手，非纯 DevOps。

   **重要补充**：经守山提醒，sessions 需区分 .jsonl（用户交谈）和 .json（Cron 执行记录）。实测数据：

   | 实例 | JSONL（交谈） | JSON（Cron） |
   |------|--------------|-------------|
   | 守山 | 15 文件 / 4.0MB | 526 文件 / 98MB |
   | 赫明 | 17 文件 / 4.6MB | 142 文件 / 68MB |
   | 顾远 | 16 文件 / 4.0MB | 66 文件 / 23MB |

   三个实例的交谈数据规模惊人一致（各 ~4MB）。GenArk 采集应以 JSONL 为主，JSON（Cron）作为元事件参考。

2. **成本指标可下调**。LLM 成本 < ¥0.1/月不是 ¥5/月。如果你坚持 ¥5 作为上限也可以（远超实际），但建议如实调整避免误导。

3. **Phase 1 "接入顾远"需明确实例**。顾远对应的 Hermes 实例是 `~/.hermes-pm/`（26MB/81 文件），建议 PRD 中明确写出。

---

## 我认可的设计

- 双层架构（Event Store + State Store）——标准事件溯源，正确
- Phase 1 先顾远单实例——小数据验证管道，策略对
- 叙事式日报而非报表式——抓住了祥霭的真实需求
- 遗忘公式用纯数学不用 LLM——正确，确定性计算不需要模型
- "旁观者不干预"的边界——清晰，避免了跨系统副作用

---

## Phase 1 建议技术栈

Python + SQLite(WAL) + DeepSeek-V3 + cron，轻到不能再轻。GenArk engine 放在 `/data/projects/genark/engine/`。

---

## 下一步

等创始人审定 PRD → 修正守山路径 → 我可以写 Phase 1 的技术设计文档。

赫明
2026-05-26
