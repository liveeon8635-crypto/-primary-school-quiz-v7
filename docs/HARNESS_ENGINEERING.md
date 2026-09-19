# 长缨辅学 Harness Engineering V1

## 目的

本 Harness 解决的不是“让模型多想一点”，而是让工程工作具有可恢复、可验证、可追踪的控制平面。聊天界面可以中断，但工程事实必须能从 GitHub 和 Render 恢复。

## 控制平面

唯一持久状态入口：GitHub Issue **#174 — [HARNESS] Current Engineering State**。

Issue 正文持续保存以下字段：

```yaml
project:
mode:
current_task:
phase:
base_sha:
branch:
pr:
deploy:
validation:
  ci:
  render:
  health:
  v1:
last_completed:
recovery_rule:
```

禁止把 Secrets、密码、Key、token、私钥写入状态 Issue。

## 状态机

```text
recover
  ↓
inspect
  ↓
branch
  ↓
implement
  ↓
diff-check
  ↓
ci
  ↓
merge-check
  ↓
merge
  ↓
deploy
  ↓
production-check
  ↓
checkpoint
  ↓
done / next
```

### recover

每次新会话、UI 卡顿、工具异常或上下文切换后，先做三方核对：

1. Issue #174 当前记录；
2. GitHub main / open PR / CI；
3. Render 最新 deploy。

如果三者不一致，以 GitHub/Render 实际状态修正 Issue，再继续，不重做已经完成的动作。

### merge-check

合并前必须重新确认：
- PR 仍 open；
- head SHA 未变化；
- mergeable；
- PR-head CI success；
- main 是否前进。

若 main 前进造成冲突，在最新 main 重放，不 force-push 旧任务覆盖其他已合并工作。

### deploy

main 合并后默认只观察 Render 的 `new_commit` 自动部署。除非明确诊断为自动部署未发生，否则禁止额外 API deploy。

### production-check

验收目标：
- deploy commit == GitHub merge commit；
- status == `live`；
- 新实例出现 `Application startup complete`；
- `GET /health` 200；
- `GET /v1` 200；
- 没有同一 commit 的异常重复部署。

## 单写入者原则

同一业务域/同一重构流只保留一个 merge-ready PR。

如果并行任务导致 main 前进：
- 保留已经进入 main 的工作；
- 后来的任务基于最新 main 重放；
- 关闭 stale/duplicate PR；
- 不回滚已合并的无关正确工作。

## 自动守卫

`harness-guard.yml` 在所有 main PR 上运行：
- 所有 PR：阻止常见 secret/private-key 文件进入仓库；
- 被识别为 C2 read-side 的 PR：额外阻止生产部署配置、稳定入口、依赖文件和明显写入/auth/schema 变更。

C2 read-side 自动识别条件：分支以 `refactor/c2-` 开头，并且 PR 标题/正文出现 `读侧`、`纯读取`、`只读` 或 `read-side`。

守卫是额外安全网，不替代已有 pytest/CI。

## PR 最小信息

每个自主工程 PR 正文至少写明：
- 范围；
- 明确保留不变的边界；
- 是否纯读侧；
- 基线 main SHA 或“基于最新 main”；
- 是否涉及生产配置/数据库/认证（正常 C2 纯读侧应为否）。

## 恢复示例

当聊天卡住时，不重新问“做到哪了”，执行：
1. 读取 Issue #174；
2. 查 main；
3. 查 Issue 记录的 PR；
4. 查该 head 的 CI；
5. 查 Render；
6. 修正 Issue；
7. 从真实 phase 继续。

这样聊天只承担人机交互，GitHub/Render 才承担工程事实。
