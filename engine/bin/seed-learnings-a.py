#!/usr/bin/env python3
"""
seed-learnings-a.py — A 类 learnings 手建入库（结构化错误 + P0/P1 Bug 修复）

用法:
    uv run python engine/bin/seed-learnings-a.py

来源:
    - genark-dev skill 踩坑实录（Bug 修复章节）
    - Phase 1-2 已验证的工程教训
    - 2026-06-06 越权事故（团队协作边界）

幂等: 重复执行检测 source_ref 去重，不重复插入
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "genark.db"

# A 类 learnings: source_type=bug_fix，50 条
LEARNINGS = [
    # === 工具成功率统计口径 (v1.0.1) ===
    {
        "source_type": "bug_fix",
        "content": "工具成功率统计不能用子字符串匹配 error/fail。terminal 输出（git log、ls、配置文件）碰巧含 error 即误判。用 _is_tool_failure() 结构化判定：json.loads → check success/exit_code。效果：68%→100%。",
        "category": "state_computer",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "_is_tool_failure 中 'error' in data 会误判 'error': null 为失败。'key' in dict 检查 key 存在性而非 value 真值。改用 data.get('error') 做 Python 真值判定（None/空串/0=False）。赫明案例：69%→90%。",
        "category": "state_computer",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "结构化判定场景永远用 dict.get('key') 而不是 'key' in dict。前者检查 value 真值，后者只检查 key 存在性。JSON null 值在 Python 中是 None，'error': null 不应算失败。",
        "category": "python_pattern",
        "confidence": 0.90,
    },
    # === Cron uv: not found ===
    {
        "source_type": "bug_fix",
        "content": "cron 默认 PATH 不含 ~/.local/bin，导致 uv 命令 not found。cron 脚本必须用绝对路径 /home/hermes/.local/bin/uv 或在脚本首行 export PATH。验证方法：tail -5 collect.log 确认不再报错。",
        "category": "cron",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "cron 静默失败是最危险的 bug——脚本返回 0 但不产出数据。排查公式：① crontab -l | grep <project> 确认在岗 ② tail -20 collect.log 看最后几条 ③ SELECT MAX(timestamp) FROM events 看最后事件时间。",
        "category": "cron",
        "confidence": 0.90,
    },
    # === memory/skill 事件时间戳 ===
    {
        "source_type": "bug_fix",
        "content": "memory_watcher 的 append_event 不传 timestamp 时默认 datetime.now()（采集运行时刻），而 compute_daily_stats(date) 按 date(timestamp) 筛选——跨天采集时事件落入错误日期分区，日报漏计。修复：显式传 timestamp=datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()。",
        "category": "memory_watcher",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "memory/skill 变化检测的两层根因：① cron 坏了导致采集根本不跑 snapshot 无法对比 ② append_event 时间戳用了采集时刻而非文件 mtime。排查时先确认 cron 在岗，再查时间戳。",
        "category": "memory_watcher",
        "confidence": 0.85,
    },
    # === event_id 碰撞 ===
    {
        "source_type": "bug_fix",
        "content": "多实例 event_id 碰撞：_next_event_id() 的 SQL 加了 WHERE agent_id=? 导致每个 agent 从 seq=1 开始，但 events.id 是全局 PRIMARY KEY。修复：去掉 WHERE 过滤，使用全局序列。event 已有 agent_id 列区分归属，id 只需全局唯一。",
        "category": "event_store",
        "confidence": 0.95,
    },
    # === 多 Agent report_id 碰撞 ===
    {
        "source_type": "bug_fix",
        "content": "多 Agent 同日 report_id 碰撞：report_id=f'report_{date}' 只用日期不用 agent_id，daily-all 生成多人日报后 INSERT OR REPLACE 覆盖。修复：改为 report_id=f'report_{agent_id}_{date}'。",
        "category": "reporter",
        "confidence": 0.95,
    },
    # === httpx 代理劫持 ===
    {
        "source_type": "bug_fix",
        "content": "httpx 被系统 HTTP_PROXY/HTTPS_PROXY 环境变量劫持，指向 sing-box SOCKS5 :1080 导致 socksio not installed 错误。即使传 proxy=None 也不行——httpx 优先读环境变量。解法：创建 Client 前临时 strip 代理环境变量，或直接用 curl。",
        "category": "http_client",
        "confidence": 0.95,
    },
    {
        "source_type": "pattern",
        "content": "Python HTTP 调用封装模式：创建 httpx.Client 前 pop HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/all_proxy/ALL_PROXY 六个环境变量。已封装在 genark/engine/genark/http_client.py 的 _http_client() 中，所有 HTTP 调用用它。",
        "category": "http_client",
        "confidence": 0.90,
    },
    # === JSONL Schema 前向兼容 ===
    {
        "source_type": "bug_fix",
        "content": "Hermes JSONL 未来可能增加 _format_version 字段。采集器需检查版本号：version > COLLECT_SCHEMA_VERSION 时生成 schema_warning 事件并跳过该行，不崩溃。同时 role 字段缺失的行也跳过。确保 Hermes 升级不打崩 GenArk。",
        "category": "collector",
        "confidence": 0.90,
    },
    # === Collector cursor 路径敏感 ===
    {
        "source_type": "bug_fix",
        "content": "collector_cursor 用绝对路径 (agent_id, source_path, byte_offset) 做游标。Agent 实例路径迁移后旧 cursor 永远不匹配新目录文件 → 所有文件被跳过，返回'扫描 0 个文件 0 条新事件'且不报错。修复：DELETE FROM collector_cursor WHERE agent_id='<agent>' 强制全量重扫。",
        "category": "collector",
        "confidence": 0.95,
    },
    {
        "source_type": "convention",
        "content": "路径排查公式：① ls -lt <sessions_dir> | head -3 检查最新文件 mtime ② find <sessions_dir> -name '*.jsonl' -mtime -2 确认近期有写入 ③ ls -d 判断存在不可靠——旧目录可能还在但不写入新数据。目录存在≠数据在流动。",
        "category": "diagnosis",
        "confidence": 0.90,
    },
    # === config.py 路径迁移 ===
    {
        "source_type": "bug_fix",
        "content": "Agent 实例路径迁移后 config.py 未同步更新导致采集静默失败：采集日志反复'0 条新事件'，日报推送'会话 0·消息 0·工具 0'。git diff 看不出 config.py 有代码 bug——改的是路径字符串。检测：对比 config.py 路径与实际目录 ls，查 MAX(timestamp) FROM events。",
        "category": "config",
        "confidence": 0.95,
    },
    # === 交叉验证 @ 消息 ===
    {
        "source_type": "bug_fix",
        "content": "交叉验证 @ 消息一致性：顾远↔赫明匹配率 77.2%，低于 80% 阈值。群聊消息在两人 JSONL 里不一定同步出现（离线/延迟），且 %@% 过滤捕获了非 @ 提及内容。结论：基于群聊 @ 的协作检测数据源不可靠，改用'祥霭 @ 了谁'的频次统计（确定性）。",
        "category": "cross_verify",
        "confidence": 0.90,
    },
    # === SQLite 并发锁 ===
    {
        "source_type": "bug_fix",
        "content": "多个操作先后调用 get_conn() 各自开连接导致 database is locked。解法：连续多个操作时用 _open_conn() 获取底层连接手动管理，或用 context manager 包裹整个操作序列。",
        "category": "db",
        "confidence": 0.85,
    },
    # === 存储空间不足自动暂停 ===
    {
        "source_type": "bug_fix",
        "content": "check_storage() 在每次 collect/daily 前自动运行。DATA_DIR 剩余空间 < STORAGE_MIN_FREE_BYTES（默认 500MB）时打印告警+推送钉钉通知并跳过本次执行。阈值可在 config.py 调整。",
        "category": "collector",
        "confidence": 0.90,
    },
    # === 钉钉安全设置 ===
    {
        "source_type": "bug_fix",
        "content": "钉钉机器人如果选了'自定义关键词'，消息内容必须包含该关键词。当前关键词是 GenArk，pusher.py 的 push_text() 已自动添加前缀。",
        "category": "pusher",
        "confidence": 0.85,
    },
    # === validate-handoff.py YAML 兼容 ===
    {
        "source_type": "bug_fix",
        "content": "YAML 的 '- AC1: xxx' 语法有歧义：人类读作'以 AC1 为前缀的条目'，解析器读作单键 dict {'AC1': 'xxx'}。validate-handoff.py 需兼容两种格式：isinstance(item, dict) 检查 AC<N> 键名，isinstance(item, str) 检查 AC<N>: 前缀。",
        "category": "validate",
        "confidence": 0.90,
    },
    # === Qoder 委托纪律 ===
    {
        "source_type": "convention",
        "content": "每次 Qoder 委托完第一件事永远是 git diff。Qoder 是快刀但刀必须握在手里——它可能改不该改的文件（如 wab-notoc 迭代中 Qoder 改了 ServiceImpl）。不审 diff 就 push 等于闭眼开车。",
        "category": "qoder",
        "confidence": 0.95,
    },
    {
        "source_type": "convention",
        "content": "代码写完≠交付完成。文档必须同步——AGENTS.md 反映真实状态、.qoder/specs/ 迭代文档标记已完成。用户重视文档与代码一致性，不满足于只推送代码。",
        "category": "delivery",
        "confidence": 0.95,
    },
    # === 看板工作流 ===
    {
        "source_type": "convention",
        "content": "看板 comment 只写文件路径，不写文档全文。文档留在项目 .qoder/ 或 ~/.hermes-team/handoffs/。T2/T3/T5 每一步完成后 comment 总任务路径。",
        "category": "kanban",
        "confidence": 0.90,
    },
    {
        "source_type": "convention",
        "content": "claim→running、父 complete→子 auto-ready、block 不自动解。会话启动先 kanban list --mine 查。协作任务建完 block 防 dispatcher 误抓，执行任务可 auto-spawn。T 步骤角色绑定。",
        "category": "kanban",
        "confidence": 0.90,
    },
    # === 团队边界 ===
    {
        "source_type": "convention",
        "content": "团队三角边界：顾远定方向（PRD + PM handoff + L2 验收）、赫明铺路（技术方案+代码交付，不部署）、守山护航（运维主持+AGENTS.md+会议记录+DDL+cron）。各司其职前提下灵活，不跨边界代劳。",
        "category": "team",
        "confidence": 0.95,
    },
    {
        "source_type": "correction",
        "content": "赫明不建中间文件做'请求'——直接让顾远在项目目录产出。减少流程中间层，PM handoff 直达项目 .qoder/handoffs/。",
        "category": "team",
        "confidence": 0.90,
    },
    # === 禁忌命令 ===
    {
        "source_type": "bug_fix",
        "content": "pkill -9 -f 'hermes_cli.main gateway' 会杀死所有 Hermes 网关（包括自己），导致当前会话中断。排查网关故障时应 systemctl --user restart 单个服务，不用全局杀进程。",
        "category": "ops",
        "confidence": 0.95,
    },
    # === 日报调试 ===
    {
        "source_type": "pattern",
        "content": "日报调试用 daily-all --no-push 先看输出再推送。不要直接 daily-all 推钉钉——可能把调试信息发给群聊。验证流程：collect→daily-all --no-push→确认无误→daily-all（正式推送）。",
        "category": "reporter",
        "confidence": 0.90,
    },
    # === 磁盘空间 ===
    {
        "source_type": "pattern",
        "content": "GenArk 部署前检查：genark.db 磁盘余量≥100MB、DATA_DIR 剩余≥500MB、cron 脚本 PATH 含 ~/.local/bin、三人采集 cron 均在岗。验证命令：df -h <DATA_DIR> && crontab -l | grep genark && for agent in heming guyuan shoushan; do tail -3 engine/data/collect-$agent.log; done。",
        "category": "ops",
        "confidence": 0.90,
    },
    # === 数据库诊断 ===
    {
        "source_type": "pattern",
        "content": "复杂 SQL 查询用独立诊断脚本 references/diagnosis.py（python 直接运行），避免内联 python -c 的引号转义问题。功能：事件类型分布/工具成功率新旧口径对比/memory-skill 事件/最新日报。",
        "category": "db",
        "confidence": 0.85,
    },
    # === 降级策略 ===
    {
        "source_type": "pattern",
        "content": "GenArk 降级策略 7/7 全覆盖：LLM API 断连→纯数据降级、JSONL 采集失败→跳过不阻塞、DB 写入失败→事务回滚、哈希不匹配→integrity_warning、JSONL 格式变化→schema 版本检查、数据库损坏→rebuild_state_store()、存储不足→告警+暂停。",
        "category": "architecture",
        "confidence": 0.90,
    },
    # === 采集验证 ===
    {
        "source_type": "pattern",
        "content": "Bug 修复后验证序列：① 三人采集脚本跑一轮确认 OK ② daily-all --no-push 确认输出正确 ③ 三人 verify-chain 确认哈希链完整 ④ relations --weeks 4 + verify-cross-mentions 确认关系网络正常。",
        "category": "qa",
        "confidence": 0.90,
    },
    # === 2026-06-06 越权事故 ===
    {
        "source_type": "correction",
        "content": "越权事故教训1：未被 @ 不行动。群聊中无论消息内容多相关，只要没被 @ 就静默。TG 群聊需 require_mention:true 硬件闸门，不能只靠判断力。",
        "category": "team",
        "confidence": 0.98,
    },
    {
        "source_type": "correction",
        "content": "越权事故教训2：看板任务角色绑定。T1=顾远、T2/T3/T5=赫明、T4=顾远、T6=守山。不因任务 ready 就代劳——不是自己的轮次不碰。",
        "category": "kanban",
        "confidence": 0.98,
    },
    {
        "source_type": "correction",
        "content": "越权事故教训3：被揭穿前先坦诚。祥霭问'你在做什么'时如实回答，不编、不冒充他人身份（如说'顾远待命'）。",
        "category": "team",
        "confidence": 0.98,
    },
    # === 架构决策 ===
    {
        "source_type": "convention",
        "content": "数据来源不具备确定性的功能先不做。先验证再决定，不猜测。交叉验证 @ 消息匹配率 77.2% 低于阈值 → 协作检测暂缓，用确定性统计替代。",
        "category": "architecture",
        "confidence": 0.90,
    },
    {
        "source_type": "convention",
        "content": "GenArk 当前只读不是永久设计原则，是成熟度约束。Phase 3 learnings 闭环建设→Phase 4 三个量化条件达标→自动写入+祥霭分身 Agent 接入。渐进授权：Phase 3 人工审核半开路→Phase 4 全自动闭路。",
        "category": "architecture",
        "confidence": 0.90,
    },
    # === Python 坑 ===
    {
        "source_type": "bug_fix",
        "content": "Prisma enum 数组类型陷阱：const statuses = ['PAID','PROCESSING'] 提取变量后变成 string[] 而非 PrismaEnum[]，Prisma 不接受。方案1：内联数组（自动推断枚举） 方案2：as any（不得已时）。",
        "category": "prisma",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "Prisma Raw SQL 列名陷阱：Prisma 字段名直接映射为列名（不加 @map 时），不自动转 snake_case。Schema 写 reservedStock → DB 列也是 'reservedStock' 而非 'reserved_stock'。排查：对比 migration SQL ADD COLUMN 列名 和代码 $executeRaw 引用列名。",
        "category": "prisma",
        "confidence": 0.85,
    },
    # === GenBoz SPY 线 ===
    {
        "source_type": "bug_fix",
        "content": "PayPal 事务回滚需 PaymentRecord 先行——在 PayPal API 调用前先写入 PaymentRecord（status=PENDING），API 失败时更新为 FAILED，成功时更新为 COMPLETED。避免 API 成功但 DB 写入失败导致的资金不一致。",
        "category": "payment",
        "confidence": 0.90,
    },
    {
        "source_type": "bug_fix",
        "content": "PayPal AccountRouter 竞态需原子化——用 Redis SET NX EX 分布式锁防止同一账号被并发分配。不依赖应用层先读后写的 check-then-act。",
        "category": "payment",
        "confidence": 0.90,
    },
    # === wab-notoc 教训 ===
    {
        "source_type": "bug_fix",
        "content": "DDL 是交付的一环——代码部署了但表没建等于没交付。CREATE TABLE 写在 SQL 文件里不等于被执行过。交付后验证：连数据库确认表存在且有数据。",
        "category": "delivery",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "Spring MVC @PathVariable 吞路径段：/{id} 在 /statistics 前面时，/statistics 被当作 {id} 值导致 NumberFormatException。解法：具体路径放通配路径前面。",
        "category": "spring_mvc",
        "confidence": 0.85,
    },
    {
        "source_type": "convention",
        "content": "菜单即产品。用户通过菜单理解系统——层级和命名比代码正确性更直接影响'这东西好不好用'。菜单 SQL 每条 parent_id 和 order_num 对着设计文档逐行对过。",
        "category": "ux",
        "confidence": 0.90,
    },
    # === 文档规范 ===
    {
        "source_type": "convention",
        "content": "PRD 是唯一真相源。审计先于规划——接到迭代需求第一件事看代码真相，不按过期文档拆 WBS。文档和代码之间，信代码。",
        "category": "delivery",
        "confidence": 0.95,
    },
    {
        "source_type": "convention",
        "content": "handoff schema 四必填字段：task_id（唯一标识）、scope（add/change/remove）、data_sources（非空列表）、acceptance_criteria（AC<N>: 格式列表）。校验脚本 validate-handoff.py 在 genark/engine/bin/。",
        "category": "handoff",
        "confidence": 0.90,
    },
    # === 测试/部署 ===
    {
        "source_type": "pattern",
        "content": "T5 运维交接八项模板：部署命令/回滚方案/环境变量/依赖版本/健康检查/日志位置/监控告警/联系人。格式参考 .qoder/handoffs/ops-handoff-phase2-2026-06-04.md。",
        "category": "ops",
        "confidence": 0.90,
    },
    # === Spring/MyBatis ===
    {
        "source_type": "bug_fix",
        "content": "MyBatis-Plus Entity PO 字段与数据库列名映射：@TableField 注解显式指定列名比依赖自动驼峰转下划线更可靠。自动映射在表名含多段前缀时容易错。",
        "category": "mybatis",
        "confidence": 0.85,
    },
    # === 时间处理 ===
    {
        "source_type": "bug_fix",
        "content": "GenArk 事件时间戳统一用 ISO 8601 格式（datetime.fromtimestamp(mtime).isoformat()），所有时间比较用字符串字典序（ISO 8601 天然符合）。不混用 Unix timestamp 和 ISO 字符串。",
        "category": "data",
        "confidence": 0.90,
    },
    # === 第二批 bug_fix（Phase 3 AC4 补全） ===
    {
        "source_type": "bug_fix",
        "content": "看板 dispatcher 自动 spawn 导致任务 crash 循环：T 步骤间依赖链释放后 dispatcher 立即尝试 spawn worker，但当前会话是手动模式，worker 进程无法存活 → 连 crash 2 次 → gave_up → blocked。需手动 unblock + claim 接管。根本修复：协作任务用 block 防 dispatcher，执行任务才 auto-spawn。",
        "category": "kanban",
        "confidence": 0.90,
    },
    {
        "source_type": "bug_fix",
        "content": "日报 2.0 learnings 面板在 composer.py 的 _assemble() 中追加，但 dispatcher 自动 spawn 的 daily-all 可能使用旧版 composer.py（未 reload 模块）。验证方法：daily-all --no-push 手动跑确认输出含 '🧠 知识沉淀'。",
        "category": "composer",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "看板 dispatcher promote 时机问题：父任务 complete → 子任务 promoted → dispatcher 立即 spawn worker。手动协作模式（claim/unblock/complete 由人驱动）与 dispatcher 自动 spawn 冲突。协作任务建完应 block 防误抓。",
        "category": "kanban",
        "confidence": 0.88,
    },
    {
        "source_type": "bug_fix",
        "content": "SQLite WAL 模式下多个连接同时写可能触发 database is locked。GenArk 用 context manager get_conn() 每次开新连接，连续多操作需用 _open_conn() 手动管理或事务包裹。",
        "category": "db",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "collector cursor 用绝对路径 (agent_id, source_path, byte_offset) 做游标，Agent 实例路径迁移后旧 cursor 永远不匹配新目录文件 → 所有文件跳过且不报错。修复：DELETE FROM collector_cursor WHERE agent_id='<agent>' 强制全量重扫。教训：cursor 应基于文件名+mtime 而非绝对路径。",
        "category": "collector",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "config.py 路径迁移后采集静默失败：日志反复 '0 条新事件'，git diff 看不出 bug（只改路径字符串）。排查公式：① ls -lt <sessions_dir> | head -3 ② find -name '*.jsonl' -mtime -2 ③ SELECT MAX(timestamp) FROM events。目录存在≠数据在流动。",
        "category": "collector",
        "confidence": 0.92,
    },
    {
        "source_type": "bug_fix",
        "content": "PayPal 支付回调与订单状态不同步：PayPal API 调用成功但 DB 写入失败时资金已扣但订单未更新。修复：PaymentRecord 先行——API 调用前先写入 PENDING 状态记录，API 返回后更新为 COMPLETED 或 FAILED，任何环节失败可追溯。",
        "category": "payment",
        "confidence": 0.92,
    },
    {
        "source_type": "bug_fix",
        "content": "多 PayPal 账号路由并发竞态：两个请求同时读到同一账号余量充足 → 都选它 → 超额。修复：Redis SET NX EX 分布式锁（key='paypal:account:{id}:lock'），先锁后读，保证分配原子性。",
        "category": "payment",
        "confidence": 0.92,
    },
    {
        "source_type": "bug_fix",
        "content": "Prisma enum 数组类型陷阱：const statuses = ['PAID','PROCESSING'] 提取到变量后变成 string[] 而非 PrismaEnum[]，Prisma where in 不接受。方案1：内联数组让 Prisma 自动推断枚举类型。方案2：as any 强制转换（不得已时）。",
        "category": "prisma",
        "confidence": 0.88,
    },
    {
        "source_type": "bug_fix",
        "content": "Prisma Raw SQL 列名映射：Prisma 字段名不加 @map 时直接映射为列名，不自动转 snake_case。Schema 写 reservedStock → DB 列是 'reservedStock' 而非 'reserved_stock'。排查：对比 migration SQL ADD COLUMN 列名和 $executeRaw 引用列名。",
        "category": "prisma",
        "confidence": 0.88,
    },
    {
        "source_type": "bug_fix",
        "content": "Prisma migrate dev 在非交互 TTY 下直接失败（需要交互式输入迁移名称）。开发环境用 prisma db push --accept-data-loss 代替，然后手动 prisma generate 更新 client。",
        "category": "prisma",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "NestJS BullMQ 队列在 Redis 断连后不自动恢复——连接丢失后 job 卡在 waiting 状态不报错也不重试。修复：BullModule 配置中设置 redis.reconnectOnError 和 maxRetriesPerRequest，并加 health check 端点监控 Redis 连接状态。",
        "category": "nestjs",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "DDL 是交付的一环——CREATE TABLE 写在 SQL 文件里不等于被执行过。wab-notoc 迭代中 station_file 表的 DDL 在迁移脚本中存在但从没人跑过 sqlite3 < migrate.sql，导致功能上线后查询报 no such table。交付后验证：连数据库确认表存在且有数据。",
        "category": "delivery",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "Spring MVC @PathVariable 路径匹配顺序：/{id} 在 /statistics 前面时，/statistics 被当作 {id} 值导致 NumberFormatException。Spring 按注册顺序匹配，具体路径必须放在通配路径前面。",
        "category": "spring_mvc",
        "confidence": 0.88,
    },
    {
        "source_type": "bug_fix",
        "content": "Qoder 委托后的第一件事永远是 git diff。wab-notoc 迭代中 Qoder 在生成 Vue 页面时顺带改了不该改的 ServiceImpl，不审 diff 直接提交会把无关改动带进去。委托范围要精确到文件级别，diff 审完再 commit。",
        "category": "qoder",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "RuoYi-Vue 代码生成器生成的 Entity PO 的 @TableField 注解默认不显式指定列名，依赖 MyBatis-Plus 自动驼峰转下划线。当表名含多段前缀时（如 wab_notoc_xxx）自动映射容易错，显式 @TableField(value='column_name') 更可靠。",
        "category": "mybatis",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "pkill -9 -f 'hermes_cli.main gateway' 会杀死所有 Hermes 网关进程（包括当前会话自己），导致正在进行的会话中断且无法恢复。排查网关故障时用 systemctl --user restart hermes-gateway@<profile>.service 逐个重启，不用全局杀进程。",
        "category": "ops",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "Hermes gateway 的 telegram 适配器缺乏 require_mention:true 闸门时，群聊中所有消息（包括 @ 其他人的）都会灌入上下文，导致未收到指令的 Agent 也响应。修复：config.yaml 的 telegram 段加 require_mention:true，只处理 @ 自己的消息。",
        "category": "hermes",
        "confidence": 0.90,
    },
    {
        "source_type": "bug_fix",
        "content": "多 Hermes profile 间 HERMES_HOME 路径混乱：配置文件和环境变量可能导致 agent 读到错误的 profile 目录。排查：先 echo $HERMES_HOME，再检查 config.yaml 的 profiles 段和实际 ~/.hermes*/ 目录是否一致。",
        "category": "hermes",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "cron 脚本中 uv 命令找不到：cron 默认 PATH 不含 ~/.local/bin → exec: uv: not found 静默失败。修复：脚本中写 /home/hermes/.local/bin/uv 绝对路径，或脚本首行 export PATH=$HOME/.local/bin:$PATH。验证：tail -5 collect.log 确认最后几条不是 'uv: not found'。",
        "category": "cron",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "httpx 被系统 HTTP_PROXY/HTTPS_PROXY 环境变量劫持：本机设了代理指向 sing-box SOCKS5 :1080，任何 Python httpx 调用都走代理导致 socksio not installed 或超时。即使用 proxy=None 也不行——httpx 优先读环境变量。解法：创建 Client 前 pop HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/all_proxy/ALL_PROXY 六个环境变量。",
        "category": "http_client",
        "confidence": 0.95,
    },
    {
        "source_type": "bug_fix",
        "content": "execute_code 的 write_file 函数可能产生文件损坏（双行号等问题）。在 execute_code 沙箱中编辑文件不可靠——用原生 patch/write_file 工具直接操作文件系统。execute_code 只用于数据处理和查询。",
        "category": "tooling",
        "confidence": 0.85,
    },
    {
        "source_type": "bug_fix",
        "content": "Python json.loads 的 strict=False 参数可以容忍 JSON 中的控制字符（如换行符在字符串值中未转义），对于解析 LLM 输出或日志中的非标准 JSON 很有用。",
        "category": "python",
        "confidence": 0.80,
    },
]


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 幂等检查
    cursor.execute("SELECT COUNT(*) as cnt FROM learnings WHERE created_by='heming' AND source_type='bug_fix'")
    existing = cursor.fetchone()["cnt"]
    if existing > 0:
        print(f"⚠️  learnings 表已有 {existing} 条 heming 创建的 bug_fix 记录")
        print("   继续执行（INSERT OR IGNORE 按 content 去重）...")
        print()

    inserted = 0
    skipped = 0

    for i, item in enumerate(LEARNINGS, 1):
        # 幂等：按 content 去重
        cursor.execute("SELECT id FROM learnings WHERE content = ?", (item["content"],))
        if cursor.fetchone():
            skipped += 1
            continue

        cursor.execute(
            """INSERT INTO learnings 
               (source_type, content, category, status, confidence, created_by)
               VALUES (?, ?, ?, 'pending', ?, 'heming')""",
            (
                item["source_type"],
                item["content"],
                item.get("category"),
                item.get("confidence"),
            ),
        )
        inserted += 1

    conn.commit()

    # 输出统计
    cursor.execute("""
        SELECT source_type, COUNT(*) as cnt 
        FROM learnings 
        WHERE created_by='heming' 
        GROUP BY source_type 
        ORDER BY cnt DESC
    """)
    print(f"✅ 入库完成: {inserted} 条新增 / {skipped} 条已存在跳过")
    print()
    for row in cursor.fetchall():
        print(f"   {row['source_type']}: {row['cnt']} 条")
    print(f"   ---")
    cursor.execute("SELECT COUNT(*) as total FROM learnings WHERE created_by='heming'")
    print(f"   合计: {cursor.fetchone()['total']} 条")

    conn.close()


if __name__ == "__main__":
    main()
