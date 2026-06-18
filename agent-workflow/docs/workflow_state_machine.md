# Workflow State Machine

## 1. 状态机目标

本状态机用于描述从聊天消息进入系统，到任务被提炼、审核、执行、测试、提交和回写的完整生命周期。

状态机的核心要求：

- 每个状态变化都必须落库。
- 每个状态变化都应记录时间、触发者和原因。
- Agent 执行前必须存在已验证、已批准的 WorkDoc。
- 测试和 Git 操作必须关联到同一个 WorkDoc。
- 任意失败都不能让系统状态丢失，必须可以恢复、重试或转人工。

## 2. 状态定义

### MESSAGE_RECEIVED

系统接收到一条或多条聊天消息，并保存为 ChatMessage。

进入条件：

- ChatAdapter 收到消息。
- 或通过 API / 文件导入模拟消息。

主要动作：

- 保存 ChatMessage。
- 保留 raw_json、sender_hash、room_id、timestamp 和 attachments。

可转移到：

- TASK_CANDIDATE_CREATED

### TASK_CANDIDATE_CREATED

TaskExtractor 判断消息中可能包含一个开发任务，并创建任务候选。

进入条件：

- 消息包含修复、实现、调整、测试、提交等工作意图。
- 或人工从消息中手动创建任务候选。

主要动作：

- 记录候选任务来源消息。
- 标记置信度和缺失信息。

可转移到：

- WORKDOC_DRAFTED
- HUMAN_REVIEW_REQUIRED

### WORKDOC_DRAFTED

系统根据任务候选和相关消息生成 WorkDoc 草稿。

进入条件：

- TaskExtractor 生成结构化字段。
- 或人工创建 WorkDoc 草稿。

主要动作：

- 填充 title、repo_name、branch_base、problem_summary、expected_behavior、constraints、acceptance_criteria、evidence_message_ids、uncertainties、risk_level。
- status 设为 draft。

可转移到：

- WORKDOC_VALIDATED
- HUMAN_REVIEW_REQUIRED

### WORKDOC_VALIDATED

WorkDoc 通过结构校验，具备进入审批或执行前策略判断的基本条件。

进入条件：

- title 不为空。
- problem_summary 不为空。
- acceptance_criteria 至少包含一条可验证标准。
- evidence_message_ids 不为空。
- branch_base 不指向禁止分支策略之外的目标。

主要动作：

- WorkDocService 执行字段校验。
- PolicyGate 执行初步风险检查。

可转移到：

- WORKDOC_APPROVED
- HUMAN_REVIEW_REQUIRED

### WORKDOC_APPROVED

WorkDoc 已被批准，可以进入 Agent 执行准备阶段。

进入条件：

- 人工 approve。
- 或未来低风险任务满足自动审批策略。

主要动作：

- 记录审批人、审批时间和审批备注。
- 冻结用于本次执行的 WorkDoc 版本。

可转移到：

- AGENT_RUN_CREATED

### AGENT_RUN_CREATED

系统为已批准 WorkDoc 创建一次 AgentRun。

进入条件：

- WorkDoc 处于 WORKDOC_APPROVED。
- PolicyGate 允许执行。
- repo_path、agent_type、执行超时和测试命令已确定。

主要动作：

- 创建 AgentRun 记录。
- 生成执行命令。
- 准备独立 branch 或 worktree。
- 保存 execution policy snapshot。

可转移到：

- AGENT_RUNNING
- HUMAN_REVIEW_REQUIRED

### AGENT_RUNNING

AgentRunner 正在执行代码修改。

进入条件：

- AgentRun 已创建。
- RepoContextBuilder 已准备执行目录。

主要动作：

- 调用 claude_cli、gagent_desktop 或 mock runner。
- 实时记录 stdout_log 和 stderr_log。
- 记录 started_at。

可转移到：

- PATCH_CREATED
- HUMAN_REVIEW_REQUIRED

### PATCH_CREATED

Agent 执行结束，并在仓库中产生了代码变更。

进入条件：

- AgentRunner 退出。
- git diff 非空。
- 变更未触犯敏感文件策略。

主要动作：

- 保存 diff 摘要。
- 保存 AgentRun result_summary。
- 再次调用 PolicyGate 检查变更文件。

可转移到：

- TEST_RUNNING
- HUMAN_REVIEW_REQUIRED

### TEST_RUNNING

TestRunner 正在执行测试命令。

进入条件：

- PATCH_CREATED。
- 存在可执行的测试命令。

主要动作：

- 执行配置中的测试命令。
- 记录 stdout、stderr、exit_code 和耗时。

可转移到：

- TEST_PASSED
- TEST_FAILED

### TEST_FAILED

测试失败。

进入条件：

- 测试命令 exit_code 非 0。
- 测试超时。
- 测试环境缺失且无法继续。

主要动作：

- 保存失败日志。
- 标记 WorkDoc 需要人工处理或可重试。
- 生成失败报告。

可转移到：

- HUMAN_REVIEW_REQUIRED
- REPORTED_BACK

### TEST_PASSED

测试通过。

进入条件：

- 测试命令 exit_code 为 0。
- 或 MVP 中配置为允许无测试命令但必须显式标记。

主要动作：

- 保存测试报告。
- 允许进入 GitPublisher。

可转移到：

- GIT_COMMITTED

### GIT_COMMITTED

GitPublisher 已创建 branch 并提交代码。

进入条件：

- TEST_PASSED。
- git diff 非空。
- 当前分支不是受保护分支。
- commit 模式已开启。

主要动作：

- 创建或切换到任务 branch。
- git add 允许文件。
- git commit。
- 保存 branch_name、commit_hash 和状态。

可转移到：

- PR_CREATED
- REPORTED_BACK

### PR_CREATED

系统已创建 Pull Request 或 Merge Request。

进入条件：

- GIT_COMMITTED。
- push / PR 配置已开启。
- 远程仓库和认证信息可用。

主要动作：

- push branch。
- 调用 GitHub / GitLab API 创建 PR。
- 保存 pr_url。

可转移到：

- REPORTED_BACK

### REPORTED_BACK

ReportService 已将执行结果回写到群聊、Dashboard 或 API 查询结果。

进入条件：

- 成功完成 commit / PR。
- 或失败流程需要回写。

主要动作：

- 生成执行报告。
- 回写 WorkDoc 状态、AgentRun 摘要、测试结果、commit_hash、pr_url。
- 通过 ChatAdapter 或 Dashboard 显示结果。

终态：

- 是。

### HUMAN_REVIEW_REQUIRED

系统需要人工介入。

进入条件：

- WorkDoc 缺少必要字段。
- 风险等级过高。
- 请求修改敏感文件。
- Agent 执行失败。
- 测试失败。
- Git 操作失败。
- 状态机检测到不可自动恢复的异常。

主要动作：

- 记录阻塞原因。
- 生成需要人工处理的报告。
- 暂停自动执行。

可转移到：

- WORKDOC_DRAFTED
- WORKDOC_VALIDATED
- WORKDOC_APPROVED
- AGENT_RUN_CREATED
- REPORTED_BACK

## 3. 主路径状态转移

```text
MESSAGE_RECEIVED
-> TASK_CANDIDATE_CREATED
-> WORKDOC_DRAFTED
-> WORKDOC_VALIDATED
-> WORKDOC_APPROVED
-> AGENT_RUN_CREATED
-> AGENT_RUNNING
-> PATCH_CREATED
-> TEST_RUNNING
-> TEST_PASSED
-> GIT_COMMITTED
-> PR_CREATED
-> REPORTED_BACK
```

MVP 中 `PR_CREATED` 是可选状态。默认主路径可以是：

```text
TEST_PASSED -> GIT_COMMITTED -> REPORTED_BACK
```

## 4. 失败与人工审核路径

任何状态都可以在策略不满足、信息不足或外部系统失败时进入：

```text
HUMAN_REVIEW_REQUIRED
```

典型失败路径：

```text
WORKDOC_DRAFTED -> HUMAN_REVIEW_REQUIRED
PATCH_CREATED -> HUMAN_REVIEW_REQUIRED
TEST_RUNNING -> TEST_FAILED -> HUMAN_REVIEW_REQUIRED
GIT_COMMITTED -> REPORTED_BACK
```

人工处理后可以：

- 补充 WorkDoc 信息并重新 validate。
- 调整风险等级或执行策略。
- 修改测试命令。
- 允许重试 AgentRun。
- 直接终止任务并回写报告。

## 5. 状态机硬性约束

- 没有 WorkDoc 不允许创建 AgentRun。
- WorkDoc 没有 acceptance_criteria 不允许进入 WORKDOC_VALIDATED。
- WorkDoc 未批准不允许进入 AGENT_RUN_CREATED。
- Agent 不能在 main、master、production 等受保护分支直接运行。
- Agent 不能修改敏感文件，除非显式人工审批并打开配置开关。
- TEST_FAILED 不允许进入 GIT_COMMITTED。
- Git 操作结果必须写入 GitOperation。
- REPORTED_BACK 必须包含成功或失败原因，不能只返回空状态。

