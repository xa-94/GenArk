"""query decisions — 最近决策"""

import json
import os


DECISION_LOG = os.path.expanduser("~/.hermes-team/decisions/decision-log.jsonl")


def cmd_query_decisions(args):
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    if not os.path.exists(DECISION_LOG):
        print("决策日志尚未初始化")
        return

    try:
        with open(DECISION_LOG) as f:
            lines = f.readlines()
    except Exception as e:
        print(f"读取失败：{e}")
        return

    # 取最后 20 条，倒序显示
    entries = []
    for line in lines[-20:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if not entries:
        print("决策日志为空")
        return

    print(c("1;36", "最近决策:"))
    print()
    for e in reversed(entries):
        ts = e.get("timestamp", "")[:10]
        decision = e.get("decision", "(无内容)")
        context = e.get("context", "")
        author = e.get("author", "")
        if author:
            print(f"  {ts} {author}: {decision}")
        else:
            suffix = f" ({context})" if context else ""
            print(f"  {ts} {decision}{suffix}")
