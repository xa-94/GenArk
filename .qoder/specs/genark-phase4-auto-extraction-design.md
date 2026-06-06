# GenArk Phase 4 — 自动 Learnings 提取 · 产品设计

> **版本**: v1.0  
> **日期**: 2026-06-06  
> **作者**: 守山  
> **状态**: 设计阶段  

---

## §0 问题

现在 learnings 全靠手建：赫明写 A 类 bug_fix，守山每次 T6 部署后自省写 B 类 correction。181 条积累靠的是纪律，不是系统。

真正的问题是：**GenArk 每天采集 12,000+ 事件，但 learnings 管道只靠两个人手动喂。** 绝大多数踩坑永远烂在事件流里。

Phase 4 #1 要解决：让系统自己从事件流里识别 learnings。

## §1 范围

### 做什么

- 从 `events` 表的新增事件中，用 LLM 批量提取候选 learnings
- 候选 learnings 入库时 status=pending，走现有审核管道（review cron + review-screen）
- 每天一次，跟在日报拼版后面

### 不做什么

- 不自动 approve（审核管道不变）
- 不写回 Agent Memory/Skill（那是 #3）
- 不替代手建 learnings（LLM 提取 + 人工手建并行）
- 不改事件采集管线

## §2 流程

```
事件采集 cron（30min/次，不变）
    ↓
日报拼版 daily-all（23:00，不变）
    ↓
🆕 learnings 提取 cron（23:30）  ← 新增
    ↓
    ├─ 读 events 表当天新增事件
    ├─ LLM 批量提取 learnings
    ├─ 去重（对照现有 learnings）
    ├─ 入库（status=pending）
    └─ 审核 cron 次日 10:00 处理
```

## §3 LLM 提取策略

### 输入

当天 events 表中 event_type='session_message' 的事件，取 payload JSON 中的关键字段，压缩后喂给 LLM。

### Prompt 设计

```
你是 GenArk 的知识提取器。从以下 Agent 会话事件中识别值得记录的教训。

输出 JSON 数组，每条包含：
- source_type: bug_fix / correction / pattern
- content: 一句话描述（50-200字，有具体路径/命令/角色名）
- category: python/devops/genark/teamwork/...
- confidence: 0.0-1.0

规则：
- 只提取 具体可执行 的教训，不提取泛泛而谈
- 有错误码/路径/命令/工具名 → 优先提取
- 同一问题的多次出现 → 只提取一次
- 不超过 10 条
- 没有值得提取的内容 → 返回空数组
```

### 质量控制

| 门槛 | 规则 |
|------|------|
| 最小长度 | content < 30 字 → 丢弃 |
| 最低置信度 | confidence < 0.7 → 丢弃 |
| 去重 | 对照 learnings 表相似度 > 70% → 丢弃 |

## §4 实现

### 新增文件

```
engine/bin/extract-learnings.py     ← LLM 提取主脚本
engine/genark/extractor.py          ← 提取逻辑（事件读取/LLM调用/入库）
```

### 修改文件

```
无 — cron 配置属于运维层，部署时手动加
```

### 关键设计决策

- **LLM 调 DeepSeek**：复用 genark.db 的 GENARK_DEEPSEEK_API_KEY
- **批量处理**：一次 LLM 调用处理当天全部事件，不分 Agent 单独调
- **保守策略**：宁可漏 10 条，不产 1 条噪声
- **幂等**：按 content 前 200 字去重，重复执行 0 新增

### 技术约束

- 不改 events 表结构
- 不改现有 learnings 表 schema  
- 不引入新 Python 依赖（用 httpx 调 DeepSeek API，已在依赖中）
- 纯只读 events 表，只写 learnings 表
- 错误降级：LLM 调用失败 → 日志记录，不阻断日报

## §5 验收标准

- [ ] `uv run python bin/extract-learnings.py --date 2026-06-06` 跑通
- [ ] 产生的 learnings 全部 status=pending
- [ ] 置信度 < 0.7 的被过滤
- [ ] 已有 learnings 的相似内容被去重
- [ ] 空事件日（如顾远 0 事件）返回空
- [ ] LLM 调用失败不 traceback，只打日志

## §6 Cron 配置（部署时加）

```bash
# 每天 23:30，跟在日报拼版后
30 23 * * * cd /data/projects/genark/engine && /home/hermes/.local/bin/uv run python bin/extract-learnings.py >> data/extract.log 2>&1
```
