# 设计决策

- 保留长缨深红用于主要动作，暖白用于页面和内容分层，琥珀色保留给提醒。
- 焦点以可辨识的外轮廓呈现。窄屏让表单、任务卡和工具导航自然换行。参考 [WCAG 2.2 增补条款](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) 与 [Reflow](https://www.w3.org/WAI/WCAG21/Understanding/reflow)。
- 课堂图示保留原图和逐步动作，滚动区完整承载内容。师生及家长显示沿用现有数据视图。参考 [Google Classroom 家长摘要](https://support.google.com/edu/classroom/answer/7075223)。
- 采用系统中文字体与局部作用域。CSS 单独接入，既有脚本及其兼容产物由原流程维护。性能以缺省页面与典型课堂交互分别测量。
- 大屏保留教师控制进度的机制，展示区支持键盘聚焦和滚动。参考 [Amplify 活动节奏指引](https://amplify.com/wp-content/uploads/2025/09/ADM_HS_Navigation.pdf)。
- 旧浏览器布局优先提供 `vh`，再由支持的浏览器采用 `dvh`。触屏安全区沿用已有页面策略。参考 [MDN CSS 环境变量](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Environment_variables/Using)。
- 按 [Web Vitals 指标](https://web.dev/articles/vitals) 区分测试环境响应开销与浏览器体验指标。现场指标以 LCP、INP、CLS 的第 75 百分位为依据。
