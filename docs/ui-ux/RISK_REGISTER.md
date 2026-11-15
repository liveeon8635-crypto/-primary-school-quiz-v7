# UI/UX 改造风险与证据

| 风险项 | 影响范围 | 已采取保护 | 已有验证证据 | 状态 / 下一步 |
|---|---|---|---|---|
| V1 多层 HTML 包装漏挂样式或改变脚本顺序 | `/v1*`、gzip 兼容桥、Classic | 仅经 `apply_surface()` 给最终 HTML 添加属性及 CSS；保留 ID、脚本和 `CHANGYING_UI_REFRESH=0` 回滚 | `tests/test_v1_shell_router_contract.py`, `tests/test_v1_classic_embed_bootstrap.py`, `tests/test_ui_surface_refresh.py` | 部分控制；仍需在真实浏览器检查最终 DOM 和登录/身份切换 |
| Token 认证交接失效或 iframe 页面受影响 | `/v1/tool`, `/classic` 及旧版嵌入页 | 不删除 iframe，不修改认证或 API 契约；CSS 使用页面命名空间 | `tests/test_v1_cross_context_auth_handoff.py`, `tests/test_v1_unified_tools_session_bridge.py` | 定向回归已覆盖；全角色真实浏览器流程待执行 |
| 教师答案提前向学生或大屏公开 | 周末课程、大屏、课堂讲义 | 不变更状态机或接口；只做投影布局、可滚动区域和焦点保护 | `tests/test_weekend_live_controls.py`, `tests/test_classroom_live_board.py`, `tests/test_classroom_board_lock.py`, `tests/test_classroom_handout_release.py` | 代码回归部分覆盖；课堂投影实测未完成 |
| 图片、题目顺序、数学分步过程被裁切或错配 | 周末备课、讲义、纸质备用 | 不改题目排序/图片关联/业务数据；保留容器完整滚动，不以隐藏内容解决溢出 | `tests/test_weekend_import_integrity.py`, `tests/test_weekend_example_practice_separation.py`, `tests/test_weekend_board_layout.py` | 尚缺教师现场投影及打印纸张逐题核验 |
| 学生/家长数据越权或跨学生泄露 | 学生档案、成绩、作业、家长报告 | 不改权限 API；CSS 不承载数据筛选；复用现有角色关系 | `tests/test_role_permission_matrix.py`, `tests/test_v1_guardian_runtime_registration.py`, `tests/test_v1_guardian_visibility.py`, `tests/test_student_continuity.py`, `tests/test_guardian_visibility.py` | 定向权限测试通过；全流程 UI 端到端未完成 |
| 账号、家长绑定或 AI Key 页面展示改造影响操作 | `/parent-accounts`, `/teacher/ai-settings`, `/signup` | 仅接入 scoped CSS；保留页面 DOM、接口、内联 JS、缓存头和注册校验 | `tests/test_personal_parent_accounts.py`, `tests/test_personal_ai_settings.py`, `tests/test_personal_signup.py`, `tests/test_ui_surface_refresh.py` | 本地测试通过；窄屏实机检查待做 |
| CSS 新样式造成窄屏横向溢出、控件遮挡或焦点不可见 | 全部已接入样式的页面 | 设置受限命名空间、44px 控件高度、明确焦点环；样式开关可回退 | `tests/test_ui_surface_refresh.py`, `tests/test_weekend_board_layout.py`; Playwright/Chromium 本地启动失败 | 静态与 DOM 测试部分通过；真实窄屏/平板视觉检查受容器限制 |
| Safari 12 不支持语法或渲染退化 | 旧 iPad 与旧版 Classic | 不碰旧版脚本资产；CSS 保留 `vh` fallback 后再声明 `dvh` | `tests/test_safari12_compat.py` 的脚本清单及构建检查 | 静态兼容校验可跑；Safari 12 实机未验证 |
| 加载性能指标恶化或误报提升 | 所有页面 | 区分隔离 TestClient 延时与现场 Web Vitals；不删除功能换指标 | `BASELINE.md` 记录受控环境响应大小和延时 | 真实 LCP/INP/CLS 缺失；待有真实浏览器运行器后测量 |
| 历史 URL/别名失效 | `/classic`、`/fresh-v*`、V1 入口 | 保留路由与 iframe；不删除旧版别名 | `INVENTORY.md` 记录 9 个旧版别名和 37 个 HTML 入口 | 链接和资源完整性还需专项扫查及旧设备验证 |
| CI/自动边界审查缺少执行器 | PR #1083 | PR 保持 draft；不改 `.github/**` 绕过门禁，不将无执行结果报告为通过 | 最新 head 的 guard job 返回 `runner_id=0`, `steps=[]`; 没有 CI run | 外部 runner 阻断；须取得运行器后重跑原门禁 |
| main/生产状态变化造成基线错配 | 全站改造 | 起始 main 和生产 revision 固定为 `d9b56caff452abfc57b9378df9051738ffae57ad`；不直接推 main 或部署 | `BASELINE.md` | 最终 exact-head 审查需重查主线与生产 revision |

不存在“全部风险已消除”的结论。浏览器现场、设备兼容、完整 CI 和管理端施工仍未通过验收。
