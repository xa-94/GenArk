#!/usr/bin/env python3
"""GenArk Phase 4 — 自动 learnings 提取

用法: uv run python bin/extract-learnings.py [--date YYYY-MM-DD]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 加载 .env（cli.py 的 _load_env 只在 CLI 入口执行，提取脚本需要自己加载）
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

from datetime import datetime
from genark.extractor import extract_learnings

parser = argparse.ArgumentParser(description="自动从 Agent 会话事件提取 learnings")
parser.add_argument("--date", help="日期 (YYYY-MM-DD)，默认今天")
args = parser.parse_args()

date = args.date or datetime.now().strftime("%Y-%m-%d")
result = extract_learnings(date)
print(f"提取完成：{result['extracted']} 条新 learnings，过滤 {result['filtered']} 条")
