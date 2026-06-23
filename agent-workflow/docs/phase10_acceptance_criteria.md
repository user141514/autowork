# Phase 10 Acceptance Criteria

## 1. Scope

These criteria accept Phase 10: Requirement Review Workbench.

The accepted product path is:

```text
ChatMessage or DemandMessage
-> DemandRadar
-> CandidateRequirement
-> HumanReviewDecision
-> WorkDocDraft
-> AgentInputPack
-> existing WorkDoc / AgentRun execution chain
```

## 2. Documentation Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| DOC-001 | Phase 10 design document exists | `agent-workflow/docs/phase10_requirement_review_workbench.md` |
| DOC-002 | Acceptance criteria document exists | `agent-workflow/docs/phase10_acceptance_criteria.md` |
| DOC-003 | Official object responsibilities are defined | ChatMessage, CandidateRequirement, WorkDocDraft, WorkDoc, AgentInputPack separated |
| DOC-004 | Forbidden transitions are documented | Raw chat cannot create AgentRun |

## 3. Workbench UI Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| UI-001 | `GET /review-workbench` exists | Returns HTTP 200 |
| UI-002 | Workbench page identifies itself | Contains `Requirement Review Workbench` |
| UI-003 | Page exposes Demand Radar action | Contains `Extract candidates` |
| UI-004 | Page exposes promotion action | Contains `Promote` |
| UI-005 | Page explains non-execution boundary | States raw/review output does not auto-execute code |

## 4. Demand Radar Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| DR-001 | Workbench can call `/demand-radar/extract` | Candidate extraction request shape is present in JavaScript |
| DR-002 | Candidate cards are rendered | Candidate id, type, status, confidence displayed |
| DR-003 | Selection preserves full candidate JSON | Selected candidate output visible |
| DR-004 | Extraction remains review-only | No AgentRun endpoint called from extraction |

## 5. Human Review Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| HR-001 | Reviewer field exists | Human reviewer is captured |
| HR-002 | Decision field exists | confirm/reject/merge/expire available |
| HR-003 | Project or repo field exists | Promotion receives projectOrRepo |
| HR-004 | Scope field exists | Promotion receives scope |
| HR-005 | Constraints field exists | Promotion receives constraints |
| HR-006 | Acceptance criteria field exists | Promotion receives acceptanceCriteria |
| HR-007 | Human notes field exists | Promotion receives humanNotes |

## 6. Promotion Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| PR-001 | Workbench can call `/requirement-promotion/promote` | Request includes candidate and decision |
| PR-002 | Promotion result is displayed | WorkDocDraft / AgentInputPack / brief visible |
| PR-003 | Optional inbox write is supported | `writeInbox=true` path available |
| PR-004 | Promotion does not call AgentRun | No `/agent-runs/from-workdoc` call in workbench JS |
| PR-005 | Promotion does not call Git | No Git endpoint call in workbench JS |

## 7. Safety Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| SAFE-001 | Raw chat is evidence only | Workbench text and docs state this boundary |
| SAFE-002 | Agent execution remains gated | Workbench does not create AgentRun |
| SAFE-003 | Git remains gated | Workbench does not call Git endpoints |
| SAFE-004 | Existing PolicyGate remains authoritative | Docs do not weaken Phase 8 rules |
| SAFE-005 | Review is required before promotion | HumanReviewDecision is required by API |

## 8. Test Acceptance

| ID | Criterion | Required Result |
|---|---|---|
| TEST-001 | Workbench route smoke test exists | Test client checks `/review-workbench` |
| TEST-002 | Existing backend test suite passes | `python -m pytest` succeeds |
| TEST-003 | No regression in workflow tests | `test_workflow.py` still passes |
| TEST-004 | No regression in demand radar tests | `test_demand_radar.py` still passes |
| TEST-005 | No regression in requirement promotion tests | `test_requirement_promotion.py` still passes |

## 9. Definition of Done

Phase 10 is accepted only when all of the following are true:

1. Documentation exists and defines the official review chain.
2. `/review-workbench` is registered in FastAPI.
3. The page demonstrates chat batch to candidate to promotion flow.
4. The page does not execute agents or Git operations.
5. A route smoke test exists.
6. The full backend test suite passes.
