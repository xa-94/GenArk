# Learnings 归档报告 — Phase 3 审核完成
> 日期: 2026-06-06 11:32
> 审核人: 守山
> 总计: 150 条 approved

## 消费记录

- 150 条 learnings → learning_consumptions 表
- consumed_by=shoushan, action=apply

## Pattern → SKILL.md

- #31 [architecture] → `engine/data/skills_extracted/learned-architecture-31.md`
  GenArk 降级策略 7/7 全覆盖：LLM API 断连→纯数据降级、JSONL 采集失败→跳过不阻塞、DB 写入失败→事务回滚、哈希不匹配→integrity_warning、JSONL 格式变化→schema 版本检查、数据库损坏→...
- #30 [db] → `engine/data/skills_extracted/learned-db-30.md`
  复杂 SQL 查询用独立诊断脚本 references/diagnosis.py（python 直接运行），避免内联 python -c 的引号转义问题。功能：事件类型分布/工具成功率新旧口径对比/memory-skill 事件/最新日报。...
- #11 [http_client] → `engine/data/skills_extracted/learned-http_client-11.md`
  Python HTTP 调用封装模式：创建 httpx.Client 前 pop HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/all_proxy/ALL_PROXY 六个环境变量。已封装在 g...
- #29 [ops] → `engine/data/skills_extracted/learned-ops-29.md`
  GenArk 部署前检查：genark.db 磁盘余量≥100MB、DATA_DIR 剩余≥500MB、cron 脚本 PATH 含 ~/.local/bin、三人采集 cron 均在岗。验证命令：df -h <DATA_DIR> && c...
- #47 [ops] → `engine/data/skills_extracted/learned-ops-47.md`
  T5 运维交接八项模板：部署命令/回滚方案/环境变量/依赖版本/健康检查/日志位置/监控告警/联系人。格式参考 .qoder/handoffs/ops-handoff-phase2-2026-06-04.md。...
- #32 [qa] → `engine/data/skills_extracted/learned-qa-32.md`
  Bug 修复后验证序列：① 三人采集脚本跑一轮确认 OK ② daily-all --no-push 确认输出正确 ③ 三人 verify-chain 确认哈希链完整 ④ relations --weeks 4 + verify-cross...
- #28 [reporter] → `engine/data/skills_extracted/learned-reporter-28.md`
  日报调试用 daily-all --no-push 先看输出再推送。不要直接 daily-all 推钉钉——可能把调试信息发给群聊。验证流程：collect→daily-all --no-push→确认无误→daily-all（正式推送）。...

## Convention → 待写入 AGENTS.md

- #36 [architecture]
  数据来源不具备确定性的功能先不做。先验证再决定，不猜测。交叉验证 @ 消息匹配率 77.2% 低于阈值 → 协作检测暂缓，用确定性统计替代。
- #37 [architecture]
  GenArk 当前只读不是永久设计原则，是成熟度约束。Phase 3 learnings 闭环建设→Phase 4 三个量化条件达标→自动写入+祥霭分身 Agent 接入。渐进授权：Phase 3 人工审核半开路→Phase 4 全自动闭路。
- #22 [delivery]
  代码写完≠交付完成。文档必须同步——AGENTS.md 反映真实状态、.qoder/specs/ 迭代文档标记已完成。用户重视文档与代码一致性，不满足于只推送代码。
- #45 [delivery]
  PRD 是唯一真相源。审计先于规划——接到迭代需求第一件事看代码真相，不按过期文档拆 WBS。文档和代码之间，信代码。
- #14 [diagnosis]
  路径排查公式：① ls -lt <sessions_dir> | head -3 检查最新文件 mtime ② find <sessions_dir> -name '*.jsonl' -mtime -2 确认近期有写入 ③ ls -d 判断存在不可靠——旧目录可能还在但不写入新数据。目录存在≠数据在流动。
- #46 [handoff]
  handoff schema 四必填字段：task_id（唯一标识）、scope（add/change/remove）、data_sources（非空列表）、acceptance_criteria（AC<N>: 格式列表）。校验脚本 validate-handoff.py 在 genark/engine/bin/。
- #23 [kanban]
  看板 comment 只写文件路径，不写文档全文。文档留在项目 .qoder/ 或 ~/.hermes-team/handoffs/。T2/T3/T5 每一步完成后 comment 总任务路径。
- #24 [kanban]
  claim→running、父 complete→子 auto-ready、block 不自动解。会话启动先 kanban list --mine 查。协作任务建完 block 防 dispatcher 误抓，执行任务可 auto-spawn。T 步骤角色绑定。
- #21 [qoder]
  每次 Qoder 委托完第一件事永远是 git diff。Qoder 是快刀但刀必须握在手里——它可能改不该改的文件（如 wab-notoc 迭代中 Qoder 改了 ServiceImpl）。不审 diff 就 push 等于闭眼开车。
- #25 [team]
  团队三角边界：顾远定方向（PRD + PM handoff + L2 验收）、赫明铺路（技术方案+代码交付，不部署）、守山护航（运维主持+AGENTS.md+会议记录+DDL+cron）。各司其职前提下灵活，不跨边界代劳。
- #44 [ux]
  菜单即产品。用户通过菜单理解系统——层级和命名比代码正确性更直接影响'这东西好不好用'。菜单 SQL 每条 parent_id 和 order_num 对着设计文档逐行对过。
- #50 [ux]
  菜单即产品——用户通过菜单理解系统，层级和命名比代码正确性更直接影响用户体验。菜单 SQL 每条 parent_id 和 order_num 对着设计文档逐行对过，不能批量生成后跳过人工核对。

## Bug Fix / Correction 统计

- bug_fix: 27 条 → 消费记录已写入，可用于未来自动 Memory 同步（Phase 4）
- correction: 104 条 → 消费记录已写入

## 分类明细

- genark: 16 条
- kanban: 15 条
- engineering: 9 条
- teamwork: 8 条
- hermes: 7 条
- devops: 6 条
- process: 6 条
- python: 6 条
- telegram: 5 条
- architecture: 4 条
- team: 4 条
- meeting: 4 条
- collector: 3 条
- delivery: 3 条
- ops: 3 条
- knowledge: 3 条
- memory: 3 条
- proxy: 3 条
- sqlite: 3 条
- tools: 3 条
- cron: 2 条
- db: 2 条
- http_client: 2 条
- memory_watcher: 2 条
- payment: 2 条
- prisma: 2 条
- reporter: 2 条
- state_computer: 2 条
- ux: 2 条
- git: 2 条
- knowledge_graph: 2 条
- config: 1 条
- cross_verify: 1 条
- data: 1 条
- event_store: 1 条
- mybatis: 1 条
- pusher: 1 条
- python_pattern: 1 条
- spring_mvc: 1 条
- validate: 1 条
- diagnosis: 1 条
- handoff: 1 条
- qoder: 1 条
- skills: 1 条
- qa: 1 条
