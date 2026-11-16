# 历史作业来源追溯（隔离样本，2026-11-16）

核对基准：main `0bb9b6b7b93e914f56e69167c91a2d82206bf7cf`；周报分类实现位于尚未合并的草稿 PR #1100（`7efcff67253538a40aebc0ee47b73ea6d45218f9`）。本文不代表生产数据已核查，也不授权对生产历史数据做任何写入。

## 写入路径和证据

`AssignmentRecipient` 以作业和学生为唯一接收关系；`ensure_recipient` 遇到现有记录时直接返回，后续迁班、重新补录不会重写既有来源。`source` 的 ORM 默认值为 `assignment`；隔离 SQLite 的 `PRAGMA table_info` 显示该列 NOT NULL 且无数据库默认值。不能由 ORM 默认值推断历史数据库每行的实际值；其他部署的真实约束未核验。

| 来源或线索 | 写入路径 | 归类依据 |
|---|---|---|
| `assignment` | `app_v924.py` 普通作业创建 | A：明确的普通作业接收记录 |
| `paper_import` | `changying/web/paper_import_routes.py` 导入并布置 | A：明确由导入试卷生成并布置的作业 |
| `knowledge_map`、`teacher_ai_practice`、`ai_reinforcement`、`exam_prep`、`student_self_reinforcement`、`student_module_practice`、`student_comprehensive_test` | 各自知识地图、AI 出题、巩固、应试专项、自主练习路径 | B：明确为对应专项或练习；晚托求助巩固调用 `teacher_reinforcement_assign`，来源为 `ai_reinforcement` |
| `submission_backfill`、`class_history_backfill`、`current_member_backfill` | `app_v924.py` 的 `v730_backfill` | 仅描述接收关系的恢复方式，单独出现不能证明原作业类型。迁班历史用于计算当时班级归属，不提供普通作业来源。 |
| 空字符串、未知值 | 可能来自历史数据或外部写入 | D：无法单凭该值判定；不能把所有空来源视为普通作业。当前模型不允许 NULL，但真实历史数据库约束需另行只读核实。 |

同一作业的另一个接收记录若保留明确的普通或非普通来源，可作为该作业类别的旁证；同一作业同时出现明确普通与明确非普通来源时归 C，不能自动选边。只有补录来源、缺少其他可靠证据时归 D。#1100 对 C、D 提示统计不完整，不把提示当作已恢复来源。

`AuditLog` 的 `assignment.create`、`ai.questions.assign`、`ai.reinforcement.assign`、`knowledge_map.reinforce`、`paper.import.save` 和 `exam_prep.*` 等记录可能提供作业 ID 线索；应核实学校、作业 ID、事件类型和时间一致性及日志完整性。`Paper`、`Submission`、标题和班级成员关系本身不足以唯一证明普通或专项来源；不能用标题关键词代替证据。日志缺失也不能反推类别。

## 隔离样本统计

统计对象为本机自动化测试合成库 `tmp/uiux1100-browser-seed2/test_report_shows_the_weeks_or0/solve.sqlite3` 的 **接收记录**，非作业数、非生产样本。按 #1100 的分类口径：

| 分类 | 数量 | 含义 |
|---|---:|---|
| A | 133 | 有普通作业明确来源或同一作业存在可用普通来源旁证 |
| B | 1 | 有明确专项练习来源 |
| C | 2 | 同一作业来源冲突 |
| D | 3 | 空值、未知值或缺乏可用来源旁证 |

样本中按原始 `source` 分组：`assignment` 71、`paper_import` 1、`knowledge_map` 2、`submission_backfill` 1、`class_history_backfill` 61、空字符串 2、`legacy_manual` 1。分类以每条接收记录计数；冲突的同一作业可贡献多条记录。样本人工构造，不能外推生产规模。测试包含已知历史作业、知识地图、未知及冲突来源、不同学校、报告发布和不完整提示；见 #1100 的 `tests/test_weekend_report_weekly_homework.py`。

## 建议的安全追溯流程

先在获授权的只读脱敏副本中导出候选作业 ID、学校 ID、接收来源和可关联审计事件，记录快照时间与校验值；仅将可验证的唯一事件作为候选证据，对无日志、冲突或无法验证的记录保留 C/D。由业务人员复核抽样、变更数量和跨校边界，再单独设计带前后值、证据来源、幂等键和回滚文件的补全方案及隔离演练。提交方案审核并取得专门授权前，不修改生产数据、不删除不完整提示。
