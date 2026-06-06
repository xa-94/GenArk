#!/usr/bin/env python3
"""GenArk Phase 3 — B 类 learnings seed 脚本（守山）

幂等：按 content 去重，重复执行 0 新增。
source_type=correction, created_by=shoushan, status=pending.
"""
import sqlite3

DB_PATH = "/data/projects/genark/engine/data/genark.db"

learnings = [
    # === 看板协作（SOP v2.1）===
    ("correction", "看房子任务链的 --parent 指向前一个子任务（T2→T1），永远不挂总任务。总任务是独立仪表盘，blocked 状态会阻止一切子任务 claim", "kanban"),
    ("correction", "守山建 T1 后立即 kanban block，防止 dispatcher 误抓（协作任务不需要 worker，crash 2 次→blocked）", "kanban"),
    ("correction", "顾远 claim T1 前先 kanban unblock T1，再 claim。这是协作任务的标准起步动作", "kanban"),
    ("correction", "看板 comment 只写文档路径，不塞全文。文档全文留在 .qoder/ 或 ~/.hermes-team/handoffs/", "kanban"),
    ("correction", "看板是信息总线不是调度器。Agent 不会自动干活——每一步都是祥霭一句话启动会话", "kanban"),
    ("correction", "notify-subscribe 只推 terminal events（complete/block），不推 comment。订阅解决何时动，comment 解决去哪看", "kanban"),
    ("correction", "协作任务被 dispatcher 误抓是已知行为，不需要修。T1 链头 block 保护即可，T2-T6 有链式依赖保护", "kanban"),
    ("correction", "建链职责归守山——一次建 T1-T6 全链比顾远建出错率低。守山对 SOP 最熟", "kanban"),

    # === 群聊通信 ===
    ("correction", "三个 Agent 同 Telegram 群时，必须设 require_mention: true，否则一条消息三方抢答", "telegram"),
    ("correction", "搬家后需检查各实例的 gateway 配置完整性：.env 的 BOT_TOKEN 和 config.yaml 的 require_mention", "devops"),
    ("correction", "send_message list 只显示当前实例的平台连接，看不到其他 Agent 的 gateway 状态", "telegram"),

    # === 会议协议 ===
    ("correction", "会议文件 @ 令牌接力——file-based relay 是唯一通信媒介。群聊 @ 不能作为多 Agent 间的通信手段", "meeting"),
    ("correction", "会议 cron 间隔 120 秒给发言留余量，创建间隔 40s 天然错开三个 cron 首次触发", "meeting"),
    ("correction", "会议 cron 禁止调用 memory/skill_manage/cronjob/send_message，防污染长期记忆和递归创建 cron", "meeting"),

    # === 工程流程 ===
    ("correction", "PM handoff 四必填字段：task_id / scope / data_sources / acceptance_criteria。不足守山退回", "engineering"),
    ("correction", "Ops handoff 八项要素：变更概要/环境现状/待执行清单/验证命令/cron参考/回滚方案/注意事项/交接确认", "engineering"),
    ("correction", "前端铁律：API 路径用相对路径（/api/...），不用绝对路径。环境变量从 .env.test 读取", "engineering"),
    ("correction", "ngrok:80 统一入口用于跨机器测试，localhost 只在服务器本机有效，局域网其他电脑用 LAN IP", "engineering"),
    ("correction", "代码变更四步审计：问题/隐患/后续/留痕/文档。每次改完必须执行", "engineering"),

    # === Python 技术约束 ===
    ("correction", "Python 3.14 python3 -c 超时死锁→改用临时 .py 脚本执行。不要用 inline -c 跑复杂逻辑", "python"),
    ("correction", "数据统计必须查 SQLite 禁止凭记忆。sqlite3 CLI 不可用，用 Python sqlite3 模块操作", "python"),
    ("correction", "ImageMagick 可用但 rsvg-convert 不可用，SVG 渲染需另寻方案", "python"),

    # === 代理与网络 ===
    ("correction", "代理订阅解析需 CDN 去重——每域名只保留 1 节点，否则 13/18 节点同 CDN→全组瘫痪", "proxy"),
    ("correction", "DeepSeek/DingTalk 走 direct 直连（命脉服务），其余流量走 proxy。routing rules 在 sing-box 配置", "proxy"),
    ("correction", "sing-box 主 + v2ray 备。看门狗每 5min 检查：连续 2 次失败→切 v2ray，30min 冷却后→尝试恢复 sing-box", "proxy"),

    # === GenArk 采集 ===
    ("correction", "采集脚本路径变更后需同步更新 cron。赫明实例从 ~/.hermes-genboz 迁移到 ~/.hermes/profiles/heming 后 cron 要改", "genark"),
    ("correction", "collect-heming.sh 日志出现 0 条新事件→检查实例路径是否过期。搬家后采集中断是常见故障模式", "genark"),
    ("correction", "crontab -l | grep genark 确认采集 cron 条数（当前应为 3 条采集 + 1 条日报 + 1 条审核）", "genark"),

    # === GenArk learnings 体系 ===
    ("correction", "learnings 表不修改 events 表——三张新表是叠加层，不影响现有哈希链", "genark"),
    ("correction", "composer.py 的 _build_learnings_panel() 需做降级保护——learnings 表不存在时返回 None，不影响日报主流程", "genark"),
    ("correction", "seed 脚本必须幂等——按 content 去重，重复执行 0 新增。CREATE TABLE IF NOT EXISTS 也幂等", "genark"),
    ("correction", "B 类 learnings 入库规范：source_type=correction，created_by=shoushan，status=pending", "genark"),
    ("correction", "审核 cron 每天只输出 pending 列表到 review.log，不自动 approve。Phase 3 人工审核半开路", "genark"),
    ("correction", "Phase 4 自动写入 Agent Memory/Skill 的触发条件：learnings 连续 30 天 FP<5% + 去重准确率 >90% + 祥霭确认", "genark"),

    # === 知识图谱 ===
    ("correction", "知识图谱写入权限归图主——shoushan 空间归守山维护，其他 Agent 只读", "knowledge_graph"),
    ("correction", "八字周回顾 cron 跑通但静态 Skill 边际递减——周回顾+用户反馈回路才是真正有效的 Agent 优化方式", "knowledge_graph"),

    # === Hermes 基础设施 ===
    ("correction", "HERMES_KANBAN_DB 环境变量是最高优先级 DB 路径覆盖，设了就没有 board 隔离。团队协作只能用单 default board+前缀", "hermes"),
    ("correction", "Dashboard 需 gateway 后台 service 保活，会话重启后进程丢失。用 systemd user service 管理", "hermes"),
    ("correction", "Profile 迁移后需验证：config.yaml路径/skills目录/systemd服务 HERMES_HOME/gateway 平台连接", "hermes"),
    ("correction", "DECREE 优先级高于 Memory 中的流程约定。每会话加载 notices/README.md→读生效中的 DECREE", "hermes"),

    # === 团队协作 ===
    ("correction", "赫明守山直连走运维交接文档，祥霭不在中间传话。handoff→checklist→实现→验收→交接→部署，链式推进", "teamwork"),
    ("correction", "顾远审阅产品设计时先看 AGENTS.md 了解项目全貌，再看 handoff 了解当前迭代范围", "teamwork"),
    ("correction", "文件@令牌接力协议——顾远→赫明→守山循环。守山被@时做阶段总结推进议题，然后@下一轮首发人", "teamwork"),
    ("correction", "Agent 禁止跨角色操作：赫明不写 PRD/AGENTS.md，顾远不写业务代码，守山不写产品方向决策", "teamwork"),

    # === Memory 管理 ===
    ("correction", "Memory 接近上限（94%+）时优先合并旧条目而非新增。合并比删除更保留信息密度", "memory"),
    ("correction", "Memory 只存长期事实，不存任务进度/PR 号/commit SHA——这些一周内过时", "memory"),
    ("correction", "Memory 用声明式而非指令式语气——'用户偏好简洁'而非'始终简洁回复'，避免跨会话覆盖用户意图", "memory"),

    # === Git / 版本管理 ===
    ("correction", "代码修改前先 git stash 保存现场，改完验证后再 commit。避免半成品污染工作区", "git"),
    ("correction", "commit message 用中文描述为什么改而非改了什么——diff 已经告诉改了什么", "git"),

    # === 部署 ===
    ("correction", "测试环境部署前先核验 ops-handoff 八项完整性。缺任何一项退回赫明补", "devops"),
    ("correction", "部署后用交接单的验证命令逐项确认，不做猜测。cron 状态/哈希链/手动试跑日报", "devops"),

    # === 数据库 ===
    ("correction", "SQLite WAL 模式下读写不互斥但需注意：写事务期间读拿不到最新数据，高频采集场景用 IMMEDIATE 事务", "sqlite"),
    ("correction", "genark.db 单文件可被多脚本读但只有一个写者。采集 cron 错峰执行（两人采集间隔 1min 以上）", "sqlite"),

    # === 本迭代特有 ===
    ("correction", "Phase 3 迭代不走看板（没有建 T1-T6 链），用文件交接直接推进。看板适合标准化迭代，文件适合探索性阶段", "process"),
    ("correction", "decision-log.jsonl 格式：每行 JSON，字段 timestamp/decision/rationale/context。append-only，守山维护", "process"),
    ("correction", "B 类 learnings 持续产出机制：守山每次 T6 部署时自省本迭代，追加 5-10 条 correction→审核 cron 次日过", "process"),
]

conn = sqlite3.connect(DB_PATH)
new_count = 0
skip_count = 0

for source_type, content, category in learnings:
    # 幂等检查：按 content 去重
    exists = conn.execute(
        "SELECT COUNT(*) FROM learnings WHERE content=? AND created_by='shoushan'",
        (content,)
    ).fetchone()[0]
    if exists:
        skip_count += 1
        continue
    conn.execute(
        """INSERT INTO learnings (source_type, content, category, status, confidence, created_by)
           VALUES (?, ?, ?, 'pending', 0.85, 'shoushan')""",
        (source_type, content, category)
    )
    new_count += 1

conn.commit()
total = conn.execute("SELECT COUNT(*) FROM learnings WHERE created_by='shoushan'").fetchone()[0]
conn.close()

print(f"B 类 learnings: {new_count} 条新增 / {skip_count} 条已存在跳过 / 总计 {total} 条")
