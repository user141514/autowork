# Phase 9 WeChat Intake Design

Phase 9 prioritizes Windows WeChat Desktop UIAutomation through `wxauto`.

Direct local database reads are not the main route because local WeChat databases may be encrypted, unstable across versions, privacy sensitive, and outside the goal of a group-chat-driven workflow system.

## Adapters

### WxautoAdapter / PersonalWeChatAdapter

Responsibilities:

- Read recent messages from a fixed whitelisted group.
- Send feedback messages to a fixed whitelisted group.
- Convert UIAutomation messages into `ChatMessageCreate`.

Constraints:

- Only reads rooms in `AGENT_WORKFLOW_WECHAT_WHITELIST_ROOMS`.
- Does not process private chats or scan all conversations.
- Does not trigger AgentRun directly.
- Stores messages first as `ChatMessage`.

### ManualExportAdapter

Supports importing historical chat records from:

- `.txt`
- `.json`
- `.csv`
- `.md`

The output is still `ChatMessage`; manual exports do not bypass WorkDoc validation or approval.

### LocalDatabaseImportAdapterStub

Only exposes a refusal boundary.

It does not:

- bypass encryption
- reverse engineer database formats
- read all local chat data
- act as a forensic tool

## Required Flow

Personal WeChat messages must follow:

```text
ChatMessage
-> MessageSegment
-> TaskCandidate
-> WorkDoc
-> Validate
-> Approve
-> AgentRun
```

Only messages containing `@WorkBot` enter TaskCandidate creation.

Normal messages remain stored evidence and context but do not enter execution flow.

## API

Poll wxauto:

```text
POST /wechat/wxauto/poll
```

Send feedback:

```text
POST /wechat/wxauto/send
```

Import manual export:

```text
POST /wechat/manual-export/import
```

Create Segment:

```text
POST /segments/from-messages
```

Create TaskCandidate:

```text
POST /task-candidates/from-segment
```

Create WorkDoc from TaskCandidate:

```text
POST /workdocs/from-task-candidate
```

## Example

Chat message:

```text
@WorkBot 首页设置按钮点了没反应，应该跳转到 /settings。先别重构，只修这个按钮。
```

This becomes a TaskCandidate because it contains `@WorkBot`.

The same text without `@WorkBot` stays as a normal ChatMessage/Segment and cannot enter the task flow.

