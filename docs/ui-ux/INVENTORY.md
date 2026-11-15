# 页面资产清单

基线 main 与生产 revision 为 `d9b56caff452abfc57b9378df9051738ffae57ad`。注册 574 个路由项。排除参数化 API、健康检查及 9 个 /fresh-v* 历史页面别名后，应用生产入口通过隔离 SQLite 返回 37 个可直接访问的 HTML 页面入口。这里按页面模板族去重，同时保留实际别名。

| 页面族 | 已核实路由 | 最终页面来源 | 用户操作与角色 | API、权限和依赖 | 现有回归 |
|---|---|---|---|---|---|
| 产品首页与独立教师工作台 | /、/new、/workbench | product_shell.py:teacher_workbench_html; legacy.py:install_product_visibility_routes | 访客，介绍产品；教师，读取本人工作台事实 | 会话查询与工作台读取；不写教学业务数据 | tests/test_individual_workspace.py, tests/test_product_shell.py |
| V1 登录、工作台、档案、历史、衔接、导览 | /v1、/v1/workspace、/v1/student、/v1/history、/v1/transition、/v1/guide | v1.py:v1_html; legacy.py 多层补丁及 gzip 兼容桥 | 教师查看当前教学与学生连续档案；学生进入本人学习；家长看授权孩子；管理员使用管理入口 | 现有角色会话及各自 API。/v1 页面共用最终拼装 HTML，不代表操作页相同 | tests/test_v1_shell_router_contract.py, tests/test_v1_mobile_real_data_layout.py, tests/test_student_continuity.py |
| 全部功能与 Classic 工具 | /v1/tool、/classic?legacy=1&unified=1&from=v1&page=... | v1_classic_gzip_embed.py、v1_tool_hub.py、v1_unified_tools.py | 四种角色按菜单进入保留的 Classic 教学及管理功能 | /session、单次认证交接、工具页面授权列表及已有 Classic API | tests/test_v1_classic_embed_bootstrap.py, tests/test_v1_cross_context_auth_handoff.py, tests/test_v1_unified_tools_session_bridge.py |
| 晚托作业助手 | /v1/homework | homework_assistant.py:homework_page → homework_assistant_pages.py | 教师建立与审阅作业；学生处理作业、提示与求助 | HOMEWORK_ASSISTANT=1；角色会话及作业/求助 API | tests/test_homework_teacher_help.py, tests/test_homework_assistant_tables.py, tests/test_homework_help.py, tests/test_homework_guided_help.py |
| 周末课备课与课件 | /v1/weekend-plan | weekend_plan_views.py:plan_page_html → weekend_pages.py | 教师导入教案、审核题目、编排课件和逐步图示 | 教师会话、现有周末课程和课件 API | tests/test_weekend_import_integrity.py, tests/test_weekend_review_flow.py, tests/test_weekend_example_practice_separation.py |
| 周末课教师控制 | /v1/weekend | weekend_views.py:control_page_html → weekend_pages.py | 教师开课、推进环节、操作提示、批改及结束课堂 | 教师会话、班级及课堂 session API | tests/test_weekend_views.py, tests/test_weekend_live_controls.py |
| 课堂大屏 | /v1/weekend-board?s=...、/v1/classroom-board/{sid} | weekend_views.py:board_page_html、v1_classroom_live_board.py:board_html | 教师控制；投影设备显示当前环节、批准课件与已公开答案 | 当前课堂数据、答案公布状态、课堂遮挡/冻结状态 | tests/test_weekend_board_layout.py, tests/test_classroom_live_board.py, tests/test_classroom_board_lock.py |
| 课堂学生练习与周末课家长反馈 | /v1/weekend-practice、/v1/weekend-brief、/v1/weekend-report | weekend_practice.py、weekend_scoring_views.py、weekend_report_views.py | 学生按课堂环节作答；教师生成反馈；关联家长只读孩子已发布报告 | 学生/教师会话、课堂及关系授权 | tests/test_weekend_written.py, tests/test_weekend_reports.py, tests/test_weekend_feedback_upgrade.py |
| 知识点讲解与知识地图 | /v1/knowledge、/v1/knowledge-map、/v1/my-knowledge-map | kp_cards_views.py、knowledge_map_views.py、knowledge_map_student.py | 教师查看知识点及诊断并布置；学生只读本人知识进展 | KNOWLEDGE_MAP=1（地图）；既有题库、作答和会话 API | tests/test_knowledge_map_draft_note_ui.py, tests/test_v1_student_practice.py |
| 应试专项、模拟卷、报告 | /v1/exam-prep、/v1/exam-paper、/v1/exam-report | exam_prep_views.py → exam_prep_pages.py | 教师准备专项与测验；学生完成模拟；学生/家长按发布授权查看报告 | 题库、现有测验记录和角色范围 API | tests/test_question_type_fit_and_quiz_navigation.py, tests/test_student_quiz_learning_points_ui.py |
| 课堂审核、执行、邀课和随堂测验 | /v1/classroom-review、/v1/classroom-execution、/v1/classroom-invitations、/v1/classroom-quick-checks | v1_classroom_review.py、v1_classroom_execution.py、v1_classroom_quick_check.py | 教师审核讲义、执行课堂、邀请学生；学生参与邀请与随堂测验 | 角色授权、课堂 session、发布版讲义及原有答题 API | tests/test_classroom_quick_login.py, tests/test_classroom_quick_check_phase_c.py, tests/test_classroom_live_board.py |
| 课堂讲义发布与学生读取 | /v1/classroom-handouts | v1_classroom_handout_release.py → 共享 V1 shell | 教师发布冻结讲义；学生只读本人作为接收人的当前发布版本 | 课堂归属、作业接收人及当前讲义版本校验 | tests/test_classroom_handout_release.py |
| 角色实操沙盒 | /v1/training、/v1/training-sandbox/{session_id} | v1_training_workbench.py、v1_training_sandbox.py | 老师、学生、家长或管理员在隔离虚拟业务数据中按角色完成流程 | 沙盒 session，不向正式学生教学记录写入 | tests/test_v1_training_sandbox.py |
| 产品反馈与审核记录 | /v1/feedback、/v1/product-feedback/... | v1_product_assistant.py | 反馈提交者查看本人反馈；维护者查看授权的审核及处理上下文 | 当前账号角色、反馈记录所有权 | tests/test_v1_product_assistant.py, tests/test_product_assistant_feedback_records_navigation.py |
| 个人工作室与账号辅助页 | /start、/parent-accounts、/teacher/ai-settings、/signup | app_v924.py | 独立教师注册和工作台；教师管理家长绑定及本人 AI 设置 | 登录、所属工作室与角色检查 | tests/test_personal_start.py, tests/test_personal_parent_accounts.py, tests/test_personal_ai_settings.py, tests/test_personal_signup.py |
| 法律、离线与运营支持页 | /legal/privacy、/legal/terms、/offline、/operator-console | app_v924.py | 访客阅读政策、离线说明；运维人员进入运营控制台 | 政策公开；运营功能依现有密钥与管理员校验 | tests/test_prelaunch_legal_readiness.py, tests/test_offline_page.py, tests/test_operator_console_route.py |


## 需要单独梳理的辅助入口

- `/operator-console` 页面测试为 `tests/test_operator_console_route.py`；运营鉴权还由应用现有密钥与管理员校验执行。
- `/parent-accounts`、`/teacher/ai-settings`、`/signup` 是根应用内嵌模板；对应测试分别为 `tests/test_personal_parent_accounts.py`、`tests/test_personal_ai_settings.py`、`tests/test_personal_signup.py`。
- `/offline` 是静态提示页。9 个 `/fresh-v*` 版本入口共用旧版包，需继续按兼容用途检查链接及调用关系。
