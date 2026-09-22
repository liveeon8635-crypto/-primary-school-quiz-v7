# 长缨辅学代码结构与模块化路线

## 当前生产结构

Render 始终启动：

```text
uvicorn app:app --host 0.0.0.0 --port $PORT
```

当前调用链：

```text
Render
  -> app.py
  -> changying.production
  -> changying.compat.legacy
  -> app_v924.py
       + changying.web.pwa
       + changying.utils.*
       + changying.security.*
       + changying.domain.*
```

- `app.py`：永久稳定入口，不包含版本号和业务逻辑。
- `changying/production.py`：只负责选择当前生产实现、应用兼容桥并导出 FastAPI app。
- `changying/compat/legacy.py`：过渡期兼容桥，把已抽离函数安装到 legacy 模块的运行时全局名称中。
- `app_v924.py`：当前生产 legacy 实现；数据库模型、绝大多数 API、前端页面和数据库型业务仍在这里。
- `app_v923.py`、`app_v925.py`、`app_v926.py`：近期回退/候选版本，暂时保留。
- `render.yaml`：Render 部署配置。

## 已完成的模块化

### Web / PWA

- `changying/web/pwa.py`
  - PWA manifest 构造。
  - 修复并隔离了 legacy `MANIFEST` 缺失造成的 `/manifest.webmanifest` 500。

### 通用工具

- `changying/utils/json_tools.py`
  - JSON 列表兼容解析。
- `changying/utils/datetime_tools.py`
  - 学校时区 `UTC+8`。
  - 作业截止时间转换。
  - 学校本地时间序列化。

### 安全模块

- `changying/security/passwords.py`
  - scrypt 密码哈希。
  - 密码校验。
  - 密码强度规则。
  - 密码版本号。
- `changying/security/tokens.py`
  - JWT 签发。
  - 生产密钥、算法和有效期仍由 legacy 配置提供，避免重构产生第二套 secret。
- JWT 解码、用户/学校数据库验证、角色依赖仍留在 legacy，待数据库/Router 阶段处理。

### 业务纯规则

- `changying/domain/assignments.py`
  - 作业提交方式名称。
  - 作业 pending / overdue / completed / late_completed 状态计算。
- `changying/domain/commercial.py`
  - 商业套餐目录。
  - 功能/订阅状态名称。
  - trial / active / grace / expired 状态机。
- `changying/domain/growth.py`
  - 周、日、积分周期时间窗口。
  - 自动奖励周期窗口。
  - 连续进步与连续守纪风险趋势计算。

## 自动测试安全网

GitHub Actions 使用 Python 3.14，在分支 push 和 `main` PR 上执行完整 `pytest`。

当前测试包括：

- `/health`、首页 `/`、`/manifest.webmanifest` smoke tests。
- Render 启动命令、稳定 `app.py`、生产版本与静态资源版本同步的部署契约测试。
- PWA、JSON、日期时间、作业状态、商业订阅、成长趋势等纯函数测试。
- scrypt 密码与 JWT 签发行为测试。
- **隔离数据库认证集成测试**：在临时 SQLite 数据库和测试专用 secrets 中完整验证：
  - 错误密码被拒绝。
  - 正常登录获取 JWT。
  - 初始密码必须修改的业务门禁。
  - 修改密码后旧 JWT 立即失效。
  - 新 JWT 可继续访问受保护接口。
  - 新密码可重新登录。

测试不得连接 Render 的生产 PostgreSQL。

## 仍在 legacy 中的高风险区域

以下内容目前有意不做“大爆炸”迁移：

1. SQLAlchemy Engine、Session、全部 ORM models。
2. schema migration、启动迁移、生产数据回填。
3. JWT 解码与数据库型 `authenticated_user/current_user` 权限依赖。
4. 题库、试卷、作业、提交的数据库查询与写入。
5. 教学方案、积分奖励、班主任工作台的数据库服务。
6. 商业客户、续费、订单、收付款和运营日志。
7. FastAPI 路由注册与 Pydantic schemas。
8. 大型内嵌前端 HTML/CSS/JS。

## 下一阶段顺序

### 阶段 C1：数据库回归安全网（已完成）

在真正移动 ORM/Session 之前，当前 main 已建立以下隔离安全网：

- 临时 SQLite 真实 startup / migration 测试，并验证连续启动幂等。
- 核心教学、连续档案、积分与迁移表的存在性和关键字段契约测试。
- admin / teacher / student / parent 多角色权限矩阵集成测试。
- 题库 → 试卷 → 作业 → 学生提交 → 教师复核的最小教学 CRUD 闭环。
- 课堂积分记录 → 学生读取 → 撤销补偿流水的最小积分 CRUD 闭环。
- 商业订单 → 收款 → 退款 → 作废与商业操作日志的隔离 CRUD 闭环。
- 原有认证生命周期测试继续覆盖登录、首次改密、旧 token 失效与重新登录。

以上测试全部使用临时 SQLite / 测试专用配置，不连接生产 PostgreSQL。阶段 C1 完成后，后续服务层抽离必须保持这些契约继续全绿。

### 阶段 C2：服务层（进行中）

优先把“数据库查询 + 业务计算”迁到 service 层，但路由 URL 和 ORM 表保持不变。当前 main 已存在并由兼容桥实际接线的数据库读侧包括：

```text
changying/services/
  assignments.py       # AssignmentService
  teaching.py          # TeachingService
  points.py            # PointService
  wrong_questions.py   # WrongQuestionService
  followups.py         # FollowUpService
```

以上服务均通过 `changying.compat.legacy.apply_legacy_compatibility` 注入 legacy 全局调用契约，现有 FastAPI URL、ORM 表和返回结构不变；对应 C2 测试覆盖 school/student/teacher/class scope、排序、limit 与序列化契约。

C2 后续不再按旧文档重复创建 `homeroom.py` 或 `commercial.py` 占位模块。下一批只在能够从 legacy 找到**单一、已有测试保护、无 schema 变化**的数据库读侧边界时抽离；优先读侧，写侧继续保留在 legacy，避免服务层整理与生产数据语义同时变化。

当前阶段完成条件：核心教学读侧的直接 ORM 查询逐批减少，兼容桥仍保持原调用契约，C1/C2 集成测试持续全绿。之后才进入阶段 D Router 拆分。

### 阶段 D：API Router

在集成测试覆盖后，再把同领域路由迁入 `APIRouter`，保持公开 URL 和返回结构不变。

### 阶段 E：数据库层

最后迁移：

```text
changying/database.py
changying/models/
changying/schemas/
changying/migrations/
```

数据库层迁移必须小批次执行；禁止同时改表名、字段名和 API 结构。

### 阶段 F：前端资源

后端稳定后，再把内嵌 HTML/CSS/JS 拆到独立资源；不与数据库重构同时进行。

## 强制生产约束

任何重构都必须保证：

- `GET /health` 返回 200。
- 首页 `GET /` 返回 200。
- `/manifest.webmanifest` 返回合法 JSON。
- Render 启动命令保持 `uvicorn app:app --host 0.0.0.0 --port $PORT`。
- `app.py` 保持极薄、无版本号、无业务逻辑。
- 生产实现与 PWA asset version 必须同步升级。
- CI 不通过不得合并 `main`。
- 不允许测试连接生产 PostgreSQL。
- 数据库/权限/收费等高风险模块一次只迁移一个边界。
- 近期回退版本在模块化结构稳定前继续保留；长期版本历史交由 Git commit/tag 管理。
