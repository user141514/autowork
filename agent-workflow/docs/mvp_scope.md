# MVP Scope

## 1. MVP 目标

第一版 MVP 的目标是跑通一个本地、可审计、可恢复的自主开发工作流闭环：

```text
模拟群聊消息
-> 保存消息
-> 生成 WorkDoc
-> 人工 approve
-> 调用 mock agent 或 claude_cli
-> 检查 diff
-> 运行测试
-> 创建本地 branch 和 commit
-> 输出执行报告
```

MVP 不追求真实微信接入、复杂前端、自动 PR 或高级 Agent 能力。它要证明的是：系统可以把非结构化聊天输入转成受控工程工作流，并且每个关键步骤都有状态、日志和结果记录。

## 2. 第一版必须实现什么

### 基础工程

- FastAPI 后端。
- SQLite 数据库。
- 基本配置系统。
- 结构化日志。
- README 启动说明。
- 本地开发运行方式。

### 数据模型

必须实现以下核心对象：

- ChatMessage
- WorkDoc
- AgentRun
- GitOperation

每个对象需要基础 CRUD API 或服务方法。

### 消息输入

- 支持通过 API 手动提交模拟群聊消息。
- 支持 MockChatAdapter。
- 消息必须保存到 MessageStore。
- raw_json 和 attachments 字段可以先用 JSON 字段保存。

### WorkDoc 生成

- 支持 mock extractor。
- 从一组 ChatMessage 生成 WorkDoc draft。
- WorkDoc 必须包含 problem_summary、expected_behavior、constraints、acceptance_criteria、evidence_message_ids、risk_level。
- 没有 acceptance_criteria 的 WorkDoc 不允许 validate。

### WorkDoc 审批

- 支持 validate。
- 支持 approve。
- 未 approve 的 WorkDoc 不允许创建 AgentRun。
- 状态变化必须落库。

### PolicyGate

MVP 必须实现最低限度的硬规则：

- 禁止直接在 main / master 分支执行。
- 禁止没有 acceptance_criteria 的任务执行。
- 默认禁止修改 .env、secrets.*、*.pem、*.key。
- 高风险任务进入 HUMAN_REVIEW_REQUIRED。

### AgentRunner

- 支持 mock runner。
- 预留 claude_cli runner，并允许通过配置启用。
- 记录 command、stdout_log、stderr_log、started_at、finished_at、status、result_summary。
- 支持超时。
- AgentRun 必须关联 WorkDoc。

### Repo 与 Git

- 检查 repo_path 是否为 Git 仓库。
- 创建独立 branch，禁止直接在 main / master 修改。
- Agent 执行后检查 git diff。
- 测试通过后创建本地 commit。
- 保存 GitOperation。

### TestRunner

- 支持配置测试命令。
- 记录测试 stdout、stderr 和 exit_code。
- 测试失败不允许 commit。
- 如果没有测试命令，MVP 可以允许显式 dry-run 模式，但报告必须说明未运行测试。

### ReportService

- 生成文本执行报告。
- 报告包含 WorkDoc 状态、AgentRun 结果、测试结果、commit_hash 和失败原因。
- MVP 中可以先通过 API 返回报告，不强制真实群聊回写。

### Demo

必须提供一个端到端 demo，输入示例：

```text
首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。
```

系统应生成 WorkDoc，人工 approve 后执行 mock agent 或 claude_cli，并输出报告。

## 3. 第一版明确不实现什么

MVP 不实现以下能力：

- 不接真实微信群。
- 不接真实企业微信。
- 不做完整前端 Dashboard。
- 不实现复杂多租户权限系统。
- 不自动 push 到远程仓库。
- 不默认创建 PR。
- 不自动处理高风险任务。
- 不实现复杂 LLM 任务规划。
- 不重新实现 Coding Agent。
- 不做跨仓库多任务调度。
- 不做分布式 worker。
- 不做完整 Temporal / LangGraph 编排。
- 不实现生产级密钥管理。
- 不实现复杂回滚策略。

这些功能可以在架构中预留接口，但不能拖慢第一版闭环。

## 4. 第一版只预留接口的功能

### 真实聊天平台

预留：

- WeChatAdapter
- EnterpriseWeChatAdapter
- SlackAdapter
- DiscordAdapter

MVP 实现：

- MockChatAdapter
- API message import

### LLM Extractor

预留：

- LLMTaskExtractor
- prompt template
- structured output schema

MVP 实现：

- MockTaskExtractor
- 基于规则的简单字段提取

### 外部 Agent

预留：

- ClaudeCliRunner
- GAgentDesktopRunner
- FutureAgentRunner

MVP 实现：

- MockAgentRunner
- 可选 ClaudeCliRunner 的最小命令封装

### 远程 Git 平台

预留：

- GitHubPublisher
- GitLabPublisher
- create_pr
- push_branch

MVP 实现：

- 本地 branch
- 本地 commit
- dry-run push / PR 配置

### 前端界面

预留：

- Dashboard API
- WorkDoc detail API
- AgentRun log API
- GitOperation status API

MVP 实现：

- FastAPI JSON API
- 文本报告

### 高级工作流编排

预留：

- retry policy
- resumable workflow
- external orchestrator adapter
- delayed job queue

MVP 实现：

- 数据库状态机
- 单进程顺序执行
- 失败后可人工重试

## 5. MVP 成功标准

MVP 完成后，系统应能回答以下问题：

- 哪些群聊消息触发了这个任务？
- WorkDoc 是如何生成的？
- WorkDoc 是否通过校验？
- 谁批准了执行？
- Agent 执行了什么命令？
- Agent 产生了什么日志？
- 仓库中有哪些 diff？
- 测试是否通过？
- commit hash 是什么？
- 如果失败，失败在哪一步，是否需要人工处理？

如果这些问题都能通过数据库记录和执行报告回答，MVP 就达到了目标。

## 6. 推荐 Phase 1 实现边界

Phase 1 只做项目骨架，不写完整业务逻辑：

- 创建 FastAPI 项目结构。
- 接入 SQLite。
- 定义配置和日志。
- 建立 app / domain / services / adapters / runners / publishers / tests 目录。
- 写 README。
- 提供 health check。

Phase 1 不实现 Agent 调用、Git commit、WorkDoc 生成等业务闭环。这些留到后续阶段按模块推进。

