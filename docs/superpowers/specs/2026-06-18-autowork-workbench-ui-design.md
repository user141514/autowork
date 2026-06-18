# Autowork 工作台 UI 设计规格

日期：2026-06-18

## 背景

当前 `/dashboard` 更像 API 调试台：模块和按钮直接映射后端接口，用户需要自己理解 `Message -> Segment -> TaskCandidate -> WorkDoc -> AgentRun -> GitOperation -> Report` 的顺序。它能调试系统，但不能自然地引导开发者开始一次自动化工作流。

新的方向是 **Autowork 工作台**。它面向开发者/操作者，默认视图清晰地呈现“从微信群消息到本地 Git 提交”的主流程，同时保留调试和审计能力。

核心链路：

```text
微信/手动输入
-> 筛选 @WorkBot / 白名单群
-> 形成可执行 WorkDoc
-> 人工审批
-> Agent 执行
-> 测试
-> 本地 Git 分支 + commit
-> 报告回写微信
```

## 设计目标

1. 首屏让用户知道从哪里开始，而不是看到一堆 API 按钮。
2. 全中文界面，内部技术名只作为辅助信息或调试信息出现。
3. 把“微信内容筛选转换为输入”和“执行输出接回 Git/微信”作为主产品体验。
4. 支持一个大工作区目录，系统扫描其中所有 Git 项目。
5. 聊天内容只能辅助推荐项目，不能直接决定执行目标。
6. 默认保守：`Finish Automation` 只创建本地分支和本地 commit，不 push、不 PR、不 merge。
7. Debug / Audit 能力保留，但默认折叠，不抢主流程视线。

## 信息架构

工作台采用三栏布局：

```text
左侧：输入来源 + 工作区项目
中间：自动化任务队列 + 流程状态
右侧：当前任务详情 + 下一步操作 + 输出目标 + 调试审计
```

### 左侧：输入来源与工作区

左侧负责“任务从哪里来”和“能改哪些项目”。

输入来源包括：

- 手动输入模拟消息
- 轮询白名单微信群
- 导入历史聊天文件

工作区项目包括：

- 工作区根目录，例如 `F:\workspace`
- 扫描得到的 Git 项目列表
- 项目别名，例如 `官网`、`后台`、`小程序`
- 当前分支、路径、关联任务数量
- 重新扫描入口

左侧必须明确提示：

```text
只处理 @WorkBot 命令；普通聊天只保存为证据，不会直接触发执行。
```

### 中间：自动化任务队列

中间是主工作区，默认显示“待处理”任务。

任务列表应显示：

- 任务编号
- 中文标题
- 来源：微信群 / 手动导入 / 文件导入
- 当前状态
- 目标项目
- 风险等级
- runner 类型
- 是否需要测试
- 关键证据消息摘要

任务队列顶部显示流程步骤：

```text
消息 -> 任务 -> 审核 -> 执行 -> 测试 -> Git -> 反馈
```

当前步骤高亮，完成步骤打勾，阻塞步骤显示原因。

### 右侧：当前任务详情

右侧只显示选中任务的下一步和必要上下文。

内容包括：

- WorkDoc 编号
- 状态
- 目标项目
- 本地路径
- 基准分支
- 输出目标
- 问题摘要
- 验收标准
- 下一步操作卡片
- 完成自动化说明
- 执行记录时间线
- 调试与审计折叠入口

未选中任务时，右侧显示开始引导：

```text
1. 配置工作区目录
2. 输入或导入消息
3. 从消息生成任务
4. 审核并执行
```

## 主流程

### 1. 消息进入

用户可以手动输入、导入文件，或轮询白名单微信群。

微信路径必须遵守：

- 只读白名单群
- 不处理私聊
- 不自动读取所有聊天
- 只有 `@WorkBot` 命令进入任务流
- 所有消息先保存为 `ChatMessage`

普通消息可以出现在证据里，但不能直接触发 Agent。

### 2. 任务候选

系统把有效命令转为任务候选，并展示来源证据。

内部仍可使用 `Segment` 和 `TaskCandidate`，但默认 UI 不展示这些术语。对用户显示为：

- 候选任务
- 证据消息
- 需要补充的信息

### 3. 项目选择

系统通过 Workspace Registry 扫描大工作区目录下的 Git 项目。

聊天内容可以用于推荐项目，但必须明确区分：

```text
聊天推荐项目
```

和：

```text
实际执行项目
```

如果无法唯一确定项目，任务进入阻塞状态：

```text
需要选择项目
```

未选择目标项目时，禁止审批和执行。

### 4. WorkDoc 审核

WorkDoc 是执行契约。右侧详情展示：

- 问题摘要
- 预期行为
- 验收标准
- 约束
- 目标项目
- 测试命令
- 风险等级

用户可以：

- 保存草稿
- 校验任务
- 批准执行
- 退回修改

### 5. Agent 执行

批准后才允许 Agent 运行。

UI 默认展示人类可读摘要：

- runner 类型
- 当前状态
- 变更文件
- diff 摘要
- 执行耗时

完整命令、stdout、stderr 放入调试与审计区域。

### 6. 测试

如果 WorkDoc 配置了测试命令，工作台显示：

- 测试命令
- 是否必需
- 测试状态
- 失败原因

如果 `test.required=true`，测试未通过时禁止 commit。

### 7. Finish Automation

主按钮使用：

```text
Finish Automation
```

第一版默认语义：

```text
创建本地分支 + 本地 commit
```

必须在界面上清楚写出：

- 默认只创建本地分支和本地 commit
- 不会 push main
- 不会自动创建 PR
- 不会自动 merge
- 完成后可发送报告到微信群

未来如果启用远程能力，`Finish Automation` 根据配置决定：

- local commit
- push branch
- create PR

但默认仍然是最保守路径。

### 8. 报告回写

完成后生成报告摘要。

报告应包含：

- WorkDoc 摘要
- 来源证据
- 目标项目
- Agent 执行结果
- 变更文件
- 测试结果
- 本地分支
- commit hash
- policy decision 摘要

用户可手动发送反馈到微信群。自动发送需要显式开启。

## Workspace Registry 与 ProjectResolver

### Workspace Registry

新增工作区概念：

```text
workspace_root = F:\workspace
```

系统扫描其中所有 Git repo，形成项目注册表。

项目记录建议包含：

```json
{
  "repo_id": "website",
  "repo_name": "website",
  "repo_path": "F:\\workspace\\website",
  "aliases": ["官网", "网站", "landing"],
  "remote_url": "git@github.com:example/website.git",
  "default_branch": "main",
  "project_type": "node",
  "test_commands": ["npm test"]
}
```

### ProjectResolver

ProjectResolver 负责推荐项目，但不做最终执行决策。

推荐信号：

- 项目别名
- repo 名称
- remote URL
- 文件关键词
- 群聊与项目绑定关系

决策规则：

- 唯一高置信匹配：自动填入推荐项目，但 UI 仍显示可修改
- 多个候选：要求人工选择
- 无候选：阻塞为“需要选择项目”
- 未确认项目：禁止 approve / run agent

## 中文文案

### 主要区域

- 输入来源
- 工作区项目
- 自动化任务
- 当前任务
- 任务契约
- 下一步
- 完成自动化
- 执行记录
- 调试与审计

### 主要按钮

- 导入消息
- 轮询微信
- 导入历史聊天文件
- 重新扫描
- 生成工作任务
- 保存草稿
- 校验任务
- 批准并开始执行
- 退回修改
- 运行测试
- 查看变更
- Finish Automation
- 查看报告
- 发送反馈

### 状态文案

| 内部状态 | 中文显示 |
| --- | --- |
| MESSAGE_RECEIVED | 消息已接收 |
| TASK_CANDIDATE_CREATED | 候选任务 |
| WORKDOC_DRAFTED | 草稿 |
| WORKDOC_VALIDATED | 已校验 |
| WORKDOC_APPROVED | 已批准 |
| APPROVED_FOR_AGENT | 已批准执行 |
| AGENT_RUNNING | 执行中 |
| PATCH_CREATED | 代码已修改 |
| TEST_RUNNING | 测试中 |
| TEST_FAILED | 测试失败 |
| TEST_PASSED | 测试通过 |
| APPROVED_FOR_COMMIT | 已批准提交 |
| GIT_COMMITTED | 已本地提交 |
| REPORTED_BACK | 已反馈 |
| HUMAN_REVIEW_REQUIRED | 需要人工处理 |
| POLICY_BLOCKED | 策略拦截 |

## Debug / Audit

默认折叠，入口放在右侧底部。

折叠内容包括：

- policy decisions
- AgentRun 原始命令和日志
- TestRun stdout / stderr
- GitOperation 原始输出
- diff 原文
- raw JSON

调试信息分层：

- L0：主流程摘要，默认显示
- L1：WorkDoc 完整内容，点击展开
- L2：执行证据，点击展开
- L3：审计日志，折叠在 Debug / Audit 内

## 参考模式

借鉴但不照搬：

- GitHub Actions：run -> job -> step 的状态与日志展开方式
- Temporal Web UI：以一次 workflow execution 为中心对象
- Linear：列表 + 右侧详情面板的信息组织
- Vercel / Netlify：结果摘要、状态、commit 信息的清爽展示
- VS Code：底部/侧边调试面板的渐进披露方式

不采用：

- n8n / Retool 那种自由拖拽编排器，因为 Autowork 的流程是固定受控流程
- IDE 级复杂界面，因为目标是工作台，不是完整开发环境

## 非目标

第一版 UI 不做：

- 真实微信长期后台运行控制台
- 多用户权限系统
- 复杂前端框架
- 自由拖拽工作流编排
- 自动 push main
- 自动 merge
- 默认自动创建 PR

## 实施建议

第一阶段仍可保持简单 HTML/JS，不急着引入复杂前端工程。

优先级：

1. P0：中文工作台布局，替换当前按钮墙。
2. P0：首屏开始引导和主流程步骤条。
3. P0：任务队列 + 当前任务详情。
4. P1：项目选择 UI 和 workspace root 配置入口。
5. P1：Debug / Audit 折叠面板。
6. P2：Workspace Registry 后端扫描 API。
7. P2：ProjectResolver 推荐逻辑。
8. P3：实时日志流。

## 验收标准

1. 用户打开页面后能在 10 秒内理解从哪里开始。
2. 页面主文案为中文。
3. 首屏明确显示工作流步骤。
4. 未选择目标项目时，界面阻止审批或执行。
5. `Finish Automation` 明确说明默认只做本地 branch + commit。
6. Debug / Audit 不占默认主视图。
7. 当前后端已有能力仍可从工作台触发。
8. 页面不再以 raw JSON dump 作为默认反馈方式。
