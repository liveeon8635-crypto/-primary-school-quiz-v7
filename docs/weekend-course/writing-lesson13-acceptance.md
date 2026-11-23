# 第 13 次作文课本地验收记录

2026-11-23；分支 `codex/weekend-writing-lesson13`；基线 `49ca5b9869d0ef1f5a7100548119908ac20fb2de`。仅使用隔离 SQLite 数据库，不连接生产库、不部署。

## 原件和补图

- 只读工作副本：`C:\Users\14228\Documents\Codex\2026-11-23\13-yaml-c-users-14228-gemini\work\lesson13.docx`；SHA-256 `5D936241C28ABE1141E465C24D95DDB445B0810DDFB694A407D9699281DE0635`。测试在导入前后校验哈希相同。
- 完整提取：56 个文字节点、1 张五行观察表、11 张 PNG。核对《醉美秋天》《春归万物苏》、观察顺序、感官、修辞、动静结合和“我最喜欢的季节”主题。11 张原件图片逐张制成联系表并查看，内容是审题、景物清单及写作方法图；导入后保持待确认。
- `assets/writing_lesson13/` 四张插画是依据原件文字生成的新素材，文件名标明“AI生成”。三张对应《醉美秋天》的果园、麦田、银杏段；一张用于春景看图写话。它们不是原件图片，也不是学生真实作文照片。
- 可直接上传的 `第13次-我最喜欢的季节-作文课导入包.json` 保存于本次工作区 `outputs/`；它包含原件内容与四张补图，并保留声明来源、五行表格和图文绑定建议。JSON 导入仍将素材置于待确认状态，需教师逐项核对。操作说明在同目录。

## 真实教案链路

`tests/test_writing_workflow.py` 使用原件导入并验证缺图阻断；随后经教师接口上传四张补图、绑定三处范文图文关系、确认范文/方法/主题、忽略未用于课堂的原件素材，审核通过后创建课堂。学生接口在开放前返回空节点；教师开放主题后，模拟学生上传一张 JPEG，另一名同班学生无法看到该提交；教师记录箭头批注、保存反馈草稿并发布，学生与已关联家长仅在发布后看到反馈。该测试验证接口和本地页面，不等同于对教师教学内容的人工终审或实体手机拍照。

## 测试

先设置 `PYTHONUTF8=1`、`WRITING_LESSON13_DOCX` 为上述只读副本；浏览器测试设置 `PLAYWRIGHT_BROWSERS_PATH` 为本地 Chromium 目录。

| 命令 | 实际结果 |
| --- | --- |
| `python -m pytest tests/test_writing_workflow.py tests/test_weekend_views.py tests/test_weekend_written.py tests/test_weekend_course_types.py tests/test_chinese_readiness.py tests/test_weekend_bundle_import.py tests/test_weekend_reports.py tests/test_weekend_open_gate.py -q -p no:cacheprovider` | 38 通过、0 失败、5 条 Python/SQLAlchemy 弃用警告（运行于新增浏览器与补图测试之前） |
| `python -m pytest tests/test_writing_workflow.py -q -p no:cacheprovider` | 5 通过、0 失败（含原件补图链路及 Chromium 页面渲染） |
| `python -m pytest tests/test_writing_workflow.py::test_writing_workbench_and_classroom_render_in_browser -q -p no:cacheprovider` | 1 通过、0 失败（最后一次页面修改后重跑） |
| `python -m pytest tests/test_writing_workflow.py -q -p no:cacheprovider`（后续沙箱会话） | 4 通过、2 跳过；两项 Chromium 测试因 Windows 命名管道返回 WinError 5，未计为通过 |
| `python -m pytest tests/test_writing_workflow.py::test_lesson13_bundle_import_retains_sources_tables_and_review_gate -q -p no:cacheprovider` | 1 通过、0 失败；真实 JSON 整包经站内导入入口验证，74 项素材、15 张图片、五行表格及审核门槛保留 |
| `PYTHONUTF8=1 HARNESS_BASE_SHA=49ca5b9869d0ef1f5a7100548119908ac20fb2de python scripts/harness_guard.py` | 通过 |
| `git diff --check` | 通过 |

先前浏览器检查使用真实生成的作文备课和课堂 HTML，在 Chromium 的 390×844 视口分别打开教师审核、教师课堂和学生课堂；检查六环节、缺项提示、图文环节切换、拍照/多图控件以及横向溢出。截图保存在本次工作区 `outputs/`，不含真实学生数据。后续新增了备课工作栏的浏览器断言，但当前 Windows 沙箱拒绝启动 Chromium 的命名管道，尚未实际执行该页面的浏览器检查；本条不能算通过。尝试以无沙箱方式启动浏览器被自动审批拒绝，理由是会绕过先前的沙箱限制；后续没有继续尝试绕过。

## 使用前人工核对

教师仍需逐张核对 AI 补图是否适合教学、核对《醉美秋天》原件中因 Word 排版而拆成多行的自然段、决定是否采用《春归万物苏》作为第二范文或仅作看图参考。备课工作栏浏览器检查、旧 iPad/Safari 的实体设备操作和生产环境行为未在本次本地验收中执行。
