# Phase 12 Message-to-Document Pipeline Design

## 1. Purpose

Phase 12 turns the current message extraction layer into a stable deliverable:

```text
DemandMessage batch
  -> Demand extractor
  -> CandidateRequirement list
  -> human-review document markdown
  -> later human confirmation / WorkDoc promotion
```

The goal is to make the path from chat messages to a reviewable document reliable enough to hand to a user before any Agent execution happens.

## 2. Scope

This phase covers:

- A stable request/response contract for message-to-document generation.
- Local rule extractor and LLM extractor as interchangeable backends.
- A review document markdown format that contains evidence, candidate requirements, missing fields, and a human confirmation section.
- Optional local file writing for handoff to WeChat File Transfer Assistant or other notification channels.
- Tests for the API, document format, and no-execution boundary.

This phase does not cover:

- Agent execution.
- Git operations.
- Automatic WorkDoc approval.
- Automatic code editing.
- Full long-running orchestration.

## 3. Product Boundary

Raw chat messages are evidence. The generated review document is still a human-review artifact, not an execution authorization.

Allowed path:

```text
messages -> review document -> human review -> WorkDocDraft / AgentInputPack -> WorkDoc approval -> AgentRun
```

Forbidden path:

```text
messages -> AgentRun
messages -> Git
review document -> AgentRun without approval
```

## 4. API

```text
POST /message-documents/from-demand-messages
```

Request fields:

- `messages`: list of `DemandMessage`.
- `extractor`: `local` or `llm`.
- `title`: optional document title.
- `writeDocument`: whether to write the markdown file locally.

Response fields:

- `reviewDocumentId`: stable document id.
- `title`.
- `extractor`.
- `sourceMessageCount`.
- `candidateCount`.
- `candidates`.
- `markdown`.
- `documentPath` when written.
- `warnings`.

## 5. Markdown Contract

The generated markdown must contain:

1. Document metadata.
2. Source message count.
3. Extractor mode.
4. Candidate list.
5. For each candidate:
   - Type.
   - Status.
   - Confidence.
   - Hypothesis.
   - Missing fields.
   - Evidence messages.
   - Facts.
   - Inferences.
6. Human confirmation section.
7. Explicit non-execution warning.

## 6. File Output

If `writeDocument=true`, the markdown is written under:

```text
review_documents/<reviewDocumentId>.md
```

This file can later be sent to File Transfer Assistant or opened from the dashboard.

## 7. Stability Rules

- Empty message batches return a document with no candidates and a warning.
- LLM errors are surfaced as HTTP errors, not silently swallowed.
- Local extraction remains available offline.
- The response never contains API keys.
- The API does not call AgentRun, Git, or WorkDoc approval endpoints.
- Repeated requests over identical input generate stable document IDs.

## 8. Acceptance Criteria

- Local extractor can generate a review document from sample messages.
- LLM extractor can be tested through a mocked client without network access.
- `writeDocument=true` writes a markdown file.
- Markdown includes candidate evidence and human confirmation fields.
- API endpoint returns the same candidate structure used by the review workbench.
- Full backend tests pass.
