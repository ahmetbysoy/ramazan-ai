# Project Requirements

## Product Overview
RAMAZAN AI autonomous software engineering system for deterministic task planning, multi-agent code implementation, continuous test verification, strict code review, and automated git delivery.

## Functional Requirements
1. **Deterministic Task Engine**:
   - Parse requirements into structured tasks (`TASK-XXX.json`).
   - Validate task dependencies with DAG resolution.
   - Enforce lifecycle transitions: PENDING -> READY -> ASSIGNED -> IN_PROGRESS -> IMPLEMENTED -> TESTING -> REVIEWING -> APPROVED -> COMPLETED.
2. **Multi-Agent Orchestration**:
   - Orchestrator: High-level reasoning and coordination.
   - Architect: Module boundaries, technology stacks, ADRs.
   - Worker: Code generation targeted to specific task files.
   - Reviewer: Structured critique returning `APPROVED` or `CHANGES_REQUIRED`.
   - Test Engine: Objective execution of unit/integration test suites.
3. **Model Router**:
   - Route tasks by complexity: LOW (cheap/fast), MEDIUM (balanced), HIGH (reasoning), CRITICAL (ensemble).
   - Track token usage and enforce project budget limits ($USD).
4. **Resilience & Circuit Breaker**:
   - Limit retries to 3 per task.
   - On breach: Option A (Change approach), Option B (Switch model), Option C (Human escalation).
5. **Memory & Immutability**:
   - Generate `.ramazan/memory/TASK-XXX.md` for completed tasks.
   - Author ADRs in `.ramazan/decisions/ADR-XXX.md` for architectural changes.
6. **Tool & Command Security**:
   - Prohibit dangerous terminal operations (`rm -rf`, format, credential leaks).
   - Enforce mandatory command metadata: COMMAND, PURPOSE, EXPECTED EFFECT, RISK.
7. **Git & Final Audit**:
   - Atomic git commits per completed task (`feat:`, `fix:`, etc.).
   - Full final audit before marking project `COMPLETED`.
