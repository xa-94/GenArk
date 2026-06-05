#!/bin/bash
# GenArk 采集脚本（守山）— cron 每 30min 触发
set -e
cd /data/projects/genark/engine
set -a; source .env; set +a
exec /home/hermes/.local/bin/uv run python -m genark.cli collect --agent shoushan >> data/collect-shoushan.log 2>&1
