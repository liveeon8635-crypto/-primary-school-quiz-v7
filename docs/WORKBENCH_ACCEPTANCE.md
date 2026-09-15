# 教学实践工作台验收清单（V1.3）

本文档为长缨辅学「实践工作台」（Product Shell V1.3）的最小验收清单，用于人工验收与 CI 契约对照。

- 生产入口：`uvicorn app:app --host 0.0.0.0 --port $PORT`（见 `render.yaml`）。
- 工作台标记：`PRODUCT_SHELL_MARKER = changying_product_shell_v1_3`（见 `changying/web/product_shell.py`）。
- 相关自动化契约：`tests/test_product_shell.py`、`tests/test_product_visibility.py`、`tests/test_smoke.py`、`tests/test_deployment_contract.py`。

## 1. 入口与路由

| 检查项 | 期望 | 对应测试 |
| --- | --- | --- |
| `GET /` | 200，返回工作台 HTML，含「长缨辅学」「实践工作台」「V1.3」 | `test_product_shell_html_contains_brand_and_classic_entry`、`test_smoke.test_homepage_loads` |
| `GET /classic` | 200，返回 legacy 首页原文 | `test_product_shell_preserves_legacy_root_at_classic` |
| `GET /workbench` | 200，返回工作台 HTML | `test_product_visibility_routes_add_explicit_workbench_entries` |
| `GET /new` | 200，返回工作台 HTML | `test_product_visibility_routes_add_explicit_workbench_entries` |
| `GET /health` | 200 | `test_smoke.test_health_endpoint` |
| `GET /manifest.webmanifest` | 200，合法 JSON，`name=长缨辅学`，`start_url=/?source=pwa`，含 192x192 图标 | `test_smoke.test_manifest_is_valid_json` |

## 2. 响应头契约

- 工作台相关响应必须带 `X-Changying-Product-UI: changying_product_shell_v1_3`。
- 工作台相关响应必须带 `NO_CACHE_HEADERS` 中定义的全部头（见 `changying/compat/legacy.py`）。
- 覆盖路径：`/`、`/classic`、`/workbench`、`/new`。
- 对应测试：`test_product_visibility_headers_cover_root_and_classic`。

## 3. 幂等安装

- 重复调用 `install_product_shell(app)` 不改变行为。
- 重复调用 `install_product_visibility_routes(app)` 不改变行为。
- 对应测试：`test_product_shell_install_is_idempotent`、`test_product_visibility_install_is_idempotent`。

## 4. 内容与教学范围

- 品牌与入口：含「长缨辅学」「实践工作台」「V1.3」「/classic」「完整系统」。
- 复用既有鉴权与实时数据源：`v717Token`、`v717Remember`、`v6Token`、`/session`、`/admin/overview`、`/teacher/classes`、`kpi-students`、`classList`。
- 运营引导：含「今日上课路径」「运营体检」「首次使用建议」「STEP 01」「移动端快捷入口」。
- 教学范围：含「小学阶段晚托、周末课、寒暑假班」「当前教学」「学习动态」「历史与衔接」「年级/升学衔接」。
- 对应测试：`test_product_shell_reads_existing_auth_and_live_dashboard_sources`、`test_product_shell_v13_contains_operating_guidance`、`test_product_shell_v13_frames_elementary_tutoring_scope`。

## 5. 部署契约

- `render.yaml` 使用 `uvicorn app:app --host 0.0.0.0 --port $PORT`，健康检查路径 `/health`，不得出现 `uvicorn app_v`。
- `app.py` 保持极薄（≤12 行），不含版本号，仅 `from changying.production import app`。
- `changying/production.py` 中 `ASSET_VERSION` 必须等于 `PRODUCTION_MODULE` 去掉 `app_v` 前缀后的值，且对应文件存在。
- 对应测试：`test_render_uses_permanent_entrypoint`、`test_app_py_stays_thin_and_version_agnostic`、`test_production_module_and_asset_version_move_together`。

## 6. 人工验收步骤

1. 本地：`pip install -r requirements.txt -r requirements-dev.txt`，`PYTHONPATH=. pytest -q`，确认全绿。
2. 本地：`uvicorn app:app --reload`，依次访问 `/`、`/classic`、`/workbench`、`/new`、`/health`、`/manifest.webmanifest`，核对第 1、2 节。
3. 浏览器 DevTools 检查响应头，核对第 2 节。
4. 上线后：确认 Render 部署状态为 `live`，`/health` 持续返回 200。

## 7. 非目标

- 本文档不修改生产代码、依赖、数据库、权限或部署配置。
- 不连接生产 PostgreSQL。
- 不合并 `main`，不部署生产。
