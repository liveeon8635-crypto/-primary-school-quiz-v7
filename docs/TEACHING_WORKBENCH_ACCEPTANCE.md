# 长缨辅学教学工作台验收清单

本文档为教学工作台（实践工作台 V1.3）的最小验收清单，用于人工验收与回归对照。

本文档只描述验收步骤与预期结果，不修改任何生产代码、依赖、数据库、权限或部署配置。

## 适用范围

- 生产入口：`uvicorn app:app --host 0.0.0.0 --port $PORT`（见 `render.yaml`）。
- 工作台页面由 `changying/web/product_shell.py` 提供，标记为 `changying_product_shell_v1_3`。
- 显式入口路由由 `changying/compat/legacy.py` 的 `install_product_visibility_routes` 安装。
- 现有自动化契约见 `tests/test_product_shell.py` 与 `tests/test_product_visibility.py`。

## 验收前置条件

1. 已按 `README.md` 安装 `requirements.txt` 与 `requirements-dev.txt`。
2. 未设置 `DATABASE_URL` 时使用本地 SQLite；验收不得连接生产 PostgreSQL。
3. 本地启动：`uvicorn app:app --reload`。

## 验收项

### A. 基础可用性

| 编号 | 步骤 | 预期结果 |
| --- | --- | --- |
| A1 | 访问 `GET /health` | 返回 200 |
| A2 | 访问 `GET /` | 返回 200，页面包含“长缨辅学”与“实践工作台” |
| A3 | 访问 `GET /manifest.webmanifest` | 返回 200，`content-type` 以 `application/manifest+json` 开头，JSON 合法 |

### B. 工作台入口

| 编号 | 步骤 | 预期结果 |
| --- | --- | --- |
| B1 | 访问 `GET /workbench` | 返回 200，包含“长缨辅学”与“实践工作台” |
| B2 | 访问 `GET /new` | 返回 200，包含“长缨辅学”与“实践工作台” |
| B3 | 检查 `/workbench`、`/new` 响应头 | `X-Changying-Product-UI` 等于 `changying_product_shell_v1_3` |
| B4 | 检查 `/`、`/classic` 响应头 | 同样带有 `X-Changying-Product-UI` 与 `NO_CACHE_HEADERS` |
| B5 | 访问 `GET /classic` | 返回 200，展示 legacy 首页内容 |

### C. 工作台内容

| 编号 | 步骤 | 预期结果 |
| --- | --- | --- |
| C1 | 查看工作台页面 | 包含“今日上课路径”“运营体检”“首次使用建议”“STEP 01”“移动端快捷入口” |
| C2 | 查看教学范围说明 | 包含“小学阶段晚托、周末课、寒暑假班” |
| C3 | 查看教学分区 | 包含“当前教学”“学习动态”“历史与衔接”“年级/升学衔接” |
| C4 | 查看数据来源 | 页面引用 `v717Token`、`v717Remember`、`v6Token`、`/session`、`/admin/overview`、`/teacher/classes`、`kpi-students`、`classList` |

### D. 幂等与兼容

| 编号 | 步骤 | 预期结果 |
| --- | --- | --- |
| D1 | 重复调用 `install_product_shell` | 不报错，`/` 与 `/classic` 仍返回 200 |
| D2 | 重复调用 `install_product_visibility_routes` | 不报错，`/workbench` 与 `/new` 仍返回 200 |

## 自动化对照

以下命令应在本地与 CI 中保持一致：

```bash
PYTHONPATH=. pytest -q
```

CI 配置见 `.github/workflows/ci.yml`，使用 Python 3.14 与 Node 22。

## 不在本清单范围

- 数据库迁移、权限模型、商业收费逻辑。
- 生产部署与 Render 状态确认。
- 前端资源拆分与 API Router 迁移。

上述内容属于 `docs/ARCHITECTURE.md` 中标注的高风险区域，需单独评审。
