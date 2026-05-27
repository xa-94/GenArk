#!/bin/bash
# GenArk 采集脚本（赫明）— cron 每 30 分钟触发
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli collect --agent heming >> data/collect-heming.log 2>&1
