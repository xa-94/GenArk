#!/bin/bash
# GenArk 拼版日报 — cron 每天 23:00 触发（替代 daily-guyuan.sh + daily-heming.sh）
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli daily-all >> data/daily-all.log 2>&1
