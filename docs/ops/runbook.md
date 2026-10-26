# 长缨辅学生产运维手册

> 适用范围：`primary-school-quiz-v7` 的 Render 生产环境。
> 工程规则以 [`AGENTS.md`](../../AGENTS.md) 为准；本文只补充**部署之外的运维动作**（回滚、备份、恢复、故障处理）。
> 当前工程断点以 GitHub Issue #174 为准，不要凭本文猜测任务状态。

## 1. 生产拓扑

| 组件 | 配置 | 备注 |
|---|---|---|
| Web Service | `primary-school-quiz-v7`，python，plan `starter`，region `singapore` | 启动：`uvicorn app:app --host 0.0.0.0 --port $PORT` |
| 健康检查 | `healthCheckPath: /health` | Render 以此判断实例是否可用 |
| 数据库 | `primary-school-quiz-v7-db`，PostgreSQL 18，plan `basic-256mb`，region `singapore` | 连接串注入为 `DATABASE_URL` |
| 环境变量 | `DATABASE_URL` / `JWT_SECRET`（自动生成）/ `ACCESS_TOKEN_HOURS=12` / `REMEMBER_TOKEN_DAYS=30` | **改环境变量属高风险动作，见 §6** |
| 代码入口 | `app.py` → `changying.production` → `changying.compat.legacy` → `app_v924.py` | `app.py` 保持极薄 |

定义文件：[`render.yaml`](../../render.yaml)（**受保护路径，不要随意修改**）。

## 2. 正常部署与验收

**路径**：PR → CI 绿 → 合并 `main` → Render **自动部署**。

合并后只做观察，**不要手动再触发同一 commit 的第二次部署**（`AGENTS.md` §2）。

生产验收三件套：

1. 对应 commit 的 deploy = `live`；
2. `GET /health` → 200；
3. `GET /v1` → 200。

> `/v1` 页面里带 `build-sha` meta，可直接核对线上跑的是哪个 commit。

## 3. 应用回滚

**触发条件**：合并后发现线上行为异常，且无法在几分钟内前向修复。

步骤：

1. 记录当前线上 commit（`/v1` 的 `build-sha`）与异常现象；
2. Render Dashboard → 该服务 → **Deploys** → 找到上一个确认正常的 deploy；
3. 对其执行 **Rollback / Redeploy**（Render 会按该 deploy 的 commit 重新部署）；
4. 回滚后复验：deploy = `live`、`/health` 200、`/v1` 200、`build-sha` 等于目标 commit；
5. 在 Issue #174 记录：异常、回滚到的 commit、回滚时间、后续修复计划。

注意：

- 回滚只改变**运行代码**，不改变数据库 schema；若本次发布含 schema 变更，见 §4。
- 回滚后不要让 `main` 与线上 commit 长期分叉，尽快提修复 PR 恢复到 `main`。

## 4. 数据变更回滚

迁移类改动必须**先可回滚再上线**。仓库已有工具：

| 文件 | 用途 |
|---|---|
| [`scripts/m1_rollback.sql`](../../scripts/m1_rollback.sql) | 仅删除 M1（晚托作业助手）新增的三张表：`help_requests`、`homework_recipients`、`homework_notices`，子表优先 |
| [`scripts/m1_verify_counts.sql`](../../scripts/m1_verify_counts.sql) | **只读**核心表行数，用于生产与恢复库对比 |

关键顺序（`m1_rollback.sql` 头部已注明）：

1. 先在 **scratch 库**演练一遍；
2. 回滚应用代码（revert 对应 PR 的合并提交）；
3. 再执行 schema 回滚 SQL。

> 只执行 SQL 而不回滚代码是无效的：应用下次启动会 `create_all` 把空表重新建出来。

## 5. 备份与恢复

### 5.1 平台备份

Render 的 Postgres 实例在付费计划下提供自动备份。**实际保留窗口以 Render Dashboard → 数据库 → Backups 页面显示为准**，不要假设固定天数。

上线前/大变更前，确认一次 Backups 页面可用，并记下最近一次备份时间。

### 5.2 手工逻辑备份

需要临近时间点的快照时：

```bash
pg_dump "$DATABASE_URL" -Fc -f changying-$(date +%Y%m%d-%H%M).dump
```

- 只在受控终端执行，`DATABASE_URL` 从 Render 环境变量读取，**不要写进仓库、Issue、聊天或日志**；
- 备份文件不要提交到 git。

### 5.3 恢复演练（必须定期做）

1. 新建一个 **scratch 数据库**（不要用生产库）；
2. `pg_restore -d <scratch_url> --no-owner changying-*.dump`；
3. 对 scratch 库跑 [`scripts/m1_verify_counts.sql`](../../scripts/m1_verify_counts.sql)；
4. 与生产同一脚本的结果对比：行数应一致，差异应是备份之后新增的行，且能解释；
5. 记录演练时间、备份文件、比对结论。

> 没有演练过的备份不算备份。

## 6. 禁止事项（对齐 `AGENTS.md` §2 / §6）

- ❌ 对同一 commit 重复手动触发部署；
- ❌ 修改 `render.yaml`、`changying/production.py`、Secrets、环境变量（须单独识别并授权）；
- ❌ 让测试连接生产 PostgreSQL；
- ❌ 在生产库上跑 DDL 演练、批量写入或不可逆操作；
- ❌ 把任何密钥、连接串、恢复码写进 Issue / PR / 测试 / 日志 / 聊天。

## 7. 故障处理清单

按顺序排查，每步都记录证据（时间、日志片段、commit）。

| 现象 | 先看什么 | 常见原因 |
|---|---|---|
| 部署后实例起不来 | Deploy logs | 依赖安装失败、`DATABASE_URL` 缺失/失效、启动期异常 |
| `/health` 非 200 | 实例日志 + 数据库状态 | 应用未监听、DB 不可连、健康检查超时 |
| `/v1` 5xx 上升 | error/critical 日志 | 代码缺陷、DB 连接耗尽、慢查询 |
| 数据库连接失败 | Render 数据库状态页 | 实例维护、连接数上限、网络 |
| 页面能开但数据不对 | 只读核对 `m1_verify_counts.sql` | 数据问题 → 走 §5.3 对比备份 |

升级路径：**先止损**（回滚，§3）→ 再定位 → 再前向修复。不要在故障中同时改代码和改 schema。

## 8. 变更前检查清单

- [ ] 改动是否触及受保护路径？（`.github/**`、`GOVERNANCE.md`、`docs/adr/**`、`render.yaml`、`Dockerfile`、数据库迁移、环境变量）
- [ ] 是否含 schema 变更？若有，回滚 SQL 是否已写好并在 scratch 库演练？
- [ ] 上线前是否确认过最近一次备份可用？
- [ ] 验收三件套是否明确（deploy live、`/health`、`/v1`）？
- [ ] 是否已在本 Issue #174 记录 baseline / PR / 预期部署 commit？
