# 长缨辅学文档地图（INDEX）

> 这是所有文档的入口。人和 AI Agent 都从这里开始，不要靠猜。
> 新增或移动文档时，同步更新本文件。

## 0. 进入仓库先读这三个

| 顺序 | 文档 | 为什么 |
|---|---|---|
| 1 | [`AGENTS.md`](../AGENTS.md) | 工程规则、边界、状态机、受保护路径、完成定义 |
| 2 | 本文件 `docs/INDEX.md` | 文档地图：哪类知识在哪 |
| 3 | GitHub Issue #174 | 当前工程断点（main SHA / PR / 部署 / 验收状态） |

## 0.5 产品维护者从这里开始

| 文档 | 内容 |
|---|---|
| [`maintainer/README.md`](maintainer/README.md) | **产品全景与维护指南**：产品原则、各模块怎么连、改一处影响哪里、风险分级、怎么和 AI 合作、当前状态、学习路线。写给不写代码的产品维护者；agent 处理维护者需求前也先读（`AGENTS.md` §9） |

## 1. 产品与范围

| 文档 | 内容 | 什么时候读 |
|---|---|---|
| [`V1_SCOPE.md`](V1_SCOPE.md) | V1 产品范围、角色、数据衔接、家长—学生关联 | 写需求、判断"这个功能属于 V1 吗"之前 |
| [`V1_FREEZE.md`](V1_FREEZE.md) | V1 冻结基线：哪些结构不再扩张、后续只做缺陷/安全/已验证能力 | 想新增结构或"顺便做全"之前 |
| [`analysis/claude-handoff-review-2026-11.md`](analysis/claude-handoff-review-2026-11.md) | 外部交接包的核对结论：学校教学场景与权限、失效引用的现行落点、三脑评审的适用范围 | 引用历史交接资料、或看到"GOVERNANCE.md / PROJECT_STATE / 三脑必须"这类说法时 |
| [`README.md`](../README.md) | 项目定位、生产入口、代码结构速览 | 第一次接触项目 |

## 2. 架构与生产运行

| 文档 | 内容 |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 代码结构与模块化路线、生产启动链、legacy 兼容桥 |
| [`ops/runbook.md`](ops/runbook.md) | 生产运维手册：应用回滚、数据回滚、备份恢复、故障处理、变更前检查清单 |
| [`AGENTS.md`](../AGENTS.md) §2 | 生产事实与验收口径（deploy=live、`/health` 200、`/v1` 200） |
| `render.yaml` | Render 服务定义（**受保护**，不要随意修改） |

## 3. 工程流程与 Harness

| 文档 | 内容 |
|---|---|
| [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) | 控制平面设计：可恢复、可验证、可追踪 |
| [`AGENTS.md`](../AGENTS.md) §3–§8 | 固定执行协议、并行与恢复规则、C2 服务层规则、反空壳规则、完成定义 |

## 4. 功能：现状与设计

| 文档 | 内容 | 状态 |
|---|---|---|
| [`analysis/knowledge-map.md`](analysis/knowledge-map.md) | 知识地图：单元/知识点/前置关系 + 题目分档 + 学生诊断 | **已上线**（`KNOWLEDGE_MAP=1`） |
| [`analysis/courseware-reuse.md`](analysis/courseware-reuse.md) | 课程资料复用：批量导入 / 课程模板 / 跨校复制 | A、B 已上线；C 待权限模型 |
| [`analysis/after-school-homework-assistant.md`](analysis/after-school-homework-assistant.md) | 晚托作业助手 MVP 设计 | **已接入代码，待真实业务验收**（开关、题库和师生流程需现场核对） |
| [`training-sandbox-plan.md`](training-sandbox-plan.md) | 角色实操沙盒实施方案 | 方案 |
| [`weekend-course/1-现状核对.md`](weekend-course/1-现状核对.md) | 周末课：可复用能力盘点 | 设计稿 |
| [`weekend-course/2-数据设计稿.md`](weekend-course/2-数据设计稿.md) | 周末课：新增表设计（均带 school_id） | 设计稿 |
| [`weekend-course/3-口径文档.md`](weekend-course/3-口径文档.md) | 周末课：指标口径（完成率 / 提示依赖 / 进步分） | 默认值，上课后调 |

## 5. 历史与验收记录

| 文档 | 内容 |
|---|---|
| [`freeman-v071-agent-green-acceptance.md`](freeman-v071-agent-green-acceptance.md) | Freeman Agent V0.7.1 自主工程闭环验收说明 |
| [`analysis/product-inventory-2026-11-04.md`](analysis/product-inventory-2026-11-04.md) | 2026-11-04 全站功能盘点快照（基线 `3809ca0`；区分“已接入”和“已验收”，并列出文档滞后项） |

## 6. 新增文档放哪里

| 你要写的东西 | 放哪 |
|---|---|
| 产品范围变化 | 改 `docs/V1_SCOPE.md`，不新建平行文档 |
| 架构决策 | 改 `docs/ARCHITECTURE.md`（`docs/adr/**` 属受保护路径，按 §7 处理） |
| 单个功能的设计 | `docs/analysis/<feature>.md` |
| 模块功能、入口、规则或现状有变化 | 同步更新 `docs/maintainer/README.md` 对应小节（`AGENTS.md` §9.7） |
| 指标体系/口径 | 对应业务目录，如 `docs/weekend-course/3-口径文档.md` |
| 临时笔记、草稿 | **不要进仓库**，留在本地；定稿后再 PR |

## 7. 维护规则

1. **`docs/` 是唯一事实来源**；本地副本一律视为草稿。
2. 新增/移动/删除文档时，**同步更新本 INDEX**。
3. 受保护路径（`.github/**`、`GOVERNANCE.md`、`docs/adr/**`、`render.yaml`、`Dockerfile`、数据库迁移、环境变量）不适用上面的约定，按 [`AGENTS.md`](../AGENTS.md) §7.5 处理。
4. 文档里引用代码位置时，写清楚 `文件:行号`；引用事实时区分"已核实"和"未确认"。

## 8. UI/UX 施工

- [页面资产](ui-ux/INVENTORY.md)、[依赖](ui-ux/DEPENDENCY_MAP.md)、[风险](ui-ux/RISK_REGISTER.md)、[基线](ui-ux/BASELINE.md)、[实施](ui-ux/IMPLEMENTATION_PLAN.md)、[设计决策](ui-ux/DESIGN_DECISIONS.md)。
