# 长缨「课程资料复用」设计稿

- 日期：2026-10-26 ｜ 状态：设计稿（历史）；**A、B 已上线，C 待权限模型**（以 [`docs/INDEX.md`](../INDEX.md) 的现状为准）
- 2026-11-04 说明：本文保留当时的设计与取舍，不再代表“未写任何代码”；上线范围和限制见索引与维护指南。
- 基线：`origin/main` @ `1eb4ef4`
- 标注：**【已核实】** = 已在代码中看到，附 `文件:行号`；**【未确认】** = 无法从仓库证实，需产品确认
- 受 `AGENTS.md` 约束：新增表属 §6 高风险，需单独评审；V1 冻结期间新增结构须走评审（`docs/V1_FREEZE.md`）

## 1. 问题

教师反馈（原话意译）：**「每次都要重新上传/重做课件，太麻烦。」**

具体表现：

1. 同一份教案教两个班，要传两次；
2. 同类课（同一知识点、不同届）要重做一遍课件；
3. 一个单元 6–8 份资料，只能一节一节传。

## 2. 现状（全部已核实）

### 2.1 课时

周末课按 `teaching_programs`（学校/年级/学期）下挂 `teaching_lessons`，**每学科固定 18 课**（`changying/web/weekend_plan_views.py:36` `LESSONS = 18`）。

课时字段：`subject`、`lesson_no`、`unit`、`core_target`、`duration_min=120`、`examples_json`、`ppt_json`、`closure_training`、`published`（见 `docs/weekend-course/1-现状核对.md`）。

### 2.2 课件：按**课**存储

表 `weekend_courseware`（`changying/web/weekend_courseware.py:47-64`）：

| 列 | 说明 |
|---|---|
| `school_id` / `lesson_id` / `teacher_id` | `lesson_id` **unique**，一节课一行 |
| `kind` | 模板类型：`rotation` / `reading` / `clock` / `steps` |
| `stage_no` | 第几环节（共 7 环节） |
| `params_json` | `{"version":2,"items":[...]}`，items 按 `(stage, page)` 索引 |
| `approved_json` / `approved_stage` | 审核通过的内容（课堂才展示） |
| `template_id` | **注意**：指向「写作题模板」，不是课件模板（见 2.5） |
| `live_json` | 上课时大屏状态，`{"session:stage:page": ...}` |

课件本体是**经审核的模板 + 参数**，AI 只填参数，不生成 HTML（`changying/services/weekend_courseware.py:1-14`）。

路由（`changying/web/weekend_courseware.py:3-8`）：按 `{lid}` 生成/编辑/审核/移除，**全部以 lesson 为单位**。

→ **结论：课件无法跨课复用。** 新 lesson 要么重新生成，要么重新填参数。

### 2.3 知识点卡：按**学校**存储，校内可复用

表 `kp_cards`（`changying/services/kp_cards.py:33`）：

`school_id`、`grade`、`subject`、`knowledge_key`、`summary`、`steps_json`、`mistakes_json`、`examples_json`、`status(draft/approved)`、`created_by` / `approved_by` / `approved_at`。

`knowledge_key` 与题库 `questions.knowledge`、学生错题记录**同一个字符串**，天然对齐（`kp_cards.py` 模块 docstring）。另有 `images` 表（`kp_cards.py:55`）。

→ **结论：校内可跨课复用，但跨学校不行**；需老师审批才对学生可见。

### 2.4 教案导入：一次一份文件 → 一节课

路由 `POST /teacher/weekend/lessons/import`（`changying/web/weekend_plan_views.py:374-431`）：

- 入参：`subject`、`lessonNo`、`force`、`text`、`file`
- 限制：文件 ≤ **10MB**（`lesson_import.py:15`）、文字 ≤ **20 万字**（`:16`）、格式 `docx/pptx/pdf/txt/md`（`:19`）
- 解析：`extract(ext, data)`（`lesson_import.py:68`），纯正则抽取，不用 XML 解析器（防 entity 展开炸弹）
- 之后**每次导入调用一次 AI** 把文字整理成结构化字段（`weekend_plan_views.py:422` `implementation._ai_call`）
- 已存在教案且 `force != "1"` → **409**（`:412-413`）

→ **结论：一次请求只处理一节课，且每份文件一次 AI 调用。**

### 2.5 已有「模板」先例

`written` 表用 **`session_id = 0` 表示「备课模板」**，`session_id > 0` 是课堂快照（`changying/web/weekend_courseware.py:251-255`、`:282`）。

这是个好先例：**同一张表用哨兵值区分模板与实例**。设计新结构时应优先复用它，而不是再造一套概念。

## 3. 根因

缺三个复用维度：

| 维度 | 现状 | 影响 |
|---|---|---|
| **跨课复用**（同内容不同班/不同课次） | 课件绑死 `lesson_id`（unique） | 每次重做 |
| **跨学期复用**（下学期沿用） | 无版本/复制概念 | 每次重传 |
| **批量导入**（一单元一次） | 一次一份文件 + 一次 AI | 一节一传 |

## 4. 方案

### 方案 A：批量导入（推荐先做）

**目标**：一次上传一个单元/一学期的资料，批量生成课时草稿。

**接口**（新增，不改旧路由）：

```
POST /teacher/weekend/lessons/import/preview   multipart: files[]（或单个 zip）
     → 200 [{filename, detectedLessonNo, subject, chars, ok, error}]

POST /teacher/weekend/lessons/import/commit    json: {items:[{filename, lessonNo, subject}], force}
     → 200 [{lessonNo, status, lessonId}]
```

**两阶段是关键**：预览阶段**只做 `extract`，不调 AI**；确认后 commit 才逐份调 AI。
理由：18 份文件 × 90s AI 超时（`weekend_plan_views.py:422` `timeout=90`）无法在一次请求里跑完，且失败要能续跑。

**课次识别**：优先文件名（`第03课`/`lesson-03`/`03-xxx.docx`），识别不到则要求前端手选。**不做猜测式自动分配**。

**改动点**：
- `changying/services/lesson_import.py`：新增 `extract_batch(entries)`（纯函数，无 IO）
- `changying/web/weekend_plan_views.py`：两个新路由；复用现有校验（大小/格式/字数/409 语义）
- 前端：`changying/web/weekend_pages.py`（现有单份上传入口在 `:496`）

**数据模型**：**不改表**。

**风险**：重复导入覆盖、部分成功、单文件失败拖垮整批 → 逐条事务 + 明确返回每条状态。

**工作量**：小（2 个路由 + 1 个纯函数 + 测试）。

### 方案 B：课程模板复用

**目标**：把一节已审核的课存为模板，新 lesson「从模板创建」只改参数。

**数据模型**（新表，需评审）：

```
weekend_courseware_template
  id, school_id, grade, subject,
  source_lesson_id,            -- 模板来源课（可追溯）
  stage_no, page, kind,
  params_json,                 -- 与 weekend_courseware.items 同构
  status(draft|approved), created_by, approved_by, approved_at
```

不放进 `weekend_courseware` 的原因：该表 `lesson_id` **unique 且非空**，塞 `lesson_id=0` 会破坏约束与语义（与 `written` 的 `session_id=0` 不同，那里列本身允许 0）。

**接口**：

```
POST /teacher/weekend/lessons/{lid}/courseware/save-as-template  {stageNo, page, name}
GET  /teacher/weekend/courseware/templates?grade=&subject=
POST /teacher/weekend/lessons/{lid}/courseware/from-template     {templateId, stageNo, page}
```

**复用语义**：复制参数（copy-on-apply），**模板后续修改不影响已应用的课**；反过来课上的修改也不回写模板。

**风险**：模板腐化（老模板套新课内容错位）→ 应用时必须再跑一次 `cw.clean(kind, params, lesson.reading_plan)` 校验，失败则拒绝并提示。

**工作量**：中（1 新表 + 3 路由 + 审批流 + 测试）。

### 方案 C：跨校区复制

**目标**：同一知识点在多个校区教学时不重复建卡/做课件。

**接口**：

```
POST /teacher/kp/cards/{id}/copy-to-school   {targetSchoolId}
POST /teacher/weekend/lessons/{lid}/copy-to-school {targetSchoolId}
```

**规则**：只复制**已审批**内容；目标校区已存在同 `knowledge_key` 时不覆盖，返回冲突列表；复制记录写 audit。

**工作量**：小–中。**前提**：确认是否真的多校区（【未确认】）。

## 5. 数据模型改动汇总

| 方案 | 改动 | 是否需评审 |
|---|---|---|
| A | 无 | 否 |
| B | 新增 `weekend_courseware_template` | **是**（§6 高风险 / V1 冻结） |
| C | 无（仅插入既有表行） | 否 |

## 6. 权限与边界

- 全部走 `need(u, "teacher")` 与 `current_user`；只能操作本校数据（沿用 `my_lesson` / `school_id` 过滤）。
- 学生侧**不新增任何入口**；模板与批量导入都是教师侧能力。
- 不触碰受保护路径：`.github/**`、`GOVERNANCE.md`、`docs/adr/**`、`render.yaml`、`Dockerfile`、迁移、环境变量。
- 不改 `app.py` 启动链，不改 `create_all` 行为（`app_v924.py:3616`）。

## 7. 测试计划

按 `AGENTS.md` §7.2，必须走应用入口：

1. **A**：`TestClient` 传 3 个文件 → 断言 preview 返回 3 条且**未产生 lesson 行**；commit 后断言 3 节课已建、409 语义与单份导入一致。
2. **A 异常**：超 10MB → 413；扫描版 PDF（抽不出字）→ 单条失败但其他条成功。
3. **B**：存模板 → 新课 from-template → 断言参数一致、`cw.clean` 校验通过；篡改模板后旧课**不受影响**。
4. **C**：跨校复制 → 断言目标校新增、源校不变、冲突时返回冲突列表不覆盖。
5. **反空壳**：每个新增顶层函数都必须被运行时代码引用（`scripts/harness_guard.py` 会拦）。

## 8. 风险与回滚

| 风险 | 处理 |
|---|---|
| 批量导入误覆盖已有教案 | 沿用 `force` 语义；commit 前返回将被覆盖的课次清单 |
| 一次性 AI 调用过多 | 两阶段 + 逐条提交，失败可续 |
| 新表上线后回滚 | 建表本身可回滚（`DROP TABLE` 仅删新表）；先在 scratch 库演练，见 `docs/ops/runbook.md` §4 |
| 模板套用错位 | 应用时强制 `cw.clean` 复核，失败拒绝 |

## 9. 明确不做

- ❌ 不做「AI 自动编排整学期课表」（超出 V1，且易产生幻觉内容）
- ❌ 不做跨学科/跨年级的通用模板库（先解决同年级同学科）
- ❌ 不做学生侧资料下载/导出
- ❌ 不改现有 `weekend_courseware` 表结构与约束

## 10. 建议顺序与验收

1. **A 批量导入**（无表结构改动、风险最低、直接解决「一节课一传」）
   - 验收：一次上传 6 份 → 6 节课建成；异常文件不影响其余；预览不产生数据。
2. **B 课程模板**（需评审后再做）
   - 验收：模板套用后 `cw.clean` 通过率 100%，旧课不受模板变更影响。
3. **C 跨校复制**（确认多校区后再做）
