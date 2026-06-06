---
name: learned-architecture-31
description: >
  GenArk 降级策略 7/7 全覆盖：LLM API 断连→纯数据降级、JSONL 采集失败→跳过不阻塞、DB 写入失败→事务回滚、哈希不匹配→integrity_warning、JSONL 格式变
source: learnings #31
date: 2026-06-06 10:50:39
---

# Architecture Pattern

GenArk 降级策略 7/7 全覆盖：LLM API 断连→纯数据降级、JSONL 采集失败→跳过不阻塞、DB 写入失败→事务回滚、哈希不匹配→integrity_warning、JSONL 格式变化→schema 版本检查、数据库损坏→rebuild_state_store()、存储不足→告警+暂停。
