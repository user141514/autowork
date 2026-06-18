# Claude Worker Task

你是外部 Claude Code CLI worker，只做只读 UI/UX 设计建议。Codex 是 supervisor。

背景：

- 项目名暂定 Autowork。
- 核心是“微信/手动输入 -> 筛选任务 -> WorkDoc -> 人审 -> Agent 执行 -> 测试 -> 本地 Git 提交 -> 报告回写”。
- 用户认为当前 `/dashboard` 像 API 调试台，看了发晕，不知道怎么开始自动化工作流。
- 新方向是中文的“工作台”，不是 dashboard。
- 用户主要是开发者/操作者，但希望保留 C 模式：默认流程清晰，Debug/Audit 信息可展开。
- 用户会指定一个大的工作区目录，系统扫描其中所有 Git 项目；聊天内容只能辅助推荐项目，不能直接决定执行目标。
- 第一版 `Finish Automation` 默认只做本地 branch + commit，不 push、不 PR、不 merge。

请输出一份中文 UI 设计建议，不要改文件，不要写代码。

重点回答：

1. 中文工作台的信息架构。
2. 首屏怎么让用户知道从哪里开始。
3. “微信输入筛选 -> 项目选择 -> WorkDoc -> 执行 -> Git 输出 -> 微信反馈”的页面布局。
4. 项目选择 / Workspace Registry 在 UI 上怎么表现。
5. Debug / Audit 信息如何隐藏但可访问。
6. 主要按钮中文文案。
7. 状态名称中文化建议。
8. 你推荐参考哪些产品的 UI 模式，但不要照搬。

输出格式：

```markdown
# Autowork 工作台 UI 设计建议

## 设计原则

## 首屏布局

## 主流程

## 项目选择

## 操作按钮与中文文案

## 状态文案

## Debug / Audit

## 参考产品与可借鉴点

## 推荐方案
```

不要编辑文件。不要提交。不要推送。
