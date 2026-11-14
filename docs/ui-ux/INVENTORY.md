# 页面资产清单

基线 `d9b56caff452abfc57b9378df9051738ffae57ad`。启动生产入口，使用隔离 SQLite，通过注册路由和真实 HTTP 响应盘点。参数化路由和开关关闭的页面需结合对应身份与夹具核对。

| 页面 | 路由 | 注册来源 | 基线 HTTP | 样式 / 脚本标签 | 依赖 |
|---|---|---|---|---|---|
| 我的工作室 · 长缨辅学 | `/start` | `app_v924.py:4918` | 200 | 1 / 1 | get_db |
| 家长账号 · 长缨辅学 | `/parent-accounts` | `app_v924.py:5173` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 我的 AI 设置 · 长缨辅学 | `/teacher/ai-settings` | `app_v924.py:5281` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 免费注册 · 长缨辅学 | `/signup` | `app_v924.py:5292` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 长缨辅学｜商业运营控制台 | `/operator-console` | `app_v924.py:5470` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 隐私政策 - 长缨辅学 | `/legal/privacy` | `app_v924.py:5547` | 200 | 1 / — | 由模板脚本加载会话或公开 |
| 用户协议 - 长缨辅学 | `/legal/terms` | `app_v924.py:5550` | 200 | 1 / — | 由模板脚本加载会话或公开 |
| 长缨辅学 · 离线模式 | `/offline` | `app_v924.py:9104` | 200 | 1 / — | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v820` | `app_v924.py:9431` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v770` | `app_v924.py:9434` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v761` | `app_v924.py:9437` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v760` | `app_v924.py:9440` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v752` | `app_v924.py:9443` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v751` | `app_v924.py:9446` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v750` | `app_v924.py:9449` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v740` | `app_v924.py:9452` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 长缨辅学 V10.7 | `/fresh-v730` | `app_v924.py:9455` | 200 | 2 / 4 | 由模板脚本加载会话或公开 |
| 经典版入口 | `/classic` | `app_v924.py:9428` | 307 | — / — | 由模板脚本加载会话或公开 |
| 产品首页入口 | `/` | `changying/web/product_shell.py:178` | 307 | — / — | 由模板脚本加载会话或公开 |
| 长缨辅学｜小学托管与教学 | `/new` | `changying/compat/legacy.py:201` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 长缨辅学｜小学托管与教学 | `/workbench` | `changying/compat/legacy.py:201` | 200 | 1 / 1 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/classroom-review` | `changying/web/v1_classroom_review.py:665` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/classroom-execution` | `changying/web/v1_classroom_execution.py:1056` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/classroom-invitations` | `changying/web/v1_classroom_execution.py:1056` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/classroom-quick-checks` | `changying/web/v1_classroom_quick_check.py:939` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 互动课堂实时大屏 | `/v1/classroom-board/{sid}` | `changying/web/v1_classroom_live_board.py:414` | 参数化 | — / — | 由模板脚本加载会话或公开 |
| 知识点讲解 | `/v1/knowledge` | `changying/web/kp_cards_views.py:123` | 200 | 1 / 2 | 由模板脚本加载会话或公开 |
| 周末课 | `/v1/weekend` | `changying/web/weekend_views.py:240` | 200 | 1 / 3 | 由模板脚本加载会话或公开 |
| 课堂大屏 | `/v1/weekend-board` | `changying/web/weekend_views.py:244` | 200 | 1 / 3 | 由模板脚本加载会话或公开 |
| 课堂练习 | `/v1/weekend-practice` | `changying/web/weekend_practice.py:265` | 200 | 1 / 2 | 由模板脚本加载会话或公开 |
| 周末课学情反馈 | `/v1/weekend-brief` | `changying/web/weekend_scoring_views.py:570` | 200 | 1 / 2 | 由模板脚本加载会话或公开 |
| 课后总结与家长反馈 | `/v1/weekend-report` | `changying/web/weekend_report_views.py:222` | 200 | 1 / 2 | 由模板脚本加载会话或公开 |
| 周末课备课 | `/v1/weekend-plan` | `changying/web/weekend_plan_views.py:483` | 200 | 1 / 3 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/classroom-handouts` | `changying/web/v1_classroom_handout_release.py:591` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 · 角色实操沙盒 | `/v1/training` | `changying/web/v1_training_workbench.py:468` | 200 | 1 / 2 | 由模板脚本加载会话或公开 |
| 我的反馈记录 · 长缨辅学 | `/v1/feedback` | `changying/web/v1_product_assistant.py:1039` | 200 | 1 / 3 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1` | `changying/web/v1.py:336` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/workspace` | `changying/web/v1.py:302` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/student` | `changying/web/v1.py:302` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/history` | `changying/web/v1.py:302` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/transition` | `changying/web/v1.py:302` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 长缨辅学 V1 | `/v1/guide` | `changying/web/v1.py:302` | 200 | 19 / 27 | 由模板脚本加载会话或公开 |
| 全部功能 · 长缨辅学 | `/v1/tool` | `changying/web/v1_classic_gzip_embed.py:104` | 200 | 2 / 3 | 由模板脚本加载会话或公开 |

## 角色、操作与验证

| 入口 | 角色与操作 | 运行依赖与现有测试 |
|---|---|---|
| V1 工作台、学生档案、往期、衔接 | 教师工作模式切换，查看班级与连续档案 | `v1.py` 与兼容补丁，`/session`、`/teacher/students/{id}/growth-profile`。固定导航、移动真实数据、学生连续档案测试。 |
| 全部功能与旧版 | 四种角色按可用入口进入。原生功能列表由 gzip 兼容桥送达，具体工具经同页跳转进入 Classic，历史 iframe 路径继续存在 | `v1_tool_hub.py`、`v1_unified_tools.py`、Classic 会话桥。已有 iframe bootstrap、跨窗口交接和授权契约测试。 |
| 晚托 | 教师发清单、审阅求助，学生处理作业与求助 | `homework_assistant.py` 与 `homework_assistant_pages.py`，`/session` 与晚托业务路由。已有清单、权限、引导和教师求助测试。 |
| 周末备课、控制、大屏、练习、报告 | 教师备课审核、开课、推进与发布，学生练习和家长读取授权报告 | `weekend_pages.py` 与课程课件、纸质备用、作答和报告模块。已有周末课课程、班级绑定、作答、报告与直播大屏测试。 |
| 学生、家长、管理 | 学生作答与复习、家长按授权查看、管理员账号维护 | V1 shell 与 Classic 功能工作区，角色与数据范围由对应 API 判断。已有家长可见性、学生练习和账号权限测试。 |

## 功能开关开启时的入口

隔离环境启用 `HOMEWORK_ASSISTANT=1` 与 `KNOWLEDGE_MAP=1`。

| 页面 | 路由 | 注册来源 | HTTP |
|---|---|---|---|
| 晚托作业助手 | `/v1/homework` | `changying/web/homework_assistant.py:202` | 200 |
| 知识地图 | `/v1/knowledge-map` | `changying/web/knowledge_map_views.py:240` | 200 |
| 我的知识地图 | `/v1/my-knowledge-map` | `changying/web/knowledge_map_student.py:155` | 200 |
| 应试专项 | `/v1/exam-prep` | `changying/web/exam_prep_views.py:361` | 200 |
| 限时模拟卷 | `/v1/exam-paper` | `changying/web/exam_prep_views.py:367` | 200 |
| 考试提分报告 | `/v1/exam-report` | `changying/web/exam_prep_views.py:373` | 200 |
