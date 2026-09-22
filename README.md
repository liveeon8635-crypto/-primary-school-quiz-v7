# 长缨辅学

长缨辅学是面向小学阶段培训机构、学校、教师、学生与家长的教学系统。当前生产服务运行在 Render，后端为 FastAPI + SQLAlchemy，生产数据库使用 PostgreSQL。

## 生产入口

Render 固定启动：

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

`app.py` 是永久稳定入口，不应直接加入业务逻辑或版本号。当前生产实现由 `changying/production.py` 选择，并通过 `changying/compat/legacy.py` 与正在逐步模块化的 legacy 应用兼容。已抽离的 service 和 Web Router 保持原 URL/调用契约；`app_v924.py` 中剩余 ORM、直接 API 与内嵌前端继续按测试保护的小批次迁移，不做一次性重写。

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
  services/
    assignments.py
    teaching.py
    points.py
    wrong_questions.py
    followups.py
    transition_plans.py
    parent_link_history.py
    class_history.py
    academic_summary.py
  web/
    pwa.py                      # PWA / favicon
    product_shell.py            # 产品首页 / Classic 兼容入口
    v1.py                       # V1 shell
    v1_auth_handoff.py          # V1 → Classic 一次性认证交接
    v1_transition_*.py          # 升年级/升学衔接事实与计划
    v1_historical_teaching.py   # 往期教学只读事实
    v*_learning_evidence*.py    # 学习证据读写/可见性
    v1_classroom_*.py           # 互动课堂执行、检测、讲义与评价
tests/                         # 单元、smoke、契约与隔离集成测试
docs/ARCHITECTURE.md           # 模块化状态与后续路线
render.yaml                    # Render 部署定义
```

## 长缨辅学 V1

V1 复用现有认证、学生、家长关联、班级历史、作业、成绩与成长档案接口，新增独立的机构/学校工作台及学生连续发展视图。范围和占位能力见 [docs/V1_SCOPE.md](docs/V1_SCOPE.md)。原教学系统继续保留在 `/classic`。

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
