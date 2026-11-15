# 基线

GitHub main 与在线 revision 核对为 `d9b56caff452abfc57b9378df9051738ffae57ad`。本地重建文件树并校验 Git tree `b7cf46e50c45ad77e0f6e5ae67194b46a2e44a7b`，应用测试使用独立 SQLite。通过生产应用入口枚举 574 个路由注册项，含接口、别名、HTML 和框架路由。公开生产 GET 仅作为可达性证据。

路由盘点分两种开关状态：默认环境 `runtime-baseline.json` 记录 40 个 HTML 响应（含 9 个 `/fresh-v*` 历史别名）；隔离环境开启 `HOMEWORK_ASSISTANT=1` 与 `KNOWLEDGE_MAP=1` 后，`runtime-flags.json` 记录 46 个 HTML 响应，其中 37 个为非旧版别名入口。参数 API、健康检查和框架自带文档路由不计页面。开关状态和 574 个路由注册总数均分别统计，避免混为一类。
