#!/bin/bash
# GenArk 日报脚本（赫明）— cron 每天 23:00 触发
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli daily --agent heming >> data/report-heming.log 2>&1
