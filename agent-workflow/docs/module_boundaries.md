# Module Boundaries

## 1. 模块边界原则

本系统按工作流职责拆分模块。模块之间通过明确的数据对象和服务接口协作，避免把聊天平台、Agent 执行、Git 操作和业务状态混在一起。

核心原则：

- ChatAdapter 只负责输入输出，不做业务判断。
- WorkDocService 是任务语义和状态流转中心。
- PolicyGate 负责风险和权限，不执行具体任务。
- AgentRunner 只根据已批准 WorkDoc 和 RepoContext 执行。
- GitPublisher 只处理 Git 结果发布，不判断需求是否合理。
- ReportService 统一组织对外反馈。

## 2. ChatAdapter

职责：

- 从聊天平台或 mock source 接收消息。
- 向指定 room 发送文本、文件或执行报告。
- 屏蔽微信、企业微信、Slack、Discord、文件导入等平台差异。

核心接口：

```text
listen(room_id)
send_message(room_id, text)
send_file(room_id, file_path)
```

输入：

- room_id
- 平台 SDK 原始消息

输出：

- ChatMessage DTO

不负责：

- 判断消息是否是任务。
- 生成 WorkDoc。
- 调用 Agent。
- 处理 Git。

## 3. MessageStore

职责：

- 持久化 ChatMessage。
- 保存 raw_json、attachments、sender_hash 和 timestamp。
- 为 TaskExtractor 提供按 room、时间窗口、消息 ID 查询的能力。

输入：

- ChatMessage

输出：

- message_id
- 消息查询结果

不负责：

- 理解消息语义。
- 过滤任务优先级。
- 触发代码执行。

## 4. TaskExtractor

职责：

- 从一组 ChatMessage 中识别任务候选。
- 提取 WorkDoc 草稿字段。
- 标记不确定性和缺失信息。
- MVP 先实现 mock extractor，后续预留 LLM extractor。

输入：

- ChatMessage 列表
- room_id
- 可选上下文窗口

输出：

- TaskCandidate
- WorkDoc draft payload

不负责：

- 审批任务。
- 决定是否执行。
- 调用 Agent。
- 修改数据库中的最终状态。

## 5. WorkDocService

职责：

- 创建、读取、更新 WorkDoc。
- 执行结构校验。
- 管理 WorkDoc 状态流转。
- 保存 evidence_message_ids 和 WorkDoc 版本。
- 提供 approve / reject / request_changes 能力。

输入：

- WorkDoc draft payload
- 审批动作
- 状态变更请求

输出：

- WorkDoc
- validation result
- status transition result

不负责：

- 直接执行 Agent。
- 直接操作 Git。
- 调用聊天平台。

## 6. PolicyGate

职责：

- 执行任务执行前和 patch 生成后的风险检查。
- 判断是否允许自动执行。
- 判断是否需要人工审核。
- 检查禁止分支、敏感文件、风险等级、缺失验收标准。

典型策略：

- 禁止直接在 main / master / production 分支运行。
- 禁止默认修改 .env、secrets.*、*.pem、*.key。
- 默认禁止修改认证核心逻辑、支付逻辑和生产部署配置。
- 没有 acceptance_criteria 的 WorkDoc 不能执行。
- 高风险任务必须人工审批。

输入：

- WorkDoc
- RepoContext
- changed_files
- system config

输出：

- allow
- deny
- require_human_review
- reasons

不负责：

- 生成 WorkDoc。
- 执行测试。
- 创建 commit。

## 7. RepoContextBuilder

职责：

- 为 AgentRun 准备受控的仓库上下文。
- 检查 repo_path 是否存在且为 Git 仓库。
- 确认 base branch。
- 创建独立 branch 或 worktree。
- 生成 Agent 可用的任务上下文文件。

输入：

- WorkDoc
- repo_path
- branch_base
- execution config

输出：

- RepoContext
- worktree_path
- branch_name
- context_file_path

不负责：

- 调用 Agent。
- commit 代码。
- 创建 PR。

## 8. AgentRunner

职责：

- 根据 WorkDoc 和 RepoContext 调用外部 Coding Agent。
- 支持 claude_cli、gagent_desktop 和 mock runner。
- 记录命令、stdout、stderr、开始时间、结束时间和结果摘要。
- 执行超时控制。

核心接口：

```text
run(workdoc_id, repo_path, agent_type)
```

输入：

- workdoc_id
- RepoContext
- agent_type
- timeout

输出：

- AgentRun
- exit_code
- stdout_log
- stderr_log
- result_summary

不负责：

- 判断 WorkDoc 是否应该批准。
- 判断 patch 是否安全。
- 运行测试。
- commit 或 push。

## 9. TestRunner

职责：

- 在 Agent 生成 patch 后运行测试命令。
- 保存测试日志、退出码和耗时。
- 返回 TEST_PASSED 或 TEST_FAILED。

输入：

- RepoContext
- test command
- timeout

输出：

- test status
- stdout
- stderr
- exit_code

不负责：

- 决定测试命令是否符合业务需求。
- 修改代码。
- 创建 commit。

## 10. GitPublisher

职责：

- 检查 git diff。
- 创建或确认任务 branch。
- commit 允许的变更。
- 可选 push branch。
- 可选创建 PR / MR。
- 保存 GitOperation。

输入：

- WorkDoc
- RepoContext
- changed_files
- commit message
- publish config

输出：

- branch_name
- commit_hash
- pr_url
- GitOperation status

不负责：

- 生成代码变更。
- 判断需求是否合理。
- 回写聊天平台。

## 11. ReportService

职责：

- 生成面向用户的执行报告。
- 汇总 WorkDoc、AgentRun、测试结果和 GitOperation。
- 将结果发送到 ChatAdapter 或提供给 Dashboard API。

报告应包含：

- 任务标题
- 当前状态
- 成功或失败原因
- 变更摘要
- 测试结果
- commit_hash
- pr_url
- 需要人工处理的事项

输入：

- workdoc_id

输出：

- report text
- report file
- dashboard payload

不负责：

- 执行工作流状态变更。
- 调用 Agent。
- 执行 Git 操作。

## 12. 模块协作主链路

```text
ChatAdapter
-> MessageStore
-> TaskExtractor
-> WorkDocService
-> PolicyGate
-> RepoContextBuilder
-> AgentRunner
-> PolicyGate
-> TestRunner
-> GitPublisher
-> ReportService
-> ChatAdapter
```

这条链路中，WorkDoc 是语义中心，PolicyGate 是安全边界，AgentRunner 是执行器适配层，GitPublisher 是发布边界。

