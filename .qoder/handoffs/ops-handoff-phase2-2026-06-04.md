# GenArk Phase 2 运维交接单

> **日期**: 2026-06-04
> **交付人**: 赫明
> **接收人**: 守山
> **代码基线**: `833f8b9`

---

## 一、变更概要

Phase 2 推送策略对齐创始人确认的方案 C（拼版合推 + 重大事件单推）。

| 变更 | 旧 | 新 |
|------|----|----|
| 日报推送 | 每人分推（顾远 + 赫明各一条） | 一条拼版合推 |
| 重大事件 | 无 | 阈值触发时紧跟拼版推送 |
| cron 日报 | `daily-guyuan.sh` + `daily-heming.sh` | `daily-all.sh`（一条） |
| 采集 cron | 不变 | `collect-guyuan.sh` + `collect-heming.sh` |
| 赫明实例路径 | `~/.hermes-genboz`（已删除） | `~/.hermes/profiles/heming` |

---

## 二、Cron 状态

```
# GenArk — 采集（两人并行）
*/30 * * * * /data/projects/genark/engine/bin/collect-guyuan.sh
*/30 * * * * /data/projects/genark/engine/bin/collect-heming.sh
# GenArk — 拼版日报（替代分推，23:00）
0 23 * * * /data/projects/genark/engine/bin/daily-all.sh
```

**确认清单**：
- [ ] `crontab -l | grep genark` 显示 3 条（非 4 条）
- [ ] `collect-heming.sh` 日志不再显示 "0 条新事件"（路径已修复）
- [ ] 23:00 后祥霭收到 1 条拼版日报（非 2 条分推）

---

## 三、新增文件

| 文件 | 用途 |
|------|------|
| `engine/genark/major_events.py` | 重大事件阈值判定（技能≥+5 / 新技能 / 记忆≥+5 / 成功率<50%） |
| `engine/bin/daily-all.sh` | 拼版日报 cron 脚本（替代旧两条分推） |

---

## 四、验证命令

```bash
# 1. 手动跑一次拼版日报（不推送，检查输出）
cd /data/projects/genark/engine
/home/hermes/.local/bin/uv run python -m genark.cli daily-all --no-push --date $(date +%Y-%m-%d)

# 2. 验证哈希链
/home/hermes/.local/bin/uv run python -m genark.cli verify-chain --agent heming
/home/hermes/.local/bin/uv run python -m genark.cli verify-chain --agent guyuan

# 3. 确认 cron 在岗
crontab -l | grep genark

# 4. 检查最近日志
tail -20 data/daily-all.log
```

---

## 五、回滚方案

如需回退到分推模式：

```bash
# 恢复旧 cron
crontab -l | sed 's|daily-all.sh|daily-guyuan.sh|' | crontab -
# 手动加回 heming 分推
(crontab -l; echo "0 23 * * * /data/projects/genark/engine/bin/daily-heming.sh") | crontab -

# 代码回退
cd /data/projects/genark && git revert 833f8b9
```

---

## 六、已知问题

1. **交叉验证 77.2%** — 交汇小节的 @ 数据不完全可靠，当前用质量门禁（双方数据不对称时降级展示）
2. **赫明 6/2-6/4 数据空白** — 路径过期期间采集中断，DB 中无此期间事件。是否需回溯补采待定
3. **顾远今日采集为 0** — 需确认 `collect-guyuan.sh` 是否正常（顾远实例路径未变，应为正常）

---

赫明
2026-06-04
