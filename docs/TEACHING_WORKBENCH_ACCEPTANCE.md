# 教学工作台验收清单（V1.3）

本文档为长缨辅学“实践工作台”（产品外壳 V1.3）的人工验收清单，用于在 CI 通过后、合并 `main` 前对教学与运营工作台进行可复核的验收。

本文档只描述验收步骤与判定标准，不修改任何生产代码、依赖、数据库、权限或部署配置。

## 适用范围

- 产品外壳：`changying/web/product_shell.py`（`PRODUCT_SHELL_MARKER = changying_product_shell_v1_3`）。
- 可见性路由：`changying/compat/legacy.py` 中的 `install_product_visibility_routes`。
- 现有自动测试契约：`tests/test_product_shell.py`、`tests/test_product_visibility.py`、`tests/test_smoke.py`、`tests/test_deployment_contract.py`。

本清单不替代上述自动测试，只作为人工验收的补充记录。

## 前置条件

1. 已在独立分支完成改动，未直接提交 `main`。
2. 本地已安装依赖：

   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. 本地未设置 `DATABASE_URL`，使用本地 SQLite；**不得连接生产 PostgreSQL**。
4. 本地启动：

   ```bash
   PYTHONPATH=. uvicorn app:app --reload
   ```

## 自动测试基线

在人工验收前，先确认自动测试全绿：

```bash
PYTHONPATH=. pytest -q
```

判定：全部通过。若失败，停止人工验收，先修复或回退。

## 验收项

### A. 稳定入口与部署契约

- [ ] `GET /health` 返回 200。
- [ ] `GET /` 返回 200，且页面包含“长缨辅学”。
- [ ] `GET /manifest.webmanifest` 返回 200，`content-type` 以 `application/manifest+json` 开头，JSON 中 `name == "长缨辅学"`、`start_url == "/?source=pwa"`，且存在 `sizes == "192x192"` 的图标。
- [ ] `render.yaml` 中启动命令仍为 `uvicorn app:app --host 0.0.0.0 --port $PORT`，`healthCheckPath: /health`，且不含 `uvicorn app_v`。
- [ ] `app.py` 保持极薄、无版本号、无业务逻辑。

### B. 产品外壳内容（V1.3）

- [ ] 首页包含品牌“长缨辅学”与“实践工作台”。
- [ ] 首页包含版本标识“V1.3”。
- [ ] 首页包含“完整系统”入口，且指向 `/classic`。
- [ ] 首页包含“今日上课路径”“运营体检”“首次使用建议”“STEP 01”“移动端快捷入口”。
- [ ] 首页包含小学阶段范围描述“小学阶段晚托、周末课、寒暑假班”。
- [ ] 首页包含“当前教学”“学习动态”“历史与衔接”“年级/升学衔接”。

### C. 复用既有认证与实时数据源

- [ ] 首页引用既有 token 存储键 `v717Token`、`v717Remember`、`v6Token`。
- [ ] 首页引用既有接口 `/session`、`/admin/overview`、`/teacher/classes`。
- [ ] 首页包含 KPI 容器 `kpi-students` 与班级列表容器 `classList`。

### D. 可见性路由与缓存头

- [ ] `GET /workbench` 返回 200，包含“长缨辅学”与“实践工作台”。
- [ ] `GET /new` 返回 200，包含“长缨辅学”与“实践工作台”。
- [ ] `/workbench`、`/new`、`/`、`/classic` 响应头均包含 `X-Changying-Product-UI: changying_product_shell_v1_3`。
- [ ] 上述路径响应头均包含 `NO_CACHE_HEADERS` 中定义的全部头与值。
- [ ] 重复安装 `install_product_visibility_routes` 不产生重复路由或异常（幂等）。

### E. 经典入口保留

- [ ] `GET /classic` 返回 200，且内容为 legacy 首页（未被产品外壳覆盖）。
- [ ] 重复安装 `install_product_shell` 不改变 `/` 与 `/classic` 的行为（幂等）。

## 判定与记录

- 全部勾选通过：验收通过，可进入 PR 合并流程。
- 任一项失败：记录失败项、复现步骤与响应片段，停止合并，按发布规则回退或修复。

## 明确不做的事

- 不修改生产代码、依赖、数据库、权限或部署配置。
- 不合并 `main`，不部署生产。
- 不连接生产 PostgreSQL。
- 不新增或修改自动测试断言；本清单只做人工验收记录。
