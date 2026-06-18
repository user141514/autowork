你是一个资深全栈工程师和 Agent 工作流架构师。我要开发一个“群聊驱动的自主开发工作流系统”，请你不要一上来写代码，先帮我调研参照项目，再一步步实现 MVP。

## 一、项目目标

我要做的不是普通微信机器人，也不是普通代码 Agent，而是一个完整的自主工作流：

固定微信群聊 / 企业微信群 / 可替换聊天源
→ 机器人读取聊天记录
→ 提取与工作相关的信息
→ 生成结构化 WorkDoc 工作文档
→ 根据 WorkDoc 调用外部 Coding Agent
→ Coding Agent 修改代码
→ 自动测试
→ Git commit / branch / PR
→ 把执行结果反馈回群聊或前端界面

其中 Coding Agent 不需要你重新实现，暂时有两个可选执行器：

1. Claude CLI / Claude Code CLI
2. 我自己的 gagent-desktop

你的重点是搭建工作流系统，而不是重新造 Agent 模型。

## 二、我的核心思想

我认为各个单点组件都已经有人做过：

* 微信机器人 / 企业微信机器人 / 聊天记录读取
* LLM 信息抽取
* Coding Agent
* Git 自动提交
* 前端 Dashboard
* 本地 Agent Desktop

所以这个项目的价值不在单点组件，而在把它们组织成一个稳定、可审计、可替换、可迭代的工作流。

系统核心不应该是“微信群消息直接驱动代码修改”，而应该是：

聊天记录 → 任务识别 → WorkDoc 工作文档 → 审核 / 风险判断 → Agent 执行 → Git 结果 → 状态回写

WorkDoc 是中间契约，是整个系统的 Single Source of Truth。Agent 不能直接根据群聊原文改代码，必须根据 WorkDoc 工作。

## 三、你首先要做的事：调研参照项目

请你先不要写代码。请先搜索、阅读、总结可参考的开源项目或架构模式。重点找以下几类：

1. ChatOps 项目

   * 从 Slack / Discord / 企业微信 / 微信等聊天工具触发工作流的项目
   * 看它们如何做命令解析、权限控制、任务反馈

2. Coding Agent 项目

   * 例如 Aider、OpenHands、SWE-agent、Claude Code 类项目
   * 看它们如何接收任务、修改代码、生成 diff、跑测试、提交代码

3. Workflow / Orchestrator 项目

   * 例如 Temporal、LangGraph、Prefect、Dagster、AutoGen workflow 等
   * 看它们如何做状态机、任务重试、失败恢复、日志记录

4. GitOps / PR 自动化项目

   * 看它们如何创建 branch、commit、PR、回写状态

5. 桌面 Agent / 本地 Agent 项目

   * 看它们如何本地管理任务、文件系统、命令执行、日志和权限

请你输出一个 `reference_research.md`，内容包括：

* 每个参考项目的名称
* 项目解决的问题
* 可以借鉴的设计
* 不适合直接照搬的地方
* 对我这个项目的启发
* 最后给出推荐架构

注意：你不是简单堆项目列表，而是要判断哪些设计适合我的系统。

## 四、你要帮我形成的目标架构

请你在调研后，设计一个 MVP 架构。默认技术栈如下：

* 后端：Python FastAPI 优先，后续可迁移 Rust
* 数据库：SQLite 起步，后续可换 PostgreSQL
* 前端：先可选，后续 Vue / Electron / gagent-desktop 集成
* Agent 执行器：Claude CLI 或 gagent-desktop
* Git 操作：本地 git CLI + GitHub/GitLab API 可选
* 微信入口：先做 Adapter 抽象，不要和某个微信库强耦合

请你优先实现 Adapter 架构：

ChatAdapter:

* listen(room_id)
* send_message(room_id, text)
* send_file(room_id, file_path)

AgentRunner:

* run(workdoc_id, repo_path, agent_type)
* 支持 claude_cli
* 支持 gagent_desktop
* 后续可扩展其他 agent

GitPublisher:

* create_branch
* commit_changes
* push_branch
* create_pr

WorkDocService:

* create_from_messages
* validate
* approve
* update_status

## 五、系统中的核心对象

请你设计并实现以下核心对象：

### 1. ChatMessage

用于保存群聊消息。

字段包括：

* id
* platform
* room_id
* sender_hash
* sender_display_name
* timestamp
* message_type
* text
* attachments
* raw_json

### 2. WorkDoc

用于保存从聊天记录中提取出来的任务文档。

字段包括：

* id
* title
* repo_name
* branch_base
* problem_summary
* observed_behavior
* expected_behavior
* constraints
* acceptance_criteria
* evidence_message_ids
* uncertainties
* risk_level
* status

### 3. AgentRun

用于保存一次 Agent 执行过程。

字段包括：

* id
* workdoc_id
* agent_type
* repo_path
* status
* command
* stdout_log
* stderr_log
* started_at
* finished_at
* result_summary

### 4. GitOperation

用于保存 Git 操作结果。

字段包括：

* id
* workdoc_id
* branch_name
* commit_hash
* pr_url
* status
* created_at

## 六、MVP 工作流

请你按下面这个 MVP 做，不要一开始做复杂系统：

1. 手动或通过测试接口输入若干条群聊消息
2. 系统保存消息
3. 调用 LLM 或 mock extractor 生成 WorkDoc
4. 人工 approve WorkDoc
5. 系统根据 WorkDoc 调用 AgentRunner
6. AgentRunner 调用 Claude CLI 或 gagent-desktop
7. Agent 在指定 repo 中修改代码
8. 系统检测 git diff
9. 系统运行测试命令
10. 测试通过后创建 branch 和 commit
11. 可选 push / PR
12. 系统生成执行报告

注意：第一版可以先不接真实微信，先用 MockChatAdapter 或手动导入聊天记录跑通闭环。

## 七、重要设计约束

1. 聊天消息不能直接驱动代码修改，必须先生成 WorkDoc。
2. 没有 acceptance_criteria 的 WorkDoc 不能执行。
3. Agent 只能在独立 branch 或 worktree 中执行。
4. 默认不允许直接修改 main 分支。
5. 默认不允许自动修改敏感文件，例如：

   * .env
   * secrets.*
   * *.pem
   * *.key
   * 生产部署配置
   * 支付逻辑
   * 认证核心逻辑
6. 每次 Agent 执行必须有日志。
7. 每次代码修改必须有 diff。
8. 每次 Git 操作必须回写数据库。
9. 系统要能失败恢复，不能执行一半状态丢失。
10. 微信 Bot 只是 Adapter，不要让业务逻辑写死在微信库里。

## 八、你要按阶段工作

请按以下阶段推进，每完成一个阶段就输出：

* 你做了什么
* 修改了哪些文件
* 当前如何运行
* 当前还有什么问题
* 下一步计划

### Phase 0：参考项目调研

输出：

* reference_research.md
* architecture_decision.md

不要写业务代码。

### Phase 1：项目骨架

实现：

* FastAPI 后端
* SQLite 数据库
* 基本目录结构
* 配置文件
* 日志系统
* README

### Phase 2：核心数据模型

实现：

* ChatMessage
* WorkDoc
* AgentRun
* GitOperation
* 对应 CRUD API

### Phase 3：WorkDoc 生成

实现：

* 从消息生成 WorkDoc
* 先支持 mock extractor
* 预留 LLM extractor 接口
* WorkDoc validate / approve 状态流转

### Phase 4：AgentRunner

实现：

* Claude CLI runner
* gagent-desktop runner 抽象
* mock runner
* 执行日志记录
* 超时控制
* 工作目录隔离

### Phase 5：GitPublisher

实现：

* 检查 git diff
* 创建 branch
* commit
* 可选 push
* 可选 PR
* 生成执行报告

### Phase 6：ChatAdapter

实现：

* MockChatAdapter
* 文件导入聊天记录
* 预留 WeChatAdapter
* 预留 EnterpriseWeChatAdapter

### Phase 7：端到端 Demo

实现一个完整 demo：

输入一段模拟群聊：
“首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。”

系统自动生成 WorkDoc：

* 任务标题
* 问题描述
* 预期行为
* 约束
* 验收标准
* 风险等级

人工 approve 后：

* 调用 mock agent 或 claude_cli
* 生成 diff
* commit 到新 branch
* 输出报告

## 九、你写代码的要求

1. 代码要模块化，不要把所有逻辑塞进一个文件。
2. 每个模块职责要清楚。
3. 优先可运行，不要过度抽象。
4. 每个核心流程都要有日志。
5. 每个状态变化都要落库。
6. API 要便于后续接前端。
7. README 要写清楚如何启动、如何测试、如何跑 demo。
8. 不要默认真实连接微信，先通过 mock 跑通。
9. 不要默认真实 push Git，先做 dry-run，再开放真实模式。
10. 所有危险操作必须有配置开关。

## 十、最终目标

最终我想得到的是一个可以逐步进化的系统：

第一阶段：
模拟群聊 → WorkDoc → Agent → Git commit

第二阶段：
真实群聊 → WorkDoc → 人工确认 → Agent → PR

第三阶段：
低风险任务自动执行，高风险任务人工审核

第四阶段：
接入 gagent-desktop，形成桌面端自主开发工作台

请你现在从 Phase 0 开始，先调研参照项目并输出 reference_research.md 和 architecture_decision.md。不要直接写代码。
