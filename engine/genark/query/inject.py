"""query inject — 读取待注入 learnings"""
import json, os


def cmd_query_inject(args):
    no_color = getattr(args, "no_color", False)

    def c(code, text):
        if no_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    # 自动识别 Agent
    hermes_home = os.environ.get("HERMES_HOME", "")
    if "heming" in hermes_home:
        agent_id = "heming"
    elif "guyuan" in hermes_home or "pm" in hermes_home:
        agent_id = "guyuan"
    else:
        agent_id = "shoushan"

    path = os.path.expanduser(f"~/.hermes/genark-injections/{agent_id}-pending.json")
    if not os.path.exists(path):
        print(f"{agent_id}: 没有待注入的 learnings")
        return

    with open(path) as f:
        data = json.load(f)

    items = data.get("items", [])
    if not items:
        print(f"{agent_id}: 没有待注入的 learnings")
        return

    print(c("1;33", f"\n⚠️  {len(items)} 条 learnings 等待注入你的 Memory：\n"))
    for item in items:
        content = item["content"][:100].replace("\n", " ")
        print(f"  #{item['id']} [{item['type']}] {content}...")

    print(c("1;36", f"\n用 memory 工具逐条保存。完成后: rm {path}"))
