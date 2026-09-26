"""
Chief Software Engineering Orchestrator for RAMAZAN AI.
Implements the Master Orchestration Algorithm (Section 49).
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

try:
    from rich.console import Console
    console = Console()
except ImportError:
    class FallbackConsole:
        def print(self, *args, **kwargs):
            import re
            for a in args:
                print(re.sub(r'\[/?[a-zA-Z0-9_\s#=]+\]', '', str(a)))
    console = FallbackConsole()

from ramazan.config import RamazanConfig
from ramazan.schemas.task import Task, TaskStatus
from ramazan.schemas.state import ProjectState
from ramazan.schemas.memory import TaskMemory
from ramazan.schemas.review import ReviewResult
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.core.router import ModelRouter
from ramazan.core.circuit_breaker import CircuitBreaker, CircuitBreakerAction
from ramazan.core.context_builder import ContextBuilder
from ramazan.tools.fs import FileSystemTools
from ramazan.tools.test_runner import TestEngine, TestExecutionResult
from ramazan.tools.git_manager import GitManager
from ramazan.llm.client import LLMClient
from ramazan.llm.cost_tracker import CostTracker
from ramazan.llm.errors import ModelCallError
from ramazan.agents.worker_agent import WorkerAgent, WorkerOutput, ScopeViolationError, is_test_path
from ramazan.agents.reviewer_agent import ReviewerAgent
from ramazan.agents.architect_agent import ArchitectAgent

logger = logging.getLogger("ramazan.orchestrator")


class OrchestrationResult:
    def __init__(self, success: bool, message: str, state: ProjectState):
        self.success = success
        self.message = message
        self.state = state


class Orchestrator:
    def __init__(self, root_dir: Optional[Path] = None, config: Optional[RamazanConfig] = None, use_mock_llm: Optional[bool] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.config = config or RamazanConfig.load(self.root_dir)
        self.cost_tracker = CostTracker(
            max_budget_usd=self.config.system.maxBudgetUsd,
            warning_threshold=self.config.system.budgetWarningThreshold
        )
        self.llm_client = LLMClient(use_mock=use_mock_llm)

        # Core subsystems
        self.state_manager = StateManager(self.root_dir)
        self.task_engine = TaskEngine(self.root_dir)
        self.router = ModelRouter(self.config)
        self.circuit_breaker = CircuitBreaker(default_max_retries=self.config.system.maxRetries)
        self.context_builder = ContextBuilder(self.root_dir)
        self.fs = FileSystemTools(self.root_dir)
        self.test_engine = TestEngine(self.root_dir, default_command=self.config.tools.testCommand)
        self.git_manager = GitManager(self.root_dir)
        from ramazan.audit.final_audit import FinalAuditor
        self.final_auditor = FinalAuditor(
            self.root_dir,
            test_command=self.config.tools.testCommand,
            lint_command=self.config.tools.lintCommand,
            require_git=self.config.system.autoGitCommit
        )

        # Specialized Agents
        self.architect_agent = ArchitectAgent(
            model_config=self.router.get_architect_model(),
            root_dir=self.root_dir,
            llm_client=self.llm_client,
            cost_tracker=self.cost_tracker
        )

    def run_next_task(self) -> Optional[Task]:
        """
        Executes a single ready task through the full lifecycle:
        PLAN -> IMPLEMENT -> TEST -> REVIEW -> COMMIT -> MEMORY
        """
        state = self.state_manager.load()
        task = self.task_engine.select_next_ready_task(state.completedTasks)
        if not task:
            logger.info("No ready tasks available to execute.")
            return None

        self._execute_task_pipeline(task)
        return task

    def run_all(self, max_iterations: int = 50) -> OrchestrationResult:
        """
        Executes the master orchestration loop until all tasks are complete or blocked.
        Section 49: ANA ORCHESTRATION ALGORITHM.
        """
        logger.info("Starting RAMAZAN AI Orchestration Loop")
        state = self.state_manager.load()
        self.git_manager.init_if_needed()

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            state = self.state_manager.get_state()

            # Check circular dependencies
            cycles = self.task_engine.check_circular_dependencies()
            if cycles:
                msg = f"Circular dependency detected among tasks: {cycles}"
                logger.error(msg)
                self.state_manager.mark_blocked()
                return OrchestrationResult(False, msg, state)

            task = self.task_engine.select_next_ready_task(state.completedTasks)
            if not task:
                # Check if there are tasks remaining that are blocked or failed
                if self.task_engine.has_pending_tasks(state.completedTasks):
                    msg = "Pending tasks exist but none are ready. Pipeline blocked due to unmet dependencies or failures."
                    logger.warning(msg)
                    self.blocked_report()
                    self.state_manager.mark_blocked()
                    return OrchestrationResult(False, msg, state)
                else:
                    # All tasks finished!
                    break

            logger.info(f"--- Processing Task {task.id}: '{task.title}' ---")
            task_success = self._execute_task_pipeline(task)
            if not task_success and task.status == TaskStatus.ESCALATED.value:
                msg = f"Task {task.id} escalated. Human intervention or revised plan required."
                logger.error(msg)
                self.blocked_report()
                self.state_manager.mark_blocked()
                return OrchestrationResult(False, msg, self.state_manager.get_state())

        # All tasks completed, proceed to Final Audit
        logger.info("All tasks completed. Executing Final Audit Gate.")
        audit_report = self.final_auditor.run_audit()

        # Save audit report
        audit_file = self.root_dir / ".ramazan" / "FINAL_AUDIT.md"
        self.fs.write_file(".ramazan/FINAL_AUDIT.md", audit_report.to_markdown())

        if audit_report.passed:
            self.state_manager.mark_completed()
            logger.info("PROJECT COMPLETED: Final Audit PASSED!")
            return OrchestrationResult(True, "Project completed successfully with full verification.", self.state_manager.get_state())
        else:
            self.state_manager.mark_blocked()
            logger.error("PROJECT BLOCKED: Final Audit failed quality gates.")
            return OrchestrationResult(False, f"Project blocked on final audit: {audit_report.summary}", self.state_manager.get_state())

    def blocked_report(self) -> str:
        """
        Section 49 & Spec: Generates .ramazan/logs/PROJECT_BLOCKED.md detailing
        tasks that can never become READY.
        """
        logs_dir = self.root_dir / ".ramazan" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        lines = ["# PROJECT BLOCKED", "", "## Tasks that cannot become READY:"]
        state = self.state_manager.get_state()
        for t in self.task_engine.unresolved_tasks(state.completedTasks):
            missing = [d for d in t.dependencies if d not in state.completedTasks]
            lines.append(f"- **`{t.id}`** ({t.title}) waits for unresolved dependencies: `{missing}`")
        for t in self.task_engine.tasks.values():
            if t.status == TaskStatus.ESCALATED.value:
                lines.append(f"- **`{t.id}`** is ESCALATED (see `.ramazan/logs/ESCALATION-{t.id}.md`)")
        report = "\n".join(lines)
        (logs_dir / "PROJECT_BLOCKED.md").write_text(report, encoding="utf-8")
        return report

    def _execute_task_pipeline(self, task: Task) -> bool:
        """
        Executes one task through:
        WORKER -> TEST ENGINE -> REVIEWER -> MEMORY -> COMMIT
        With Circuit Breaker retry loop.
        """
        self.state_manager.start_task(task.id)
        self.task_engine.update_task_status(task.id, TaskStatus.IN_PROGRESS.value)

        # Model routing
        model_cfg = self.router.route_task(task)
        task.assignedModel = model_cfg.model
        task.assignedAgent = "Worker"
        self.task_engine.save_task(task)

        worker = WorkerAgent(
            model_config=model_cfg,
            root_dir=self.root_dir,
            llm_client=self.llm_client,
            cost_tracker=self.cost_tracker
        )
        reviewer = ReviewerAgent(
            model_config=self.router.get_reviewer_model(),
            root_dir=self.root_dir,
            llm_client=self.llm_client,
            cost_tracker=self.cost_tracker
        )

        test_failure_context: Optional[str] = None
        review_feedback_context: Optional[str] = None

        # Section 27: Initial snapshot of task target files before agent modification
        snapshot = self.fs.snapshots.create_snapshot(task.files)

        while True:
            # Check budget limit
            if self.cost_tracker.is_budget_exceeded():
                logger.critical("Aborting task execution: Budget exceeded.")
                self._handle_circuit_breaker(task, "Budget limit exceeded.", snapshot=snapshot)
                return False

            if task.status != TaskStatus.IN_PROGRESS.value:
                self.task_engine.update_task_status(task.id, TaskStatus.IN_PROGRESS.value)

            # 1. Build surgical context
            worker_prompt = self.context_builder.build_worker_prompt(
                task=task,
                test_failure=test_failure_context,
                review_feedback=review_feedback_context
            )

            # 2. Worker generates code and updates files under file locks
            logger.info(f"Delegating to Worker agent ({model_cfg.model}) for {task.id}")
            try:
                worker_output = worker.execute_task(
                    task=task,
                    context_prompt=worker_prompt,
                    strict_scope=self.config.system.strictScope
                )
                # Register any new files created by worker into snapshot
                for mod in worker_output.fileModifications:
                    if mod.path not in snapshot:
                        snapshot[mod.path] = None
                for tst in worker_output.tests:
                    if tst.path not in snapshot:
                        snapshot[tst.path] = None
            except ModelCallError as mce:
                logger.error(f"Worker model call error for {task.id}: {mce}")
                if mce.retriable:
                    action = self.circuit_breaker.check(task, failure_reason=f"Worker model error: {mce}")
                    self.task_engine.save_task(task)
                    if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                        time.sleep(2)
                        continue
                self.task_engine.update_task_status(task.id, TaskStatus.BLOCKED.value)
                self.state_manager.block_task(task.id)
                self._handle_circuit_breaker(task, str(mce), snapshot=snapshot)
                return False
            except ScopeViolationError as sve:
                logger.error(f"Scope violation in {task.id}: {sve}")
                action = self.circuit_breaker.check(task, failure_reason=f"Scope violation: {sve}")
                self.task_engine.save_task(task)
                if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                    review_feedback_context = f"SCOPE VIOLATION: {sve}. Stay strictly within allowed files: {task.files} and test files."
                    continue
                else:
                    self._handle_circuit_breaker(task, str(sve), snapshot=snapshot)
                    return False

            self.task_engine.update_task_status(task.id, TaskStatus.IMPLEMENTED.value)

            # 3. Test Engine verification (real test execution)
            self.task_engine.update_task_status(task.id, TaskStatus.TESTING.value)
            
            # Find task-specific test files
            target_tests = [
                f for f in task.files
                if ("test" in f or f.startswith("tests/")) and f.endswith(".py") and (self.root_dir / f).exists()
            ]
            if not target_tests and hasattr(worker_output, "testFiles") and worker_output.testFiles:
                target_tests = [
                    tf.path for tf in worker_output.testFiles
                    if tf.path.endswith(".py") and (self.root_dir / tf.path).exists()
                ]
            if not target_tests and hasattr(worker_output, "fileModifications") and worker_output.fileModifications:
                target_tests = [
                    m.path for m in worker_output.fileModifications
                    if ("test" in m.path or m.path.startswith("tests/")) and m.path.endswith(".py") and (self.root_dir / m.path).exists()
                ]

            test_path_arg = " ".join(target_tests) if target_tests else None

            # If running inside RAMAZAN repo itself, avoid running RAMAZAN's own framework tests for user project tasks
            if not test_path_arg and (self.root_dir / "ramazan").exists():
                framework_test_names = [
                    "test_agent_tools.py", "test_config.py", "test_orchestrator.py",
                    "test_router.py", "test_security.py", "test_ui_server.py", "test_worker_agent.py"
                ]
                ignores = " ".join([f"--ignore=tests/{fn}" for fn in framework_test_names if (self.root_dir / "tests" / fn).exists()])
                test_result = self.test_engine.run_tests(path=ignores if ignores else None)
            else:
                test_result = self.test_engine.run_tests(path=test_path_arg)

            task.testStatus = "PASSED" if test_result.passed else "FAILED"
            task.testOutput = test_result.summary

            if not test_result.passed:
                logger.warning(f"Tests FAILED for {task.id}. ExitCode: {test_result.exitCode}")
                action = self.circuit_breaker.check(task, failure_reason=f"Test failure: {test_result.summary}")
                self.task_engine.save_task(task)

                if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                    output_parts = [test_result.summary]
                    if test_result.stdout and test_result.stdout.strip():
                        output_parts.append(f"STDOUT:\n{test_result.stdout.strip()}")
                    if test_result.stderr and test_result.stderr.strip():
                        output_parts.append(f"STDERR:\n{test_result.stderr.strip()}")
                    test_failure_context = "\n\n".join(output_parts)
                    time.sleep(2)
                    continue
                else:
                    self._handle_circuit_breaker(task, test_result.summary, snapshot=snapshot)
                    return False

            logger.info(f"Tests PASSED for {task.id}.")

            # 4. Reviewer verification (Section 18 & 19)
            if self.config.system.reviewEnabled:
                self.task_engine.update_task_status(task.id, TaskStatus.REVIEWING.value)
                diff_output = self.git_manager.diff_for_task(files=task.files)
                reviewer_prompt = self.context_builder.build_reviewer_prompt(
                    task=task,
                    changes_summary=worker_output.explanation,
                    test_output=test_result.stdout or test_result.summary,
                    git_diff=diff_output
                )
                try:
                    review_result = reviewer.review_task(task, reviewer_prompt, git_diff=diff_output)
                except ModelCallError as mce:
                    logger.error(f"Reviewer model call error for {task.id}: {mce}")
                    if mce.retriable:
                        action = self.circuit_breaker.check(task, failure_reason=f"Reviewer model failure: {mce}")
                        self.task_engine.save_task(task)
                        if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                            time.sleep(2)
                            continue
                    self.task_engine.update_task_status(task.id, TaskStatus.BLOCKED.value)
                    self.state_manager.block_task(task.id)
                    self._handle_circuit_breaker(task, str(mce), snapshot=snapshot)
                    return False

                task.reviewStatus = review_result.status
                task.reviewFeedback = review_result.summary

                if not review_result.is_approved:
                    logger.warning(f"Reviewer REJECTED task {task.id}. Reason: {review_result.summary}")
                    action = self.circuit_breaker.check(task, failure_reason=f"Review rejection: {review_result.summary}")
                    self.task_engine.save_task(task)

                    if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                        review_feedback_context = f"Reviewer Issues:\n" + "\n".join([f"- {i.description} (Fix: {i.requiredFix})" for i in review_result.issues])
                        continue
                    else:
                        self._handle_circuit_breaker(task, review_result.summary, snapshot=snapshot)
                        return False
            else:
                review_result = ReviewResult(
                    status="APPROVED",
                    severity="LOW",
                    summary="Review skipped as reviewEnabled is false."
                )

            # APPROVED!
            self.task_engine.update_task_status(task.id, TaskStatus.APPROVED.value)
            logger.info(f"Task {task.id} APPROVED by Reviewer.")
            break

        # 5. Success Post-Processing
        # Create Task Memory (.ramazan/memory/TASK-XXX.md)
        self._create_task_memory(task, worker_output, test_result, review_result)

        # Commit to Git
        if self.config.system.autoGitCommit:
            all_modified = list(set(task.files + [m.path for m in worker_output.fileModifications] + [t.path for t in worker_output.tests]))
            self.git_manager.commit_task(
                task_id=task.id,
                title=task.title,
                task_type=task.type,
                files=all_modified
            )

        # Mark completed in Task Engine & State Manager
        self.task_engine.update_task_status(task.id, TaskStatus.COMPLETED.value)
        self.state_manager.complete_task(task.id)
        logger.info(f"Task {task.id} successfully completed and committed.")
        return True

    def _handle_circuit_breaker(self, task: Task, failure_reason: str, snapshot: Optional[Dict[str, Optional[str]]] = None):
        """
        Section 21, 22, 23 & Spec: Escalates task, atomically rolls back uncommitted changes,
        and generates comprehensive human escalation report.
        """
        if snapshot:
            logger.info(f"Rolling back agent modifications for {task.id} to preserve working tree.")
            self.fs.snapshots.restore_snapshot(snapshot)

        escalation = self.circuit_breaker.generate_escalation_report(task, failure_reason)
        escalation_file = self.root_dir / ".ramazan" / f"ESCALATION_{task.id}.json"
        with open(escalation_file, "w", encoding="utf-8") as f:
            f.write(escalation.model_dump_json(indent=2))

        # Also write human-readable Markdown report in .ramazan/logs/
        logs_dir = self.root_dir / ".ramazan" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        md_report = f"""# USER INTERVENTION REQUIRED
**Task:** `{task.id}` — {task.title}
**Attempts:** {task.retryCount}/{task.maxRetries}
**Status:** `ESCALATED`

## Last Failure
```
{failure_reason[:3000]}
```

## Actionable Resolution Options
- **Option A (Change Approach):** Rewrite task with an alternative design or break down into smaller sub-tasks (new task / ADR).
- **Option B (Switch Model):** Reconfigure the worker model in `.ramazan/config.json` and run again.
- **Option C (Manual Fix):** Resolve the issue manually in code, then run `ramazan task reset {task.id}` or tap "Sıfırla" in the Web UI to return the task to READY.

## Recommendation
Do not proceed automatically. Agent modifications were rolled back cleanly to preserve repository integrity.
"""
        (logs_dir / f"ESCALATION-{task.id}.md").write_text(md_report, encoding="utf-8")

        self.task_engine.update_task_status(task.id, TaskStatus.ESCALATED.value)
        self.state_manager.block_task(task.id)
        logger.critical(
            f"Escalation logged to {escalation_file.name} and logs/ESCALATION-{task.id}.md. Task {task.id} is marked ESCALATED."
        )

    def _create_task_memory(
        self,
        task: Task,
        worker_output: WorkerOutput,
        test_result: TestExecutionResult,
        review_result: ReviewResult,
    ):
        """
        Creates .ramazan/memory/TASK-XXX.md according to Section 15.
        """
        mem = TaskMemory(
            taskId=task.id,
            completed=f"{task.title}: {worker_output.explanation}",
            filesChanged=[m.path for m in worker_output.fileModifications] or task.files,
            importantDecisions=["Followed existing architecture and passed automated test suite."],
            problems=[] if task.retryCount == 0 else [f"Encountered {task.retryCount} retries before achieving passing tests & review."],
            resolution="Addressed feedback and passed all test suites.",
            tests=f"{test_result.testsRun} tests passed (duration: {test_result.duration}s).",
            futureConsiderations="Maintain test coverage as new modules integrate."
        )

        mem_dir = self.root_dir / ".ramazan" / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem_file = mem_dir / f"{task.id}.md"
        with open(mem_file, "w", encoding="utf-8") as f:
            f.write(mem.to_markdown())
        logger.info(f"Created task memory: {mem_file.name}")
