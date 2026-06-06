#!/usr/bin/env python3
"""
validate-handoff.py — PM handoff YAML frontmatter 校验工具

用法:
    uv run python engine/bin/validate-handoff.py <handoff.md>

校验规则:
    1. 文件存在且可读
    2. YAML frontmatter 以 --- 起止
    3. 四必填字段: task_id / scope / data_sources / acceptance_criteria
    4. scope ∈ {add, change, remove}
    5. data_sources 为非空列表
    6. acceptance_criteria 为非空列表，每条以 AC 前缀开头

退出码:
    0 — 校验通过
    1 — 校验失败（含具体错误信息）

示例:
    uv run python engine/bin/validate-handoff.py .qoder/handoffs/pm-handoff-phase3-2026-06-06.md
"""

import sys
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ 缺少 PyYAML: pip install pyyaml")
    sys.exit(1)


VALID_SCOPES = {"add", "change", "remove"}


def extract_frontmatter(filepath: str) -> tuple[str | None, str]:
    """Extract YAML frontmatter and body from markdown file.

    Returns (yaml_string, body_string) or (None, error_message).
    """
    path = Path(filepath)
    if not path.exists():
        return None, f"文件不存在: {filepath}"
    if not path.is_file():
        return None, f"不是文件: {filepath}"

    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None, "缺少 YAML frontmatter（文件必须以 --- 开头）"

    # Find closing ---
    end = content.find("---", 3)
    if end == -1:
        return None, "YAML frontmatter 未闭合（缺少第二个 ---）"

    yaml_str = content[3:end].strip()
    body = content[end + 3 :].strip()

    if not yaml_str:
        return None, "YAML frontmatter 为空"

    return yaml_str, body


def validate_frontmatter(yaml_str: str) -> tuple[bool, list[str]]:
    """Validate the parsed YAML frontmatter.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError as e:
        return False, [f"YAML 解析失败: {e}"]

    if data is None:
        return False, ["YAML frontmatter 解析为空（可能只有注释）"]

    if not isinstance(data, dict):
        return False, ["YAML frontmatter 必须是字典（key: value）"]

    # 1. task_id
    if "task_id" not in data or not data["task_id"]:
        errors.append("缺少必填字段: task_id")
    elif not isinstance(data["task_id"], str):
        errors.append(f"task_id 必须是字符串，当前类型: {type(data['task_id']).__name__}")

    # 2. scope
    if "scope" not in data:
        errors.append("缺少必填字段: scope")
    else:
        scope = data["scope"]
        if scope not in VALID_SCOPES:
            errors.append(
                f"scope 无效: '{scope}'（必须为 {' / '.join(sorted(VALID_SCOPES))}）"
            )

    # 3. data_sources
    if "data_sources" not in data:
        errors.append("缺少必填字段: data_sources")
    else:
        sources = data["data_sources"]
        if not isinstance(sources, list) or len(sources) == 0:
            errors.append("data_sources 必须是非空列表")
        elif not all(isinstance(s, str) for s in sources):
            errors.append("data_sources 中所有元素必须是字符串")

    # 4. acceptance_criteria
    if "acceptance_criteria" not in data:
        errors.append("缺少必填字段: acceptance_criteria")
    else:
        ac = data["acceptance_criteria"]
        if not isinstance(ac, list) or len(ac) == 0:
            errors.append("acceptance_criteria 必须是非空列表")
        else:
            for i, item in enumerate(ac):
                # 兼容两种格式: 字符串 "AC1: xxx" 或 dict {"AC1": "xxx"}
                if isinstance(item, dict):
                    if len(item) != 1:
                        errors.append(
                            f"acceptance_criteria[{i}] dict 格式错误: 应含单一 AC<N> 键"
                        )
                    else:
                        key = list(item.keys())[0]
                        if not re.match(r"^AC\d+$", key):
                            errors.append(
                                f"acceptance_criteria[{i}] 键格式错误: '{key}' — 应为 AC<N>"
                            )
                elif isinstance(item, str):
                    if not re.match(r"^AC\d+:", item):
                        errors.append(
                            f"acceptance_criteria[{i}] 格式错误: '{item[:60]}...' — 应以 AC<N>: 开头"
                        )
                else:
                    errors.append(
                        f"acceptance_criteria[{i}] 类型错误: {type(item).__name__}（应为字符串或 dict）"
                    )

    return len(errors) == 0, errors


def main():
    if len(sys.argv) < 2:
        print("用法: validate-handoff.py <handoff.md>")
        print("示例: validate-handoff.py .qoder/handoffs/pm-handoff-phase3-2026-06-06.md")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"📄 校验: {filepath}")

    # Step 1: Extract frontmatter
    yaml_str, error = extract_frontmatter(filepath)
    if yaml_str is None:
        print(f"❌ {error}")
        sys.exit(1)

    print(f"   YAML frontmatter: {len(yaml_str)} 字符")

    # Step 2: Validate
    is_valid, errors = validate_frontmatter(yaml_str)

    if is_valid:
        data = yaml.safe_load(yaml_str)
        ac_count = len(data.get("acceptance_criteria", []))
        src_count = len(data.get("data_sources", []))
        print(f"✅ 校验通过")
        print(f"   task_id: {data['task_id']}")
        print(f"   scope: {data['scope']}")
        print(f"   data_sources: {src_count} 条")
        print(f"   acceptance_criteria: {ac_count} 条")
        sys.exit(0)
    else:
        print(f"❌ 校验失败 ({len(errors)} 个错误):")
        for err in errors:
            print(f"   - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
