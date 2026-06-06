---
name: learned-reporter-28
description: >
  日报调试用 daily-all --no-push 先看输出再推送。不要直接 daily-all 推钉钉——可能把调试信息发给群聊。验证流程：collect→daily-all --no-push→确
source: learnings #28
date: 2026-06-06 10:50:39
---

# Reporter Pattern

日报调试用 daily-all --no-push 先看输出再推送。不要直接 daily-all 推钉钉——可能把调试信息发给群聊。验证流程：collect→daily-all --no-push→确认无误→daily-all（正式推送）。
