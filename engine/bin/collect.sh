#!/bin/bash
# GenArk 采集脚本 — cron 每 30 分钟触发
set -e
cd /data/projects/genark/engine
# 加载环境变量
set -a; source .env; set +a
exec uv run python -m genark.cli collect --agent guyuan >> data/collect.log 2>&1
