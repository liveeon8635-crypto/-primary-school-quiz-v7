# 教学工作台验收清单（V1.3 实践工作台）

本文档为长缨辅学“实践工作台”（Product Shell V1.3）的最小验收依据，仅用于人工验收与回归核对，不改变任何生产行为。

## 适用范围

- 面向对象：小学阶段晚托、周末课、寒暑假班的教学与运营场景。
- 入口：`/`（实践工作台）、`/workbench`、`/new`；`/classic` 保留 legacy 完整系统。
- 相关实现：`changying/web/product_shell.py`、`changying/compat/legacy.py`。
- 相关测试：`tests/test_product_shell.py`、`tests/test_product_visibility.py`。

## 验收前置条件

1. 分支已 push，GitHub Actions `smoke` job 全绿（Python 3.14，`PYTHONPATH=.`，`pytest -q`）。
2. 未连接生产 PostgreSQL；本地或 CI 使用临时 SQLite 与测试专用 secret。
3. 未合并 `main`，未触发 Render 生产部署。

## 验收项

### A. 品牌与入口

- [ ] `GET /` 返回 200，页面包含“长缨辅学”。
- [ ] 页面包含“实践工作台”与版本标识 `V1.3`。
- [ ] 页面包含 `/classic` 链接与“完整系统”文案。
- [ ] `PRODUCT_SHELL_MARKER == "changying_product_shell_v1_3"`。

### B. 复用既有鉴权与实时数据源

- [ ] 页面引用 `v717Token`、`v717Remember`、`v6Token`。
- [ ] 页面调用 `/session`、`/admin/overview`、`/teacher/classes`。
- [ ] 页面包含 `kpi-students` 与 `classList` 容器。

### C. 运营引导

- [ ] 页面包含“今日上课路径”“运营体检”“首次使用建议”“STEP 01”“移动端快捷入口”。

### D. 教学范围框架

- [ ] 页面包含“小学阶段晚托、周末课、寒暑假班”。
- [ ] 页面包含“当前教学”“学习动态”“历史与衔接”“年级/升学衔接”。

### E. 路由与缓存头

- [ ] `GET /workbench`、`GET /new` 返回 200，且包含“长缨辅学”“实践工作台”。
- [ ] `/`、`/classic`、`/workbench`、`/new` 响应头包含 `X-Changying-Product-UI: changying_product_shell_v1_3`。
- [ ] 上述路径响应头包含 `NO_CACHE_HEADERS` 中定义的全部键值。

### F. 幂等与 legacy 保留

- [ ] 重复调用 `install_product_shell(app)` 不报错，`/` 仍返回 200。
- [ ] 重复调用 `install_product_visibility_routes(app)` 不报错。
- [ ] `GET /classic` 返回 legacy 首页原文，未被工作台覆盖。

### G. 生产约束（只读核对，不在本任务中修改）

- [ ] `GET /health` 返回 200。
- [ ] `GET /manifest.webmanifest` 返回合法 JSON，`name == "长缨辅学"`，`start_url == "/?source=pwa"`，含 `192x192` 图标。
- [ ] `render.yaml` 启动命令保持 `uvicorn app:app --host 0.0.0.0 --port $PORT`。
- [ ] `app.py` 保持极薄、无版本号、无业务逻辑。

## 回归命令

```bash
PYTHONPATH=. pytest -q
```

## 不在本清单范围

- 数据库、权限、商业收费相关变更。
- 生产部署与 Render 手动触发。
- 内嵌前端资源拆分与 API Router 迁移（见 `docs/ARCHITECTURE.md` 阶段 C1–F）。
