# 长缨辅学文档地图（INDEX）

> 这是所有文档的入口。人和 AI Agent 都从这里开始，不要靠猜。
> 新增或移动文档时，同步更新本文件。

## 0. 进入仓库先读这三个

| 顺序 | 文档 | 为什么 |
|---|---|---|
| 1 | [`AGENTS.md`](../AGENTS.md) | 工程规则、边界、状态机、受保护路径、完成定义 |
| 2 | 本文件 `docs/INDEX.md` | 文档地图：哪类知识在哪 |
| 3 | GitHub Issue #174 | 当前工程断点（main SHA / PR / 部署 / 验收状态） |

## 1. 产品与范围

| 文档 | 内容 | 什么时候读 |
|---|---|---|
| [`V1_SCOPE.md`](V1_SCOPE.md) | V1 产品范围、角色、数据衔接、家长—学生关联 | 写需求、判断"这个功能属于 V1 吗"之前 |
| [`V1_FREEZE.md`](V1_FREEZE.md) | V1 冻结基线：哪些结构不再扩张、后续只做缺陷/安全/已验证能力 | 想新增结构或"顺便做全"之前 |
| [`README.md`](../README.md) | 项目定位、生产入口、代码结构速览 | 第一次接触项目 |

## 2. 架构与生产运行

| 文档 | 内容 |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 代码结构与模块化路线、生产启动链、legacy 兼容桥 |
| [`AGENTS.md`](../AGENTS.md) §2 | 生产事实与验收口径（deploy=live、`/health` 200、`/v1` 200） |
| `render.yaml` | Render 服务定义（**受保护**，不要随意修改） |

## 3. 工程流程与 Harness

| 文档 | 内容 |
|---|---|
| [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) | 控制平面设计：可恢复、可验证、可追踪 |
| [`AGENTS.md`](../AGENTS.md) §3–§8 | 固定执行协议、并行与恢复规则、C2 服务层规则、反空壳规则、完成定义 |

## 4. 功能设计与分析（未实现或待评审）

| 文档 | 内容 | 状态 |
|---|---|---|
| [`analysis/after-school-homework-assistant.md`](analysis/after-school-homework-assistant.md) | 晚托作业助手 MVP 设计 | 设计，未写代码 |
| [`training-sandbox-plan.md`](training-sandbox-plan.md) | 角色实操沙盒实施方案 | 方案 |
| [`weekend-course/1-现状核对.md`](weekend-course/1-现状核对.md) | 周末课：可复用能力盘点 | 设计稿 |
| [`weekend-course/2-数据设计稿.md`](weekend-course/2-数据设计稿.md) | 周末课：新增表设计（均带 school_id） | 设计稿 |
| [`weekend-course/3-口径文档.md`](weekend-course/3-口径文档.md) | 周末课：指标口径（完成率 / 提示依赖 / 进步分） | 默认值，上课后调 |

## 5. 历史与验收记录

| 文档 | 内容 |
|---|---|
| [`freeman-v071-agent-green-acceptance.md`](freeman-v071-agent-green-acceptance.md) | Freeman Agent V0.7.1 自主工程闭环验收说明 |

## 6. 新增文档放哪里

| 你要写的东西 | 放哪 |
|---|---|
| 产品范围变化 | 改 `docs/V1_SCOPE.md`，不新建平行文档 |
| 架构决策 | 改 `docs/ARCHITECTURE.md`（`docs/adr/**` 属受保护路径，按 §7 处理） |
| 单个功能的设计 | `docs/analysis/<feature>.md` |
| 指标体系/口径 | 对应业务目录，如 `docs/weekend-course/3-口径文档.md` |
| 临时笔记、草稿 | **不要进仓库**，留在本地；定稿后再 PR |

## 7. 维护规则

1. **`docs/` 是唯一事实来源**；本地副本一律视为草稿。
2. 新增/移动/删除文档时，**同步更新本 INDEX**。
3. 受保护路径（`.github/**`、`GOVERNANCE.md`、`docs/adr/**`、`render.yaml`、`Dockerfile`、数据库迁移、环境变量）不适用上面的约定，按 [`AGENTS.md`](../AGENTS.md) §7.5 处理。
4. 文档里引用代码位置时，写清楚 `文件:行号`；引用事实时区分"已核实"和"未确认"。
