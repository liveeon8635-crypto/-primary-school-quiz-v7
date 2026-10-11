# 长缨：「习题辅助」与「互动课堂」改造方案（只读分析）

- 分析基线：`main` 提交 `3f2f744`（PR #686 合并后），分析日期 2026-10-11。
- 性质：只读分析。没有修改任何代码，没有建分支、提 PR 或部署；本文件是唯一写入的文件。
- 引用格式：`文件:行号`。凡写「未确认」的地方，表示仓库内找不到依据，不能当作事实。

---

## 0. 先说三个重要结论

1. **你要的两个功能，现有代码已经覆盖了相当一部分，不是从零开始。** 错题本、同类题再练（教师驱动）、教师侧 AI 出题、互动课堂（环节、随堂检测、正确率与选项分布、讲义）都已存在。新增工作的重点是「学生自助」「AI 分步提示」「实时推送」「大屏」「家长简报」「局域网模式」，而不是重做基础。
2. **你指定的三个依据文件在仓库里不存在**：`GOVERNANCE.md`、`docs/PROJECT_STATE.md`、`docs/adr/`。在 `main` 及全部 git 历史中都找不到（`git ls-tree`、`git log --all -- GOVERNANCE.md docs/PROJECT_STATE.md docs/adr` 均无结果）。`AGENTS.md:§7` 把 `GOVERNANCE.md`、`docs/adr/**` 列为受保护路径，说明它们可能存在于别处或将来才建，**这一点未确认**。本报告改用以下文件作为项目状态依据：`AGENTS.md`、`README.md`、`docs/ARCHITECTURE.md`、`docs/V1_FREEZE.md`、`docs/V1_SCOPE.md`、`docs/HARNESS_ENGINEERING.md`，以及 AGENTS.md 指定的工程状态 Issue #174（最近更新 2026-09-29）。
3. **没有任何实时通信（WebSocket / SSE）**，所有「实时」都是前端定时轮询（见 §4）。这是功能 B 最大的架构缺口。

---

## 1. 现状概览

### 1.1 目录结构

| 路径 | 作用 | 依据 |
|---|---|---|
| `app.py` | Render 稳定入口，保持极薄 | `AGENTS.md:§2`，`README.md` |
| `changying/production.py` | 选择生产实现（`app_v924`）并应用兼容桥 | `changying/production.py:17-30` |
| `changying/compat/legacy.py` | 过渡期兼容桥，把已抽离模块「接线」进 legacy | `README.md`，`docs/ARCHITECTURE.md` |
| `app_v924.py`（8307 行） | 当前生产实现：ORM 模型、绝大多数 API、内嵌前端 HTML/JS | `app_v924.py:43-760`（模型） |
| `changying/services/` | 已抽离的服务层（作业、错题、积分、课堂等） | `docs/ARCHITECTURE.md` |
| `changying/domain/` | 纯业务规则 | 同上 |
| `changying/web/` | V1 页面与 APIRouter（课堂执行、随堂检测、讲义等） | `README.md` |
| `app_v923/925/926.py` | 回退/候选版本，保留 | `docs/ARCHITECTURE.md` |
| `tests/` | 209 个文件（含 smoke、契约、集成测试） | `ls tests` |

### 1.2 技术栈

- 后端：FastAPI 0.141.1、SQLAlchemy 2.0.52、psycopg 3.3、PyJWT、openpyxl、pypdf、requests（`requirements.txt`）。
- 数据库：生产为 PostgreSQL；未设置 `DATABASE_URL` 时回退本地 SQLite（`app_v924.py:30-41`）。
- 前端：没有独立前端工程。页面是 Python 字符串里的 HTML/CSS/JS（`app_v924.py:7894` 的 `INDEX_HTML`，以及 `changying/web/*.py` 里大量 `patch_*` 字符串替换，规则见 `AGENTS.md:§7.3`）。
- Python 版本：CI 使用 3.14（`.github/workflows/ci.yml:24`）。

### 1.3 启动与部署

- 启动链：`uvicorn app:app --host 0.0.0.0 --port $PORT` → `app.py` → `changying.production` → `changying.compat.legacy` → `app_v924.py`（`AGENTS.md:§2`，`render.yaml:14`）。
- 单进程单实例；启动事件里 `Base.metadata.create_all(engine)` 建表、再跑迁移与种子（`app_v924.py:3611-3640`）。
- `render.yaml` 声明 web 与数据库都是 `plan: free`、区域 `singapore`（`render.yaml:3-4,11-12`）。
- **不一致，未确认哪个是现状**：Issue #174（2026-09-25/26 的检查点）记录生产 web 为付费 `0.5c-512mb`、Postgres 为付费 `0.1c-256mb`、单实例。`render.yaml` 里仍写 free。以 Render 控制台为准，仓库无法证明。
- 合并 main 会触发 Render 自动部署，不手动重复触发（`AGENTS.md:§2`）。
- 版本号：`APP_VERSION="10.7"`（`app_v924.py:2663`），`ASSET_VERSION="924"`（`changying/production.py:18`）。
- 没有 Dockerfile、Procfile（`git ls-files` 无匹配）。

### 1.4 治理约束（对方案有直接影响）

- 小批次、单一目标、小 diff；高风险动作（schema/迁移、登录/JWT/权限、Secrets、环境变量）必须独立识别（`AGENTS.md:§3, §6`）。
- 新增的函数/路由必须被运行时代码接线，功能类改动必须有走真实路由的测试，否则 `scripts/harness_guard.py` 会拦截（`AGENTS.md:§7`）。
- V1 已冻结：新增「第一层业务概念、生产表、批量数据修改或新的自动判断规则」默认进入 V1.1/V2 评审（`docs/V1_FREEZE.md` 的「冻结规则」一节）。**这意味着功能 A、B 都要走评审，且新增表要有迁移与回滚说明。**
- 互动课堂的「家长可见」被 #174 明确列为 Phase F 可选/后续范围（#174 2026-09-26 15:10 检查点第 5 条），不是遗漏。

---

## 2. 数据模型

存储方式：全部在关系型数据库（SQLAlchemy ORM）。浏览器本地存储只保存登录令牌与界面偏好，不存业务数据（`v717Token`/`v717User` 键见 `changying/web/v1_classic_unified_top.py`）。

### 2.1 用户与班级

| 表 | 关键字段 | 位置 |
|---|---|---|
| `users` | `username`（唯一）、`name`、`role`、`grade`、`school_id` | `app_v924.py:53-63` |
| `classes` / `class_students` | 班级与学生关系 | `app_v924.py:73-88` |
| `student_class_history` | 换班/毕业历史 | `app_v924.py:89` |
| `parent_students` | 家长—学生多对多 | `app_v924.py:112` |
| `user_security` | 必须改密码、失败计数 | `app_v924.py:65` |

学生建档：教师创建学生时，`name` 与 `username`、初始密码都是必填（`app_v924.py:5815-5822`）。**数据库层面没有「昵称」字段，`name` 既用于显示也可能存真实姓名**（见 §8 合规）。

### 2.2 题目、题库与试卷

- `questions`：`grade/subject/textbook/unit/knowledge`、`text`、`options_json`、`correct_index`、`explanation`、`question_type`、`answer_json`、`figure_json`（`app_v924.py:119-137`）。**题库就是数据库表，按 `school_id` 隔离**；还有内置题库服务 `changying/services/builtin_question_bank*.py`、教材包 `grade5_math_textbook_packs.py`。
- 题型：单选、判断（用 `correct_index`），填空/计算/简答（用 `answer_json` 的标准答案与可接受答案）（`app_v924.py:1233-1255`，判分见 §3）。
- `papers`：`question_ids_json` 保存题目 ID 列表（`app_v924.py:139-150`）。
- `teaching_questions`：教学方案侧另一套题（单选，`app_v924.py:527-542`），与 `questions` 并存。

### 2.3 作业与答题记录

- `assignments`（班级 + 试卷 + 截止日期，`app_v924.py:152-160`）；`assignment_recipients` 记录接收学生与来源 `source`（`app_v924.py:101`）。
- `submissions`：`score/correct/total`、`answers_json`（每题 `question_id/selected_index/text_answer/correct`）、`completion_actor`（`app_v924.py:162-176`）。
- 学习证据：`learning_evidence_events`（追加式，`app_v924.py:223`）。系统明确不由单次成绩推断「已掌握」（`docs/V1_SCOPE.md`，`masteryInferred=false`）。

### 2.4 错题

`wrong_question_records`：`student_id`、`assignment_id`、`question_id`、`source`、`knowledge`、`problem_text`、`wrong_answer`、`correct_answer`、`analysis`、`status`（`active`/`mastered`）、`reinforcement_count`、`mastered_at`（`app_v924.py:495-513`）。`reinforcement_links` 记录一次针对性练习与哪些错题关联、得分（`app_v924.py:515-525`）。

### 2.5 AI 相关

- `school_ai_configs`：按学校的服务商、地址、模型、**加密的 API Key**、`enabled`、`allow_student_data`（`app_v924.py:446-459`）。
- `ai_usage_logs`：每次调用的功能、模型、token、耗时、错误（`app_v924.py:461-476`）。
- `ai_grading_reviews`：AI 判卷建议 + 教师确认（`app_v924.py:478-493`）。

### 2.6 互动课堂（不在 ORM 类里，用 SQLAlchemy `Table` 动态注册）

- `classroom_sessions / classroom_segments / classroom_presenter_turns / classroom_events`：`changying/web/v1_classroom_execution.py:64-135`。环节上有 `reveal_distribution`、`reveal_correct_answer`、`reveal_explanation` 三个展示开关（`:106-108`）。
- `classroom_quick_checks / classroom_quick_check_responses`：`changying/web/v1_classroom_quick_check.py:52-100`。响应表有 `UNIQUE(check_id, student_id)`，同一学生同一题只保留一条，可改答案（`:96`、`:900-925`）。
- 这些表靠启动时 `create_all` 创建（`app_v924.py:3612`）。`create_all` 只建缺失表，不改已有表（`app_v924.py:3596-3598` 注释）。

---

## 3. 现有答题流程（出题 → 作答 → 判分 → 展示）

**判分完全由服务端程序完成，没有交给大模型，这一点已满足你的约束。**

| 步骤 | 前端/接口 | 后端函数 | 位置 |
|---|---|---|---|
| 教师组卷/布置 | 教师页 | `Paper`/`Assignment`，AI 出题走 `ai_generate_questions`、`ai_questions_assign` | `app_v924.py:4549, 4750` |
| 学生取题 | `GET /papers/{pid}/questions` | `paperq`，学生只拿 `qj_public`（不含答案） | `app_v924.py:6065`，`qj_public` 在 `:1306` |
| 学生提交 | `POST /student/assignments/{aid}/submit` | `ssubmit` → `grade_answers` → `save_sub` | `app_v924.py:6077-6110`，`:1497`，`:1660` |
| 判分 | 服务端 | `grade_answers`：按 `correct_index` 或 `_text_answer_matches` 比对；**忽略客户端传来的 `score/correct`** | `app_v924.py:1497-1537`，`:1255`；客户端字段只是 `SubmitBody` 里的可选值（`:1069-1070`） |
| 自主练习 | `POST /student/practice-submit` | `psubmit` → `grade_answers`；**不写错题**（见下） | `app_v924.py:6191-6199` |
| 错题归档 | 提交时 | `archive_objective_assessment_wrong_answers`（幂等：按作业+题目更新） | `changying/services/assessment_feedback.py:80-194` |
| 结果展示 | `/student/assignments`、`/student/progress` | `sassign` 等 | `app_v924.py:6056, 6201` |
| 错题本 | `GET /student/wrong-questions` | 只读列表，返回 `activeCount/masteredCount` | `app_v924.py:5011-5018` |
| 针对性再练 | 教师 `POST /teacher/students/{sid}/reinforcement/generate` → `…/assign` | AI 生成 → 教师审核 → 布置；做完后 `_reinforcement_mastery_update`：得分 ≥80 标记「已掌握」 | `app_v924.py:5021, 5160, 4904-4925`（≥80 判断在 `:4919`） |

要点：
- 错题自动归档**只对特定来源生效**：`recipient.source` 必须在 `LEARNING_FEEDBACK_SOURCES` 里（学生综合测试、模块练习、AI 针对性练习、教师 AI 练习）（`assessment_feedback.py:18-26, 80-110`）。普通教师布置的作业与「自主练习」（`psubmit`）**不会自动进错题本**；另有两处手写创建 `WrongQuestionRecord`（`app_v924.py:4880, 4896`，`rubric_evidence_closure.py:741`），触发条件我没有逐一核对，**未确认**。
- 「已掌握」的判定是「再练得分 ≥80 分」（`app_v924.py:4919`），这是现有的固定规则。
- 学生端的错题本是**只读**的；再练由教师触发。**学生自己点「再练这题」目前不存在**（`app_v924.py` 的 `/student/*` 路由中没有对应入口，已 grep 核对）。

---

## 4. 现有能力盘点

图例：可复用 = 直接用；需改造 = 有基础但需调整；缺失 = 没有。

| 能力 | 状态 | 说明与依据 |
|---|---|---|
| 错题记录 | **可复用** | 表与归档已有（§2.4、§3） |
| 错题本学生页（自助浏览） | **可复用/需改造** | 只读接口 `app_v924.py:5011`；前端页面是否完整展示，**未确认**（未逐页核对前端） |
| 同类题再练（教师驱动） | **可复用** | `reinforcement/generate` 与 `assign`（`app_v924.py:5021, 5160`） |
| 学生自助再练 | **缺失** | 见 §3 |
| 自动按知识点/错题生成练习（教师触发） | **可复用** | `changying/web/v1_student_practice.py:586, 662`（`practice-options`、`auto-practice`），复用 Question→Paper→Assignment 管线，不新增表（该文件开头注释） |
| 用户身份 | **可复用** | JWT + 角色（学生/教师/家长/管理员），`current_user`、`need`（`app_v924.py:859, 874`） |
| 昵称/学号式最小化标识 | **缺失** | 只有 `username` 与 `name`（§2.1） |
| 统计 | **可复用** | 随堂检测 `quick_check_summary` 返回提交人数、正确人数、正确率、**逐选项人数与百分比**（`changying/services/classroom_quick_check.py:103-128`） |
| 实时通信（WebSocket/SSE） | **缺失** | 全仓库 grep `websocket|EventSource|StreamingResponse|text/event-stream` 无业务命中；实时靠轮询：教师课堂页每 5 秒轮询（`v1_classroom_execution.py:247-254`），学生邀请页 5 秒（`:320-325`），学生全局 10 秒（`:329-`） |
| 大屏/投屏视图 | **缺失** | 没有专门的大屏页面。教师页有分布展示开关（`v1_classroom_execution.py:275`），但那是教师操作页，不是给教室投影的页面。（grep `大屏|投屏|projector` 无专门实现） |
| 大模型调用（教师侧） | **可复用** | `_ai_call` 统一入口：按学校配置、同步 `requests.post`、记录用量、每小时限额（`app_v924.py:3256-3290`；`AI_HOURLY_LIMIT` 默认 60，`:3109`；`_ai_rate_check` `:3251`） |
| 大模型调用（学生侧） | **缺失** | `_ai_call` 的调用方全是教师/管理员功能（`app_v924.py` 内 7 处调用，均在教师路由；另见 `v1_classroom_review.py:578`、`v1_classroom_quick_check.py:519`） |
| AI 数据出境控制 | **可复用** | 需管理员开启 `allow_student_data` 才能发送学生数据（`app_v924.py:5024`、`:4929`） |
| 互动课堂：会话/环节/邀请/随堂检测/讲义 | **可复用** | `v1_classroom_execution.py`、`v1_classroom_quick_check.py`、`v1_classroom_handout_release.py` |
| 老师推题 → 学生作答 | **可复用/需改造** | 教师开放随堂检测 → 学生 `respond`（`v1_classroom_quick_check.py:614, 849`），服务端判对错（`:896`）；只支持单选（选项索引），没有填空类 |
| 家长简报 | **缺失** | 家长接口只有孩子、作业、进度、教学、积分、沟通记录（`app_v924.py:6218-6250, 7690`）；没有基于课堂的简报。#174 把「家长可见」列为 Phase F 后续范围 |
| 离线/本地同步 | **缺失** | 没有 outbox、同步或冲突处理代码（grep 无命中） |

---

## 5. 功能 A（习题辅助）改造方案

### 5.1 范围拆解

A1 自动错题本 · A2 同类题再练 · A3 AI 分步提示（不给答案）。判分仍然只由 `grade_answers` 完成。

### 5.2 最小可用版本（建议 4 步）

**步骤 A-0：评审与边界确认（不写代码）**
- 在 V1.1/V2 评审里确认：是否允许把学生答题内容发给 AI（`allow_student_data` 的家长/学校告知）。依据 `docs/V1_FREEZE.md` 冻结规则。

**步骤 A-1：让所有在线判分都进错题本（小改动，无新表）**
- 修改：`changying/services/assessment_feedback.py` 的 `archive_objective_assessment_wrong_answers`，当前只处理 `LEARNING_FEEDBACK_SOURCES`（`:80-110`）。方案：增加「自主练习」来源，并让 `psubmit`（`app_v924.py:6191`）在判分后调用同一归档函数。
- 数据：复用 `wrong_question_records`，不改表。
- 约束：必须经 `harness_guard` 接线检查，并有走 `TestClient` 的测试（`AGENTS.md:§7`）。

**步骤 A-2：学生自助「同类题再练」（新接口，无新表）**
- 新增 `POST /student/wrong-questions/{wid}/practice`：取该错题的 `knowledge/subject`，从 `questions` 同知识点、同年级抽 3–5 道**非本错题**，沿用现有「题目→试卷→作业」管线（参考 `v1_student_practice.py:335 select_student_practice_questions`，`:662 create_student_practice`）。
- 判分：学生提交走现有 `ssubmit` → `grade_answers`；全对（或得分 ≥80，沿用 `app_v924.py:4919`）才把错题标记为「已掌握」。
- 修改文件：`changying/web/v1_student_practice.py`（新增学生端 Router，需在 `compat/legacy.py` 中安装）、学生前端补丁；学生入口按钮。
- 题库不足时的行为：返回明确提示，不用大模型现编（避免答案由 AI 决定）。**题库在各知识点的覆盖度未确认**，需要抽样统计（见 §8）。

**步骤 A-3：AI 分步提示（新接口，新用量记录）**
- 新增 `POST /student/questions/{qid}/hint`，参数：当前提示级别 1/2/3。
- 实现：复用 `_ai_call(db, u, "student_hint", prompt)`（`app_v924.py:3256`），但**服务端不把标准答案和 `correct_index` 放进 prompt**；prompt 里只给题干、知识点、学生已作答内容，要求只给思路、不得出现最终答案；返回后服务端用 `_text_answer_matches`/选项文字做**答案泄露检测**，命中则丢弃并降级为固定模板提示。
- 限额：沿用学校级 `AI_HOURLY_LIMIT`；另加每个学生每题 3 次上限（需要新字段或新表记录次数；**这是 schema 变化，需单独授权**，也可先用 `ai_usage_logs`（`app_v924.py:461`）按 `user_id + feature` 计数，不改表）。
- 数据最小化：prompt 中不放 `name`/`username`，只放学生 ID 的哈希或不放。
- 管理员开关：沿用 `allow_student_data`，未开启时返回「老师暂未开启 AI 提示」。
- 未成年人风险：学生侧首次出现大模型调用，见 §8。
- 降级：AI 超时/限流（`_ai_call` 会抛 502/504/429）时前端显示固定的通用解题步骤提示，不阻塞作答。

### 5.3 可观察验收条件（功能 A）

| 编号 | 验收条件 |
|---|---|
| A-1 | 学生做完一次自主练习，错题本里 **5 秒内** 出现本次答错的题，且重复提交同一题不产生重复记录（幂等） |
| A-2 | 学生在错题本点「再练」，**3 秒内**拿到 3–5 道同知识点、不含原错题的题；全部答对后该错题状态变为「已掌握」；答错则保持「未掌握」 |
| A-3 | 学生点「提示」，**10 秒内**得到提示；提示文本经自动检测**不包含标准答案**（测试用例用含答案的伪造 AI 返回验证会被拦截并降级）；超过每题 3 次返回 429 样式的明确提示；AI 不可用时返回固定模板而不是报错页 |
| 通用 | 判分结果与改造前一致（用 `tests/` 里的判分用例回归）；`harness_guard` 与 CI 全绿；无 `name`/`username` 进入发给 AI 的 prompt（测试断言 prompt 内容） |

---

## 6. 功能 B（互动课堂）改造方案

### 6.1 现状与差距

已有：教师开放随堂检测、学生作答、服务端判对错、正确率与选项分布（`classroom_quick_check.py:103-128`）、教师控制分布/答案/解析的展示开关。缺：大屏页面、推送、家长简报、局域网模式。

### 6.2 最小可用版本（建议 5 步）

**步骤 B-1：大屏只读页（无新表，只读 API）**
- 新增 `GET /teacher/classroom-sessions/{sid}/live-board`（教师鉴权）与一张只读页面，展示：当前题目、已提交人数/班级人数、正确率、各选项人数与百分比。数据直接取 `quick_check_summary`（`classroom_quick_check.py:103`）。
- 隐私：大屏**不显示学生姓名**，只显示聚合数据；教师页仍可看到明细（`teacher_payload` 当前会返回 `studentName`，`v1_classroom_quick_check.py:378-401`，这是教师页，不是大屏）。
- 先用现有轮询把页面做出来（轮询间隔缩短为 2 秒），不依赖新通信技术。

**步骤 B-2：实时推送（SSE，见 §6.3）**
- 新增 `GET /teacher/classroom-sessions/{sid}/events/stream`（SSE）；学生端同理推送「新题已开放」。
- 服务端内存里保存「会话 → 订阅者」，答题写库后向订阅者发一条轻量事件；**客户端收到事件后再调用现有 GET 取最新聚合**，这样推送只是「提醒刷新」，数据依然来自数据库，断线重连后用一次全量 GET 即可对齐。

**步骤 B-3：课后家长简报（先教师生成、教师确认后发布）**
- 数据来源：`classroom_events`、`classroom_quick_check_responses`、`classroom_segments` 的 `baseline_accuracy/postcheck_accuracy`（`v1_classroom_execution.py:96-98`）。
- 生成：先用**模板化文本**（本堂课主题、孩子是否参与、班级正确率区间；不含排名、不含同学信息），可选再用 `_ai_call` 润色，但**事实字段由程序给定**。
- 发布：新增家长只读接口 `GET /parent/children/{sid}/classroom-briefs`（权限沿用 `ParentStudent` 校验，参考 `app_v924.py:7690-7697`），需要新表保存已发布简报（schema 变化，需单独授权）。
- 注意：#174 把「家长可见」列为后续范围（Phase F），本步骤需重新评审。

**步骤 B-4：局域网本地运行（见 §6.3，可行性有限）**
- 建议做成「**教室单机服务**」：一台教室电脑运行同一份代码，SQLite 存储（代码已支持无 `DATABASE_URL` 回退 SQLite，`app_v924.py:30-41`）；课后手动「导出课堂结果包」再导入云端。
- 不建议做双向实时同步。

**步骤 B-5：课堂前的体检与降级**
- 课前「课堂体检」按钮：检查登录、学生是否在班、网络往返时间，并预热云端实例。

### 6.3 三项可行性评估

**① 实时通信方案**
- 候选：（a）继续轮询；（b）SSE；（c）WebSocket。
- 现状：uvicorn[standard] 已装（`requirements.txt`），框架本身支持 SSE 与 WebSocket；但项目里零使用，也没有相关测试，所以是**新增能力**。
- 约束：生产是**单进程单实例**（`render.yaml:14`，#174 记录单实例），内存订阅表可行；若将来多实例需 Redis 或数据库轮询（**当前不需要**）。
- 推荐：**SSE 为主、2 秒轮询为兜底**。理由：只需要「服务器→浏览器」单向；对代理/防火墙更友好；断线可自动重连；比 WebSocket 少一套握手与状态。是否被学校网络或 Render 的代理缓冲影响，**未确认**，必须在真实环境实测（见验收 B-2）。
- 现有轮询的负载估算：30 名学生 × 每 5–10 秒 1 次 ≈ 每秒 3–6 次 GET，对单实例可承受；但这是我的估算，**未压测，未确认**。

**② 本地局域网运行**
- 可行的部分：代码无硬依赖外网即可启动（SQLite 回退存在）；教师与学生通过局域网地址访问同一服务即可。
- 阻碍（均依据仓库）：
  - 没有 Dockerfile/一键安装脚本，运行需要 Python 3.14 环境（`ci.yml:24`）。课堂电脑能否安装，**未确认**。
  - 教室网络下浏览器是否允许对 `http://局域网IP` 使用现有的安全头与 PWA/Cookie 设置，**未确认**：交接 cookie 的 `secure` 取决于 `request.url.scheme == "https"`（`v1_auth_handoff.py:32, 68`），http 下为 False；但应用另外设置了 HSTS 与较严格的 CSP（`app_v924.py:3581` 的 CSP 含 `connect-src 'self' https:`，`:3590` 起设置 HSTS），局域网 http 下可能不匹配，**需实测**。
  - 课后同步云端：仓库没有同步机制（§4）。双写会带来 ID 冲突、冲突合并，**复杂度高**，不建议在第一版做。
- 结论：做「单机课堂 + 课后导出/导入」可行；做「实时双向同步」不可行（第一版）。

**③ Render 免费实例的休眠与延迟**
- 仓库内依据：`render.yaml` 写的是 free；#174 记录生产已付费（§1.3），**以哪个为准未确认**。
- 外部事实（非仓库内容，**未在本仓库核实**）：Render 免费 web 服务一段时间无请求会休眠，再次唤醒需要数十秒。若教学现场仍在 free 套餐，**课堂第一次请求会明显卡顿**，不能接受。
- 付费常驻实例则无休眠，主要延迟变成地区（singapore）到教室的网络往返。
- 建议：课堂使用前提定为**付费常驻实例**，并加上「课前预热/体检」（步骤 B-5）；若不能升级，只能以局域网单机模式作为课堂方案。
- 免费 Postgres 到期问题：#174 记录已升级为付费（2026-09-25/26），当前仍按此为准，但**以控制台为准，未确认**。

### 6.4 可观察验收条件（功能 B）

| 编号 | 验收条件 |
|---|---|
| B-1 | 教师开放随堂检测后，大屏页面在**3 秒内**显示题目；30 名学生各提交一次后，大屏的「已提交 / 正确率 / 选项分布」与数据库统计一致，且页面上看不到任何学生姓名 |
| B-2 | SSE 开启时，学生提交后教师大屏在**2 秒内**更新；人为断网 10 秒再恢复，页面在**5 秒内**自动重连并与服务端数据一致；SSE 被拦截时自动退回 2 秒轮询，功能不丢失 |
| B-3 | 教师「开放题目」后，学生端在**3 秒内**看到新题；同一学生重复提交只保留最后一次（沿用 `UNIQUE(check_id, student_id)`，`classroom_quick_check.py:96`） |
| B-4 | 课后教师点「生成家长简报」，**30 秒内**得到草稿；教师确认发布后，绑定的家长账号能看到，未绑定账号返回 403；简报里不含其他学生姓名与排名 |
| B-5 | 局域网模式：断开外网，教师电脑启动服务，30 名学生用手机通过局域网地址完成一次完整随堂检测；课后导出结果包能在云端导入且不产生重复记录（具体设备数为假设，**未确认**） |
| 通用 | 现有课堂测试全绿：`tests/test_interactive_classroom_execution.py`、`tests/test_classroom_quick_check_phase_c.py`、`tests/test_classroom_execution_phase_ab.py`；`harness_guard` 通过；新增表之外**不改任何已有表** |

---

## 7. 每个步骤的验收条件汇总

见 §5.3（A-1…A-3）与 §6.4（B-1…B-5）。另外所有涉及新表或新字段的步骤（A-3 的次数字段、B-3 的简报表）在合并前必须额外满足：迁移方案与回滚边界（`docs/V1_FREEZE.md` 冻结规则）、单独的生产授权（`AGENTS.md:§6`）、`create_all` 只建新表不改旧表的验证（`app_v924.py:3596-3598`）。

---

## 8. 风险与待确认问题

### 8.1 未成年人数据与合规

1. **姓名最小化尚未落地**：`users.name` 必填（`app_v924.py:5815-5822`），随堂检测教师明细、家长接口、AI 提示词都可能带出姓名。你要求用昵称或学号：数据库没有昵称字段；若新增字段是 schema 变化，**需单独授权**；更小的做法是约定 `name` 只填昵称/学号，并在 AI prompt 与大屏中一律不使用 `name`。
2. **学生侧大模型调用是首次**：数据发给第三方服务商。`allow_student_data` 是管理员开关（`app_v924.py:5024`），但**面向监护人的告知与同意流程，仓库内没有，未确认**；#174 提到已配置运营主体与隐私页（2026-09-26），法律措辞仍需真实运营方审核（#174 同一检查点第 2 条）。
3. **未注册公司**：你说明尚未注册公司；#174 记录已配置运营主体为「长缨辅学」。作为个人/未注册主体处理未成年人个人信息的合规性，**我无法判断，需要法务意见**。
4. AI 返回内容的适龄性与准确性：需要教师抽检机制（教师侧已有「审核再布置」，`teacher_reinforcement_assign`，学生侧提示没有审核环节，所以必须有答案泄露检测与固定模板降级）。

### 8.2 学生设备与环境（均未确认）

- 学生用什么设备（手机、平板、学校电脑）、浏览器版本、是否有稳定 Wi-Fi：**未确认**。SSE 与现有前端补丁在老旧浏览器上的表现需实测。
- 课堂并发人数：现有测试未做压测，**未确认**。
- 教室网络是否放行 SSE 长连接、是否有代理缓冲：**未确认**。

### 8.3 数据与迁移

- 新表走 `create_all` 即可，但**不改旧表**；任何给旧表加列都需要像 `ensure_submission_completion_actor_column`（`app_v924.py:3600-3610`）那样的单独、幂等、可回滚的迁移。
- `render.yaml` 与实际套餐不一致（§1.3），涉及是否有休眠，**必须先在 Render 控制台确认**。
- 内置题库对各年级/知识点的覆盖度未统计；同类题再练可能取不到足够题目（**未确认**）。
- 页面由字符串替换补丁拼装，改页面要先找到真实注入入口，否则会触发 RuntimeError（`AGENTS.md:§7.3`；本人此前实测过补丁锚点脆弱）。

### 8.4 治理风险

- V1 冻结规则要求新业务概念走评审（`docs/V1_FREEZE.md`）。
- 功能 B 的家长简报与 #174 里「Phase F 可选」的范围重叠，需要重新决定优先级。

---

## 9. 建议开发顺序与工作量粗估

估算口径：1 人天 = 一个熟悉本仓库的工程师一个工作日；含测试与评审等待，不含部署日历时间。数字是粗估，**未经验证**。

| 顺序 | 内容 | 粗估 | 依赖 |
|---|---|---|---|
| 0 | 评审与确认：Render 套餐、学生设备、合规方案、题库覆盖度统计 | 2–3 天（以沟通为主） | — |
| 1 | A-1 全部在线判分进错题本 | 1–2 天 | — |
| 2 | A-2 学生自助同类题再练 | 3–4 天 | 1 |
| 3 | B-1 大屏只读页（轮询版） | 2–3 天 | — |
| 4 | B-2 SSE 推送 + 轮询兜底 | 3–4 天 | 3 |
| 5 | A-3 AI 分步提示（含答案泄露检测、限额） | 4–6 天 | 0（合规） |
| 6 | B-3 家长简报（需新表与授权） | 4–6 天 | 0、4 |
| 7 | B-5 课堂体检与降级 | 1–2 天 | 4 |
| 8 | B-4 局域网单机 + 导出导入 | 6–10 天，不确定性大 | 0（环境确认） |

推荐先做 1、2、3、4（不涉及新表、不涉及学生侧大模型，收益最大、风险最小），5、6 在合规结论后再做，8 最后做、且只在确有教室断网需求时才做。

---

## 附：本分析的核对方法

- 读取：`AGENTS.md`、`README.md`、`render.yaml`、`requirements.txt`、`docs/*.md`、Issue #174；
- 检索：`app_v924.py` 的模型、判分、提交、错题、AI、启动段落；`changying/services/{assessment_feedback,classroom_quick_check}.py`；`changying/web/{v1_classroom_execution,v1_classroom_quick_check,v1_student_practice}.py`；
- 未做：未运行服务、未压测、未连接生产、未读取 Render 控制台、未逐页核对前端页面。凡依赖这些的结论均已标「未确认」。
