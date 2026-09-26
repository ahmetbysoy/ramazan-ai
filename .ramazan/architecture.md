# RAMAZAN AI System Architecture

## 1. System Philosophy
RAMAZAN AI functions as a Chief Software Engineering Orchestrator coordinating specialized agents.
Core execution cycle:
`PLAN ↓ BREAK DOWN ↓ DELEGATE ↓ IMPLEMENT ↓ TEST ↓ REVIEW ↓ FIX ↓ RETEST ↓ COMMIT ↓ NEXT TASK`

Never: `PROMPT ↓ CODE ↓ DONE`.

## 2. Source of Truth Principle
- Models propose changes, but executable code and tests determine reality.
- A model claiming "the code works" is invalid without actual passing tests from the Test Engine.
- `state.json` is deterministically managed by the system, not directly altered by LLM text.

## 3. Module Boundaries
```
┌────────────────────────────────────────────────────────┐
│                        CLI / UX                        │
│                 (ramazan init/plan/run)                │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                 Orchestration Core                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Orchestrator (Lifecycle & Conflict Resolution)     │ │
│ │ TaskEngine (Dependency Graph & Priority Queue)     │ │
│ │ StateManager (Deterministic .ramazan/state.json)   │ │
│ │ CircuitBreaker (Retries, Options A/B/C)            │ │
│ │ ModelRouter (Complexity-based Routing)             │ │
│ │ ContextBuilder (Surgical context assembly)         │ │
│ └────────────────────────────────────────────────────┘ │
└──────────────────────────┬─────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
┌────────▼────────┐ ┌──────▼───────┐ ┌───────▼────────┐
│   Architect     │ │    Worker    │ │    Reviewer    │
│  (ADR, System)  │ │(Code Writer) │ │(Code Inspector)│
└─────────────────┘ └──────┬───────┘ └───────┬────────┘
                           │                 │
┌──────────────────────────▼─────────────────▼────────┐
│                     Tools Layer                     │
│  - File System Tools (Safe read/write/edit/lock)    │
│  - Unified Patch Engine (Unified diff & hunks)      │
│  - Agent Tool Dispatcher (Interactive tool loop)    │
│  - Terminal Executor (Command policy enforcement)   │
│  - Test Engine (Objective pytest/cargo/npm runner)  │
│  - Git Manager (Real git diff, commits, rollback)   │
└─────────────────────────────────────────────────────┘
```

## 4. Agent Responsibilities
- **Orchestrator**: Master planner, task lifecycle controller, circuit breaker enforcer, escalation manager.
- **Architect**: System design, technology choices, module constraints, ADR authoring (Claude 3.7 Sonnet).
- **Worker**: Multi-turn tool loop code generation, minimal diff patches and tests. Never touches files outside strict scope (DeepSeek-V3).
- **Reviewer**: Strictly verifies correctness, security, performance, edge cases, real git diff minimality, and architectural compliance. Outputs structured JSON (Grok-2 / Claude).
- **Test Engine**: Independent non-LLM execution of real test tools.

## 5. Security & Isolation
- Secret Management: Zero secrets in prompt context, logs, or repo files.
- Command Policy: Destructive commands (`rm -rf /`, formatting, raw disk writes) are hard-blocked.
- File Locking: Concurrent tasks cannot touch overlapping files.

## 6. Architecture Immutability
Rules defined in this file cannot be bypassed or modified silently by Worker agents.
Any suggested architectural shift requires:
`PROPOSAL ↓ ORCHESTRATOR ↓ ARCHITECT REVIEW ↓ DECISION ↓ ADR ↓ architecture.md update`.
