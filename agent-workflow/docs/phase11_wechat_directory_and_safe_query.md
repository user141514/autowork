# Phase 11 WeChat Directory and Safe Query Design

## 1. Purpose

This phase solves two concrete review-workbench problems in order:

1. Resolve WeChat internal identifiers into human-readable chatroom/contact names and let the reviewer choose a conversation explicitly.
2. Prevent browser or SQLite stalls caused by large one-shot message queries.

The phase does not add new Agent execution permissions. Raw chat remains evidence only.

## 2. Task 1: Conversation Directory

### Goal

Turn internal WeChat IDs such as `wxid_*` and `*@chatroom` into selectable conversations.

### Data Sources

For already-readable WeChat database copies:

- `de_MicroMsg.db.Contact`
  - `UserName`
  - `Remark`
  - `NickName`
  - `Alias`
- `de_MicroMsg.db.Session`
  - `strUsrName`
  - `strNickName`
- `de_MicroMsg.db.ChatRoom`
  - `ChatRoomName`
  - `UserNameList`
  - `DisplayNameList`
- `de_MSG*.db.MSG`
  - `StrTalker`
  - `CreateTime`
  - `StrContent`

### Display Name Priority

For chatrooms and contacts:

```text
Contact.Remark
  -> Contact.NickName
  -> Contact.Alias
  -> Session.strNickName
  -> raw UserName / StrTalker
```

For group senders:

```text
ChatRoom.DisplayNameList
  -> Contact.Remark
  -> Contact.NickName
  -> sender wxid
```

### API

```text
GET /wechat-directory/conversations?kind=chatroom|contact|filehelper|all&query=<text>&limit=100
GET /wechat-directory/messages?conversation_id=<raw_id>&before_ts=<ts>&before_local_id=<id>&limit=50
```

The frontend displays `displayName` to humans and uses `id` as the stable query key.

## 3. Task 2: Safe Query and Paging

### Problem

Large URLs such as `GET /messages?limit=50000` or scanning all decrypted databases can freeze the browser and degrade SQLite performance.

### Rules

1. The review workbench must not read all conversations by default.
2. The user must choose a chatroom/contact before reading messages.
3. Single-request message limits are capped.
4. Large browsing uses cursor paging.
5. DemandRadar should run on a selected conversation window, not the whole message database.

### Backend Limits

- `/messages` and `/messages/latest` cap limits at 200.
- `/messages/page` provides cursor paging over the business database.
- `/wechat-directory/messages` caps page size at 200.
- `/review-workbench/recent-50-stream` reads only a selected conversation.

## 4. Frontend Flow

```text
Search conversations
  -> select one chatroom/contact
  -> load latest 50 messages
  -> optionally page older messages
  -> run DemandRadar on the selected window
  -> review candidate
  -> promote to WorkDocDraft / AgentInputPack
```

## 5. Acceptance Criteria

- Chatroom list shows display name, raw ID, message count, latest time, and preview.
- Contact list shows display name, raw ID, message count, latest time, and preview.
- Group message sender is resolved from `StrContent` prefix and `ChatRoom.DisplayNameList` when available.
- XML/emoji/image/video/voice messages are normalized before DemandRadar input.
- No selected conversation means no decrypted database scan.
- Message page size is capped at 200.
- Review workbench still does not call AgentRun or Git endpoints.
- Tests cover directory resolution, group sender resolution, paging cap, and no-room scan blocking.
