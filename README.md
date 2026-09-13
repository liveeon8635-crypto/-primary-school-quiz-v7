# 长缨辅学

长缨辅学是面向学校、教师、学生与家长的教学与运营系统。当前生产服务运行在 Render，后端为 FastAPI + SQLAlchemy，生产数据库使用 PostgreSQL。

## 生产入口

Render 固定启动：

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

`app.py` 是永久稳定入口，不应直接加入业务逻辑或版本号。当前生产实现由 `changying/production.py` 选择，并通过 `changying/compat/legacy.py` 与正在逐步模块化的 legacy 应用兼容。

## 代码结构

```text
app.py                         # 稳定 Render 入口
app_v924.py                    # 当前 legacy 生产实现
changying/
  production.py                # 生产实现选择器
  compat/legacy.py             # 过渡期兼容桥
  domain/
    assignments.py             # 作业纯规则
    commercial.py              # 商业套餐/订阅纯规则
    growth.py                  # 成长分析时间窗口/趋势规则
  security/
    passwords.py               # 密码哈希与校验
    tokens.py                  # JWT 签发
  utils/
    datetime_tools.py
    json_tools.py
  web/
    pwa.py
tests/                         # 单元、smoke、契约与隔离集成测试
docs/ARCHITECTURE.md           # 模块化状态与后续路线
render.yaml                    # Render 部署定义
```

## 本地运行

创建并激活 Python 3.14 环境后：

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app:app --reload
```

未设置 `DATABASE_URL` 时应用使用本地 SQLite。生产环境必须通过环境变量使用托管 PostgreSQL。

## 测试

```bash
PYTHONPATH=. pytest -q
```

GitHub Actions 会在分支 push 和 `main` Pull Request 上自动执行同一套测试。测试包括：

- 健康检查、首页和 manifest smoke tests；
- 部署入口契约；
- 密码/JWT 行为；
- 作业、商业订阅、成长趋势等纯业务规则；
- 使用临时 SQLite 与测试专用 secret 的真实登录生命周期集成测试。

测试不得连接生产 PostgreSQL。

## 发布规则

1. 所有改动先进入独立分支。
2. 建立 PR 并等待完整 CI 通过。
3. CI 全绿后 squash 合并到 `main`。
4. Render 自动部署 `main`，不重复手动触发。
5. 上线后确认部署状态为 `live`，并确认 `/health` 持续返回 200。
6. 数据库、权限和商业收费属于高风险区域，必须有对应集成测试后才允许迁移。

详细模块化计划见 `docs/ARCHITECTURE.md`。
