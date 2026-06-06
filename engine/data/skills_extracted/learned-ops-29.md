---
name: learned-ops-29
description: >
  GenArk 部署前检查：genark.db 磁盘余量≥100MB、DATA_DIR 剩余≥500MB、cron 脚本 PATH 含 ~/.local/bin、三人采集 cron 均在岗。验证命令：d
source: learnings #29
date: 2026-06-06 10:50:39
---

# Ops Pattern

GenArk 部署前检查：genark.db 磁盘余量≥100MB、DATA_DIR 剩余≥500MB、cron 脚本 PATH 含 ~/.local/bin、三人采集 cron 均在岗。验证命令：df -h <DATA_DIR> && crontab -l | grep genark && for agent in heming guyuan shoushan; do tail -3 engine/data/collect-$agent.log; done。
