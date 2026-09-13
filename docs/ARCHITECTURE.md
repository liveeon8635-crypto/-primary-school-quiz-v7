# 长缨辅学代码结构与模块化路线

## 当前生产结构

- `app.py`：稳定生产入口。Render 永远启动 `uvicorn app:app`。
- `app_v924.py`：当前生产实现，包含数据库模型、认证、业务 API、前端 HTML/JS、PWA 资源等。
- `app_v923.py`、`app_v925.py`、`app_v926.py`：近期回退/候选版本，暂时保留。
- `render.yaml`：Render 部署配置。
- `requirements.txt`：生产依赖。
- `requirements-dev.txt`：测试与开发依赖。

## 当前单文件中的主要领域

`app_v924.py` 目前同时承担多类职责，包括：

1. 数据库连接与 SQLAlchemy 模型。
2. JWT 登录、权限与安全策略。
3. Pydantic 请求/响应模型。
4. 数据初始化、迁移、备份和审计。
5. 题库、试卷、作业与学生提交。
6. 五年级定制教学模块。
7. 班级积分、奖励与兑换。
8. 学生跟进、班务和每日工作台。
9. 商业客户、套餐、续费、订单与运营记录。
10. FastAPI 路由、中间件与健康检查。
11. 网页前端、PWA manifest、图标和 Service Worker。

## 目标结构

后续逐步迁移到：

```text
app.py
changying/
  config.py
  database.py
  models/
  schemas/
  auth/
  services/
    teaching.py
    points.py
    homeroom.py
    commercial.py
  routers/
    auth.py
    teaching.py
    points.py
    homeroom.py
    commercial.py
    admin.py
  web/
    assets.py
    pages.py
    pwa.py
tests/
```

## 拆分原则

1. 每次只拆一个领域，不做大爆炸重写。
2. 拆分前后公开 URL、数据库表名、字段和返回格式保持兼容。
3. 每个阶段必须通过自动 smoke test 后才能合并到 `main`。
4. 数据库模型和迁移属于高风险区域，最后拆；先从纯配置、PWA、无状态 helper 开始。
5. `app.py` 始终保持稳定入口，因此 Render 配置不随版本号变化。
6. 历史版本不再靠新增大量 `app_vXXX.py` 长期保存，正式版本历史交给 Git commit/tag 管理。

## 推荐拆分顺序

### 阶段 A：安全网

- GitHub Actions CI。
- `/health`、`/`、`/manifest.webmanifest` smoke tests。
- 本地运行文件和 SQLite 测试数据库加入 `.gitignore`。

### 阶段 B：低风险纯模块

- 配置常量。
- PWA manifest / Web assets。
- 通用 JSON 与格式化 helper。

### 阶段 C：业务服务

- 教学方案。
- 积分奖励。
- 班务工作台。
- 商业运营。

### 阶段 D：API Router

把同领域路由迁入 `APIRouter`，保持原 URL 不变。

### 阶段 E：数据库层

最后迁移 SQLAlchemy models、Session 和 schema migration。该阶段必须增加数据库回归测试后再执行。

## 当前生产约束

任何重构都必须保证：

- `GET /health` 返回 200。
- 首页 `GET /` 返回 200。
- `/manifest.webmanifest` 返回合法 JSON。
- Render 启动命令保持 `uvicorn app:app --host 0.0.0.0 --port $PORT`。
- 不删除近期回退版本，直到新模块化结构稳定运行一段时间。
