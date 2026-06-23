# DemandRadar Design

## 1. Positioning

`DemandRadar` is the requirement discovery layer between normalized group-chat messages and the existing WorkDoc workflow.

It does not read WeChat, log in to WeChat, decrypt databases, call coding agents, create final WorkDocs, or modify code. It receives already normalized messages and detects local conversation fragments that may contain engineering work.

Its job is to reduce the cost of finding useful requirements in noisy work chats.

The core output is not a task execution request. The core output is a human-reviewable `CandidateRequirement`.

## 1.1 Phase Goal

The goal of this phase is not to complete an automatic group-chat-to-code workflow.

The goal is to prove that a noisy batch of group-chat messages can be reliably converted into a small set of reviewable requirement cards.

Success for this phase means:

- Input: about 100 mixed group-chat messages.
- Output: about 3 to 8 `CandidateRequirement` cards.
- Each card includes evidence messages, facts, inferences, missing fields, and confidence.
- A human can decide within about 10 seconds whether to confirm, ignore, merge, or supplement the card.
- No card directly creates WorkDoc.
- No card triggers AgentRun.
- No code is modified by this layer.

This phase optimizes for review usefulness, not automation completeness.

```text
Message[]
  -> MessageNoiseMarker
  -> SignalAnnotator
  -> ContextSegmenter
  -> CandidateManager
  -> CandidateRequirement[]
  -> Markdown review draft
  -> human confirmation
  -> later WorkDoc flow
```

## 2. Problem Statement

Work-chat requirements are rarely written like tickets. They emerge from short conversation clusters:

- One person reports a problem.
- Another person clarifies expected behavior.
- Someone adds a screenshot, log, page name, repo hint, deadline, or constraint.
- Someone confirms priority or says to handle it first.

The important unit is therefore not a single message. It is a local message sequence.

DemandRadar must discover these local sequences without forcing users to write rigid commands such as `@WorkBot`.

Hard routes like `@WorkBot` remain useful as an explicit override, but they should not be the only way to find work.

## 3. Non Goals

DemandRadar must not:

- Directly create a final WorkDoc.
- Directly trigger AgentRun.
- Directly modify code.
- Treat one keyword as a high-confidence task.
- Require group members to use a fixed message template.
- Permanently summarize all chat history into tasks.
- Invent missing technical details.
- Hide uncertainty from the user.

## 4. Input Message Contract

DemandRadar accepts normalized messages. The WeChat database, manual import, UIAutomation, or any future adapter must convert source data into this shape before calling DemandRadar.

```ts
type Message = {
  id: string;
  chatId: string;
  chatName: string;
  sender: string | null;
  timestamp: string;
  text: string;
  msgType: "text" | "image" | "file" | "link" | "system" | "unknown";
  source: string;
  replyToMessageId?: string | null;
  raw?: unknown;
};
```

Important rules:

- `id` must be stable.
- `timestamp` must be comparable.
- `chatId` is the stable source identifier, such as `xxxxx@chatroom`.
- `chatName` is the user-facing name when available.
- Message source adapters are outside DemandRadar.

## 5. Output Candidate Contract

DemandRadar outputs `CandidateRequirement`.

This object is intentionally weaker than WorkDoc. It is a suspicion plus evidence, not an execution contract.

```ts
type CandidateRequirement = {
  candidateId: string;
  chatId: string;
  chatName: string;
  status:
    | "suspect"
    | "candidate"
    | "pending_review"
    | "confirmed"
    | "rejected"
    | "merged"
    | "expired";
  confidence: "low" | "medium" | "high";
  hypothesis: string;
  requirementType:
    | "bug"
    | "feature"
    | "config"
    | "data"
    | "document"
    | "process"
    | "uncertain";
  evidenceMessages: EvidenceMessage[];
  facts: CandidateFact[];
  inferences: CandidateInference[];
  missingFields: MissingField[];
  signalSummary: SignalSummary;
  sourceMessageIds: string[];
  firstMessageTime: string;
  lastMessageTime: string;
  createdAt: string;
  updatedAt: string;
};
```

Every candidate must have `sourceMessageIds`. Every fact must cite source message IDs.

## 6. MessageNoiseMarker

Noise is not deleted. It is labeled.

Low-information messages must not trigger candidates by themselves, but they may remain useful as context.

Noise examples:

- System messages.
- Pure emoji.
- Single-character replies.
- "收到", "好的", "我看看", "嗯", "1".
- Social chatter with no engineering object.
- Empty XML-only media placeholders.
- Join/leave/admin messages.

Noise labels should be attached to each message, for example:

```json
{
  "messageId": "m123",
  "isNoise": true,
  "noiseReasons": ["acknowledgement"]
}
```

This allows the segmenter to preserve context while preventing low-value messages from creating false candidates.

## 7. SignalAnnotator

SignalAnnotator labels each message with requirement signals.

The first version should use deterministic rule sets. Later versions can add LLM-assisted signal classification.

### Signal Types

`problem`

Indicates something is broken or undesirable.

Examples:

- 报错
- 失败
- 打不开
- 没反应
- 不对
- 慢
- 乱
- 丢失
- 错位

`intent`

Indicates a desire to change something.

Examples:

- 能不能
- 需要
- 帮我
- 加一个
- 改成
- 优化
- 支持
- 整理

`object`

Indicates an engineering object.

Examples:

- 页面
- 按钮
- 接口
- 数据库
- 脚本
- 仓库
- 文件名
- 路由
- 错误日志
- API
- 表
- 字段
- 组件

`constraint`

Indicates boundaries.

Examples:

- 不要重构
- 只改这里
- 今天先
- 别影响
- 保持兼容
- 先临时处理

`confirmation`

Indicates the conversation is becoming actionable.

Examples:

- 这个先处理
- 你来改
- 今天要
- 发版前修
- 确认一下
- 记个需求

`priority`

Indicates urgency.

Examples:

- 紧急
- 今天
- 马上
- 发版前
- 优先

`artifact`

Indicates evidence or attached material.

Examples:

- 截图
- 日志
- 报错
- 文件
- 链接
- 录屏

`termination`

Indicates the candidate should be suppressed, expired, or rejected-like.

Examples:

- 已解决
- 不用改
- 不是问题
- 先不做
- 取消
- 忽略

## 8. ContextSegmenter

DemandRadar should not summarize fixed windows blindly.

It should find local high-signal areas and then expand around them.

The segmenting model has three windows:

```text
Backtrace Window
  Look backward up to 20 messages or 15 minutes.

Core Window
  The signal-dense region that triggered suspicion.

Wait Window
  After the trigger, wait 3 to 5 minutes or a small number of later messages
  to collect clarification, evidence, priority, or termination.
```

A `SuspectBlob` is created when at least two core signal categories appear near each other.

Core signals:

- problem
- intent
- object
- constraint
- confirmation
- priority
- artifact

Single-message keyword hits are not enough for high confidence.

Examples:

```text
Message A: 这个按钮点了没反应
Signals: problem + object

Message B: 应该跳到设置页
Signals: intent/object-like expected behavior

Message C: 先别重构，只修这个
Signals: constraint
```

These should merge into one candidate blob.

## 9. Scoring

Initial scoring should be explainable.

```text
score =
  1.5 * problem
+ 1.5 * intent
+ 2.0 * object
+ 1.2 * constraint
+ 2.0 * confirmation
+ 1.5 * priority
+ 1.0 * artifact
- 1.5 * noise_ratio
- 2.0 * termination
- 1.0 * ambiguity_penalty
```

Rules:

- Low score plus `priority` or `confirmation` can still produce a low-confidence candidate.
- `termination` should lower score and can expire or suppress the candidate.
- A single keyword cannot produce high confidence.
- At least two core signal types are required for default candidate creation.
- High confidence should usually require object plus either problem, intent, or confirmation.

Suggested confidence mapping:

```text
high:
  score >= 5.5
  and at least 3 signal categories
  and object signal exists
  and no strong termination

medium:
  score >= 3.5
  and at least 2 signal categories

low:
  score >= 2.0
  or has priority/confirmation but missing object
```

## 10. CandidateManager

CandidateManager owns lifecycle and deduplication.

Lifecycle:

```text
suspect
  -> candidate
  -> pending_review
  -> confirmed / rejected / merged / expired
```

Phase one must implement:

- Create candidates.
- Merge similar candidates.
- Update existing candidates when new related messages arrive.
- Expire stale candidates.
- Output `pending_review` candidates.

It must not auto-create WorkDoc.

### Similarity

Candidates are similar when they share:

- Same chat.
- Overlapping source messages, or close time range.
- Similar object terms.
- Similar problem/intent text.

First version can use deterministic similarity:

```text
same chat
and time ranges within 30 minutes
and at least one shared object keyword or overlapping message ID
```

Later versions can use embeddings or LLM comparison.

## 11. Facts And Inferences

DemandRadar must separate facts from guesses.

Facts are directly supported by messages.

Example:

```json
{
  "fact": "Alice said the settings button has no response.",
  "sourceMessageIds": ["m12"]
}
```

Inferences are interpretations.

Example:

```json
{
  "inference": "This is probably a frontend navigation bug.",
  "basisMessageIds": ["m12", "m13"],
  "certainty": "medium"
}
```

No fact may exist without source message IDs.

## 12. Missing Fields

DemandRadar should identify what is missing before a candidate can become WorkDoc.

Common missing fields:

- project
- module
- page
- target_object
- expected_behavior
- actual_behavior
- assignee
- deadline
- acceptance_criteria

This is not an error. It is a review guide.

## 13. Markdown Review Draft

Each pending-review candidate should be exported as a Markdown draft.

Markdown is the human review surface. Structured JSON or database rows remain the system state.

Recommended sections:

```md
# Candidate Requirement: <hypothesis>

## Status

- Status: pending_review
- Confidence: medium
- Requirement Type: bug
- Chat: <chatName>
- Chat ID: <chatId>
- Time Range: <firstMessageTime> - <lastMessageTime>

## Why This Was Flagged

- problem: 2
- object: 1
- constraint: 1

## Evidence Messages

- [time] sender: text

## Facts

- fact text
  - Source: m1, m2

## Inferences

- inference text
  - Certainty: medium
  - Basis: m1, m2

## Missing Fields

- project: Need the target repository or project folder.
- acceptance_criteria: Need the condition that proves the fix is done.

## Human Notes

<!-- Human reviewer writes here. -->

## Review Decision

- [ ] Confirm
- [ ] Reject
- [ ] Merge with another candidate
- [ ] Expire
```

## 14. LLM Interface Reservation

DemandRadar should define a replaceable extractor interface.

```ts
interface CandidateExtractor {
  extract(blob: ContextBlob): Promise<CandidateRequirement>;
}
```

First implementation:

```text
RuleBasedCandidateExtractor
```

Future implementation:

```text
LLMCandidateExtractor
```

LLM rules:

- Use only source messages.
- Do not invent technical details.
- Separate facts and inferences.
- Attach source message IDs to every fact.
- Do not output WorkDoc.
- Do not trigger coding agents.

## 15. Human Review Actions

These actions must be reserved:

```ts
confirmCandidate(candidateId: string): void;
rejectCandidate(candidateId: string, reason: string): void;
mergeCandidates(sourceCandidateId: string, targetCandidateId: string): void;
addHumanNote(candidateId: string, note: string): void;
expireCandidate(candidateId: string): void;
```

Every action should be stored locally for audit and future feedback.

## 16. Integration With Existing Workflow

DemandRadar sits before the existing `TaskCandidate -> WorkDoc` path.

Suggested integration:

```text
Tracked chatroom messages
  -> ChatMessage
  -> DemandRadar
  -> CandidateRequirement
  -> Markdown review draft
  -> Human confirmation
  -> existing TaskCandidate or WorkDoc draft conversion
```

No automatic AgentRun is allowed from DemandRadar output.

## 17. Test Requirements

At least these cases must be tested:

1. Pure chatter should not produce candidates.
2. One complaint without object should produce no candidate or low confidence only.
3. Bug scenario: problem plus object plus expected behavior.
4. Feature request: intent plus object plus constraint.
5. Priority scenario: today / before release / urgent.
6. Artifact scenario: screenshot / log / error evidence.
7. Termination scenario: looks like demand but later says no need.
8. Repeated discussion should merge into one candidate.
9. Low-information messages do not trigger candidates but remain as context.
10. Every candidate has `sourceMessageIds`.
11. Every fact has source message IDs.
12. No candidate creates WorkDoc or AgentRun.

## 18. Acceptance Criteria

DemandRadar is acceptable when:

1. A batch of about 100 mixed normalized messages can produce `CandidateRequirement[]`.
2. The expected output size for a realistic noisy batch is about 3 to 8 cards, not dozens of fragments and not one over-compressed summary.
3. Each candidate includes evidence messages and source IDs.
4. Each candidate includes facts, inferences, missing fields, requirement type, and confidence.
5. Facts cite original messages.
6. A human reviewer can decide within about 10 seconds whether to confirm, ignore, merge, or supplement a candidate.
7. Single keywords do not create high-confidence candidates.
8. Termination signals prevent pending-review promotion.
9. Similar candidates merge.
10. Markdown review drafts are readable and actionable.
11. The module does not depend on WeChat-specific storage or login.
12. The module does not execute code, create WorkDocs, or call agents.
13. README clearly states DemandRadar only discovers candidate requirements.
