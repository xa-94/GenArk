#!/bin/bash
# GenArk 日报脚本 — cron 每天 23:00 触发
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec uv run python -m genark.cli daily --agent guyuan >> data/report.log 2>&1
