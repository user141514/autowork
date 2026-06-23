# Phase 10 Requirement Review Workbench Design

## 1. Purpose

Phase 10 turns the existing chat-intake and execution-chain modules into one product-grade review flow:

```text
ChatMessage -> DemandRadar -> CandidateRequirement -> HumanReviewDecision -> WorkDocDraft -> AgentInputPack -> Phase 8 execution chain
```

The phase is not about adding another WeChat connector or another coding agent. Its purpose is to standardize the requirement-review layer between noisy group chat and autonomous code execution.

## 2. Current Baseline

The repository already contains these capabilities:

- Phase 8 execution chain: WorkDoc, RepoContext, AgentRunner, TestRunner, PolicyGate, GitPublisher, reports.
- Phase 9 intake chain: manual chat import, wxauto adapter, readable SQLite polling, command logs, segments, task candidates.
- Demand Radar: batch extraction of candidate requirements from noisy chat.
- Requirement Promotion: human-reviewed candidate to WorkDoc draft, AgentInputPack, and markdown agent brief.

Phase 10 freezes the official product path around Demand Radar and Requirement Promotion.

## 3. Non-Goals

Phase 10 does not implement:

- New WeChat extraction techniques.
- Direct local database decryption.
- More agent runners.
- Auto-execution from raw chat messages.
- Full production frontend rewrite.

## 4. Official Flow

### 4.1 Intake

Messages may come from manual exports, wxauto polling, readable SQLite imports, or mock API calls. Regardless of source, they must become normalized ChatMessage records or DemandMessage payloads before analysis.

### 4.2 Demand Radar

Demand Radar reads a bounded batch of chat messages and returns CandidateRequirement objects.

It may infer candidate requirements, but it must not:

- Create WorkDocs directly.
- Run agents.
- Touch Git.
- Treat raw chat text as execution authority.

### 4.3 Human Review

A human reviewer must decide whether a CandidateRequirement is confirmed, rejected, merged, or expired.

For confirmed requirements, the reviewer supplies:

- Project or repository.
- Working directory when available.
- Scope.
- Constraints.
- Acceptance criteria.
- Out-of-scope boundaries.
- Whether an agent is allowed to proceed.

### 4.4 Requirement Promotion

RequirementPromotion converts the reviewed candidate into:

- WorkDocDraft.
- AgentInputPack.
- Agent brief markdown.
- Optional local inbox files under `.agent-work/inbox`.

This is the first artifact that is suitable for a coding agent to read.

### 4.5 Execution Boundary

The output of Phase 10 still does not bypass the existing Phase 8 controls. Code execution must remain gated by WorkDoc validation, approval, PolicyGate, tests, and Git dry-run/commit policy.

## 5. Object Responsibilities

| Object | Responsibility | Not Responsible For |
|---|---|---|
| ChatMessage | Persisted chat evidence | Requirement judgment |
| DemandMessage | Batch-analysis input | Storage or execution |
| CandidateRequirement | Reviewable requirement hypothesis | Code execution |
| HumanReviewDecision | Human confirmation and missing fields | Repository mutation |
| WorkDocDraft | Reviewed task contract draft | Direct Git operations |
| AgentInputPack | Agent-readable execution packet | Policy bypass |
| WorkDoc | Persisted execution contract | Raw chat interpretation |
| AgentRun | Controlled execution attempt | Intake or review |

## 6. State Rules

Allowed path:

```text
ChatMessage/DemandMessage -> CandidateRequirement -> HumanReviewDecision -> WorkDocDraft/AgentInputPack -> WorkDoc -> AgentRun
```

Forbidden paths:

```text
ChatMessage -> AgentRun
CandidateRequirement -> AgentRun
DemandRadar -> Git
HumanReviewDecision -> Git
```

## 7. Workbench UI

Phase 10 adds a lightweight HTML workbench at:

```text
GET /review-workbench
```

The page demonstrates the complete review layer:

1. Load a sample chat batch.
2. Extract candidate requirements through `/demand-radar/extract`.
3. Select a candidate.
4. Fill human review fields.
5. Promote through `/requirement-promotion/promote`.
6. Inspect WorkDocDraft, AgentInputPack, and Agent brief markdown.

The UI is intentionally simple HTML/JavaScript. It is a review console, not a production frontend rewrite.

## 8. Agent Input Pack Contract

Every AgentInputPack must include:

- Target project or repository.
- Working directory when provided.
- Task objective.
- Context.
- Evidence messages.
- Constraints.
- Acceptance criteria.
- Execution policy.
- Output contract.

The agent input pack should be sufficient for Claude CLI, gagent-desktop, or a future worker to understand the task without reading raw chat history directly.

## 9. Safety Requirements

- Raw chat messages remain evidence only.
- Demand Radar outputs hypotheses only.
- Human review is mandatory before promotion.
- Missing acceptance criteria must block promotion.
- Agent permissions must be explicit in the human decision.
- No raw chat message may create AgentRun.
- Existing PolicyGate and WorkDoc approval rules remain authoritative.

## 10. Implementation Deliverables

- `docs/phase10_requirement_review_workbench.md`
- `docs/phase10_acceptance_criteria.md`
- `GET /review-workbench`
- Dashboard or README links to the workbench
- Smoke test for the workbench route
- Existing test suite passing

## 11. Definition of Done

Phase 10 is complete when:

1. The official chain is documented.
2. CandidateRequirement, TaskCandidate, WorkDocDraft, WorkDoc, and AgentInputPack responsibilities are explicitly separated.
3. `/review-workbench` shows DemandRadar-to-RequirementPromotion flow.
4. The route is included in FastAPI router registration.
5. A smoke test proves the HTML interface is served.
6. Existing tests pass.
