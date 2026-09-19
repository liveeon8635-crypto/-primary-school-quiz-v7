# AGENTS.md — 长缨辅学工程 Harness

本文件是进入本仓库进行自主工程工作的首要规则。任何 agent 在写代码前都必须先读取本文件，并读取 GitHub Issue #174 `[HARNESS] Current Engineering State` 作为当前工程断点。

## 1. 产品与边界

长缨辅学只处理小学阶段的教学与学习管理：
- 培训机构教学与学校教学；
- 学生连续发展档案；
- 家长—学生关联；
- 升年级/升学衔接；
- 历史教学查询。

不要引入便利店、健身、AI 工作台、市场化运营等无关业务。

核心数据原则：**一个学生 → 一份长期连续档案**。换班、换老师、晚托、周末课、寒暑假班、升年级或学校教学变化，不以复制学生档案解决。

## 2. 当前生产事实

稳定启动链：

```text
Render
  -> uvicorn app:app --host 0.0.0.0 --port $PORT
  -> app.py
  -> changying.production
  -> changying.compat.legacy
  -> app_v924.py + 已抽离模块
```

生产约束：
- `app.py` 保持极薄；
- 不随意修改 `render.yaml`、`changying/production.py`、Secrets 或环境变量；
- 测试禁止连接生产 PostgreSQL；
- main 合并会触发 Render 自动部署，**不要再手动触发同一提交的第二次部署**；
- 生产验收至少确认：对应 commit 的 deploy = `live`、`/health` 200、`/v1` 200。

## 3. 固定执行协议

每个任务都按以下状态机推进，不得跳步：

1. **recover**：先读 Issue #174，再读取 GitHub main 与 Render 当前状态，确认真实断点；
2. **inspect**：锁定准确 main SHA、相关文件和既有测试；
3. **branch**：从准确 main SHA 创建隔离分支；
4. **implement**：单一目标、小 diff，避免顺手改无关代码；
5. **diff-check**：检查 changed files、patch、风险边界；
6. **ci**：等待 PR-head CI；CI 不绿不合并；
7. **merge-check**：合并前重新读取 main 与 PR mergeable/head SHA；
8. **merge**：使用 expected head SHA 合并；
9. **deploy**：仅观察 Render 自动部署，不重复触发；
10. **production-check**：核对 deploy commit、live、`/health` 200、`/v1` 200；
11. **checkpoint**：把 current_task/base_sha/branch/PR/deploy/validation 写回 Issue #174；
12. **next**：只有上一任务已完成或明确转为 recovery，才进入下一个任务。

## 4. 并行与恢复规则

- 同一业务流只允许一个“准备合并”的 PR。可以有探索分支，但不能同时让多个同域 PR 竞争 main。
- 如果 main 在任务期间前进：
  - 不强推覆盖；
  - 不把旧基线 PR 硬合并；
  - 在最新 main 上重放；
  - 新 PR 验证通过后关闭重复/过期 PR。
- 聊天或 UI 卡住不等于工程停止。恢复时以 Issue #174、GitHub main、PR/CI、Render 为事实来源，不凭聊天最后一句猜状态。
- 不重复执行已经成功的 merge、deploy 或环境变量变更。

## 5. C2 服务层规则

阶段 C2 目标是小批次把“数据库查询 + 业务计算”迁入 `changying/services/`，同时保持：
- ORM 表不变；
- 公共 URL 不变；
- 请求/响应契约不变；
- 权限边界不变；
- 写入语义不变。

**C2 纯读侧**任务禁止夹带：
- `db.add/delete/commit/flush/rollback` 等写入；
- POST/PUT/PATCH/DELETE 路由改造；
- ORM model / schema migration；
- JWT、登录、密码、角色权限改造；
- Render/Secrets/生产入口修改。

自动守卫见 `scripts/harness_guard.py` 与 `.github/workflows/harness-guard.yml`。

## 6. 高风险动作

以下动作必须独立识别，不能混在普通重构里：
- Secrets、API Key、密码、恢复码、私钥；
- 数据库 schema / migration / 回填；
- 批量或不可逆数据写入；
- 登录/JWT/权限；
- 付款/收费；
- 删除、覆盖、公开发布；
- Render 环境变量或生产配置。

任何敏感值不得写入 Issue、PR、测试、日志或聊天。

## 7. 完成定义

一个工程任务只有同时满足以下条件才算完成：
- diff 与任务边界一致；
- PR CI success；
- main 已包含目标提交；
- 对应 Render 自动部署已 live；
- `/health` 200；
- `/v1` 200；
- Issue #174 已更新为最新断点。
