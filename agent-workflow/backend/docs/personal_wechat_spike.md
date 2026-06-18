# Personal WeChat wxauto Spike

Phase 9 uses Windows WeChat Desktop UIAutomation through `wxauto`. Direct local WeChat database reading is not the primary route and is intentionally left as a non-implemented stub.

## Safety Contract

- Only whitelisted groups from `AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS` may be read.
- Private chats are not supported.
- The adapter never scans all chats.
- Ordinary messages are persisted as `ChatMessage` only.
- Only `@WorkBot` commands may enter `BotCommand -> ConversationSegment -> TaskCandidate -> WorkDoc`.
- No message can create an `AgentRun` directly.

## Environment

```powershell
$env:AGENT_WORKFLOW_PERSONAL_WECHAT_ENABLED = "true"
$env:AGENT_WORKFLOW_ALLOWED_WECHAT_ROOMS = "研发群"
$env:AGENT_WORKFLOW_WECHAT_READ_LIMIT = "20"
$env:AGENT_WORKFLOW_WECHAT_CONTEXT_WINDOW_SIZE = "8"
```

Sending feedback is disabled unless explicitly enabled:

```powershell
$env:AGENT_WORKFLOW_WECHAT_SEND_ENABLED = "true"
```

## Read Spike

```powershell
python scripts/spike_wxauto_read_group.py --room "研发群" --limit 10
```

The script switches to the named group, reads recent UI messages, and prints raw JSON-like wxauto objects for mapping inspection.

## Send Spike

```powershell
python scripts/spike_wxauto_send_message.py --room "研发群" --text "WorkBot 收到。"
```

This script refuses to send unless `AGENT_WORKFLOW_WECHAT_SEND_ENABLED=true`.

## Backend Flow

1. `GET /wechat/health`
2. `POST /wechat/poll-room`
3. `POST /bot/process-new-messages`
4. `POST /segments/from-command/{message_id}`
5. `POST /task-candidates/from-segment/{segment_id}`
6. `POST /task-candidates/{id}/update`
7. `POST /task-candidates/{id}/convert-to-workdoc`

After WorkDoc conversion, the existing Phase 8 flow handles validate, approve, agent run, tests, git policy, commit, and report.
