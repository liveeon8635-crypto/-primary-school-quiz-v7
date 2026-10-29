# 知识地图（教师端 + 学生端）

- 日期：2026-10-27 ｜ 状态：**已在生产启用**（`KNOWLEDGE_MAP=1`）
- 整理自代码，标注同 `docs/INDEX.md` 的约定

## 1. 它是什么

一份「单元 → 知识点 → 前置关系」的结构，加上**每个知识点的题目分档**（基础 / 中等 / 提高）。教师维护草稿，**发布后**学生才看得到。

一个（学校, 年级, 学科, 学期）一份地图，同校老师共享同一份。

## 2. 开关与可见性

| 项 | 行为 |
|---|---|
| 环境变量 `KNOWLEDGE_MAP` | 默认**关闭**；关闭时 `/knowledge-map/*` 等路由返回 **404** |
| 生产现状 | `KNOWLEDGE_MAP=1`，`GET /knowledge-map/config` → `{"enabled":true}` |
| 草稿 vs 已发布 | 编辑草稿**不影响**学生；只有 publish 后学生端才更新 |
| 写权限 | **只有教师能写**；学生只读已发布副本 |

## 3. 数据模型

地图本身是**一个 JSON 文档**：

```json
{"version": 1,
 "units": [{"key":"U1","name":"观察简单组合体","kind":"unit|activity|review","learned":true}],
 "nodes": [{"key":"1-1","unit":"U1","name":"...","detail":"...","kind":"core|optional|display|review",
            "prereqs":["..."],"bankKeys":["..."],"levels":{"<question id>":"basic|medium|hard"},
            "enabled":false}]}
```

约束（`changying/services/knowledge_maps.py`）：

| 常量 | 值 | 含义 |
|---|---|---|
| `MAX_UNITS` | 20 | 单元上限 |
| `MAX_NODES` | 120 | 知识点上限 |
| `MIN_PER_NODE` | 6 | 每个知识点最少题数 |
| `MIN_PER_LEVEL` | 2 | 每档最少题数 |

节点类型：`core` 必学 / `optional` 选学 / `display` **只展示（永不出题）** / `review` 综合。

数据表（启动 `create_all` 加性创建）：

| 表 | 用途 | 清理脚本分类 |
|---|---|---|
| `knowledge_maps` | 地图 JSON + revision + 发布状态 | KEEP |
| `knowledge_map_ratings` | 教师对每个学生/单元的自己判断 | DELETE（活动数据） |
| `knowledge_map_runs` | 学生 12 题诊断的运行记录 | DELETE（活动数据） |

## 4. 教师流程

1. `GET /teacher/knowledge-maps` — 本校地图 + 尚未使用的模板
2. `POST /teacher/knowledge-maps` — 从模板建草稿（内置模板 `RJ2026_G5_MATH_UP`，人教版 2026 五上数学）
3. `PUT /teacher/knowledge-maps/{mid}` — 保存草稿（带 revision 校验，防并发覆盖）
4. 给每个知识点配题：
   - `GET .../nodes/{key}/questions` — 按知识点名匹配题库
   - `GET .../bank?unit=&q=` — 按单元/关键词从题库挑题（**不要求知识点名一致**）
   - `POST .../nodes/{key}/ai` — AI 出题草稿（混合题型；按单元选考法：计算 / 图形 / 可能性；数学答案按算式验算），老师审核后存入题库
   - `POST .../nodes/{key}/visual` — 系统画图题（只限有图形的知识点）
   - `PUT .../nodes/{key}/levels` — 分档
5. `POST .../units/{ukey}/restore` — 一键恢复该单元模板里缺失的知识点
6. `POST .../publish` — 发布（学生端才更新）
7. `GET .../classes/{cid}` — 班级掌握度
8. `POST .../classes/{cid}/reinforce` — 给选中学生在薄弱节点生成**一键巩固作业**
9. `PUT .../classes/{cid}/ratings` — 教师自评，班级视图会报告「教师判断与地图的一致度」

## 5. 学生流程

1. `GET /student/knowledge-map` — 已发布地图 + 每节点掌握度 + 诊断状态
2. `POST /student/knowledge-map/diagnosis` — 开始/继续 12 题诊断（返回的题**不含答案**）
3. `POST /student/knowledge-map/diagnosis/submit` — 提交，用**现有判分引擎**批改并保存为一次练习提交
4. `POST /student/knowledge-map/nodes/{key}/quiz` — 某个知识点的 3～5 题小测（随时可做，只出没做过的题）
5. `POST /student/knowledge-map/nodes/{key}/quiz/submit` — 提交小测，同样保存为一次练习提交（标题「知识地图小测：编号 名称」）

入口：学生首页「我的知识地图」卡片；周末课课堂练习页（`/v1/weekend-practice`）顶部——未做诊断时显示「课前诊断」，做完后显示「课后补测」。

## 6. 代码位置

| 文件 | 行数 | 作用 |
|---|---|---|
| `changying/services/knowledge_maps.py` | ~358 | 地图模型、校验、内置模板 |
| `changying/web/knowledge_map_views.py` | ~528 | 教师端路由（15 条） |
| `changying/web/knowledge_map_pages.py` | ~446 | 教师端页面 JS |
| `changying/web/knowledge_map_student.py` | ~179 | 学生端路由（3 条） |
| `changying/web/homework_knowledge_views.py` | ~121 | 晚托作业助手的知识记录只读视图 |

测试：`tests/test_knowledge_maps.py`、`tests/test_knowledge_map_student.py`、
`tests/test_grade5_knowledge_modules_textbook_edition.py`、`tests/test_homework_knowledge_views.py`。

## 7. 边界

- 学生端只有 5 条路由（读地图 / 开始、提交诊断 / 开始、提交小测），不返回班级或他人数据（见 `knowledge_map_student.py`）
- 学生**看不到**草稿；只有 `publish` 之后才是学生可见的副本
- `display` 类节点只展示，**不参与出题与诊断**
- 关闭开关即整体下线（404），不需要改数据

## 8. 运维

- **开启**：Render 环境变量 `KNOWLEDGE_MAP=1` → 重新部署
- **关闭**：设为 `0` 或删除 → 重新部署（数据保留）
- 清理脚本 `scripts/prelaunch_data_cleanup.py` 已把三张表正确分类，新表不会漏删或误删

## 9. 页面交互

**教师端 `/v1/knowledge-map`**（`KNOWLEDGE_MAP_JS`）
- 左侧单元导航，右侧单元卡片；每个知识点一行，点开后看说明、前置、题目覆盖（各档题数）。
- 知识点上的操作：编辑（名称、说明、前置编号）、题目分档（按知识点名匹配 / 从题库挑题）、AI 出题、生成图形题。
- AI 出题：选难度、题型、数量、可选参考资料 → 草稿卡片显示题型、考法、「已验算」或「答案待核对」→ 老师逐题修改、勾选 → 「存入题库并分为某档」。
- 发布按钮把草稿复制为学生可见版本；班级视图里看全班颜色表、一键巩固、记录自己的判断。

**学生端 `/v1/my-knowledge-map`**（`STUDENT_MAP_JS`）
- 顶部入门诊断卡（开始 / 继续 / 已完成）；中间 SVG 地图：单元区块 + 知识点圆点 + 前置连线（跨单元连线只在选中时显示）。
- 圆点颜色：绿 熟练、蓝 达标、红 薄弱、空心灰 证据不足、虚线 未学或未开启、紫 只展示。
- 点知识点：显示掌握情况（加权正确率、依据几题、可信度）、先学 / 接着学；学过的知识点有「做 3～5 题小测」按钮，没有新题时提示等老师补题。
- 诊断和小测都在页面里作答，选择题点选、其余填写；交卷前检查漏题；交卷后地图立即重画。

## 10. 诊断题与小测题从哪里来

- **只用分好档的题**：题目必须出现在已发布地图某个知识点的 `levels` 里，并且属于本校。
- **可以出现在诊断 / 小测里的题**：能自动判分的题型；不在学生未完成的正式作业里（避免提前泄题）；带图的题只限页面能画的图（照片、系统画图的立体图、方格图、可能性图）。
- **入门诊断**（每个学生每份地图一次，`knowledge_map_runs` 记一行）：12 题，按已学单元里参与诊断的知识点数分配名额，每个单元至少 1 题；单元内知识点轮流取题，每个知识点优先中等、其次基础、最后提高，优先学生没做过的题；可用题少于 6 道时不开放。
- **知识点小测**（不建表）：只出该知识点里学生从没做过的题，基础 → 中等 → 提高轮流，最多 5 题；少于 3 道新题时不开放。交卷时服务器按同一规则重算题目，必须与学生作答的题完全一致，所以每道题都是第一次作答，交两次会被拒绝。
- **更新**：老师给知识点补题、调档并重新发布后，学生端下次打开即按新题计算；已有作答记录不受影响。

## 11. 掌握度口径（`node_mastery`，每次查看时现算，不另存）

- **只算第一次作答**：学生在任何提交（作业、练习、诊断、小测、巩固作业）里对某题的第一次作答；以后再做同一题不改变结论。
- **权重**：基础 1、中等 1.5、提高 2；得分 = Σ(权重 × 对错) ÷ Σ权重。
- **三档**：薄弱 < 0.6，达标 0.6～0.85，熟练 > 0.85。
- **证据量**：少于 3 题 → 证据不足（不下结论）；3～4 题 → 初步；5 题及以上 → 可信。页面始终显示依据几题。
- **单元掌握度**：把该单元所有参与诊断的知识点的题合在一起，用同一公式计算。
- **教师一致率**：班级视图里老师对每个学生、每个单元给出自己的判断；只比较地图已下结论（非证据不足）的格子，目标 ≥ 80%。
