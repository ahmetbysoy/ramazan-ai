"""
Chief Software Engineering Orchestrator for RAMAZAN AI.
Implements the Master Orchestration Algorithm (Section 49).
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console

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
from ramazan.agents.worker_agent import WorkerAgent, WorkerOutput
from ramazan.agents.reviewer_agent import ReviewerAgent
from ramazan.agents.architect_agent import ArchitectAgent
from ramazan.audit.final_audit import FinalAuditor

logger = logging.getLogger("ramazan.orchestrator")
console = Console()


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
        self.final_auditor = FinalAuditor(self.root_dir, test_command=self.config.tools.testCommand)

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

        while True:
            # Check budget limit
            if self.cost_tracker.is_budget_exceeded():
                logger.critical("Aborting task execution: Budget exceeded.")
                self.state_manager.block_task(task.id)
                return False

            # 1. Build surgical context
            worker_prompt = self.context_builder.build_worker_prompt(
                task=task,
                test_failure=test_failure_context,
                review_feedback=review_feedback_context
            )

            # 2. Worker generates code and updates files under file locks
            logger.info(f"Delegating to Worker agent ({model_cfg.model}) for {task.id}")
            worker_output = worker.execute_task(task, worker_prompt)
            self.task_engine.update_task_status(task.id, TaskStatus.IMPLEMENTED.value)

            # 3. Test Engine verification (real test execution)
            self.task_engine.update_task_status(task.id, TaskStatus.TESTING.value)
            test_result = self.test_engine.run_tests()
            task.testStatus = "PASSED" if test_result.passed else "FAILED"
            task.testOutput = test_result.summary

            if not test_result.passed:
                logger.warning(f"Tests FAILED for {task.id}. ExitCode: {test_result.exitCode}")
                action = self.circuit_breaker.check(task, failure_reason=f"Test failure: {test_result.summary}")
                self.task_engine.save_task(task)

                if action == CircuitBreakerAction.RETRY_WITH_FEEDBACK:
                    test_failure_context = f"{test_result.summary}\n{test_result.stderr or test_result.stdout}"
                    continue
                else:
                    self._handle_circuit_breaker(task, test_result.summary)
                    return False

            logger.info(f"Tests PASSED for {task.id}.")

            # 4. Reviewer verification (Section 18 & 19)
            self.task_engine.update_task_status(task.id, TaskStatus.REVIEWING.value)
            reviewer_prompt = self.context_builder.build_reviewer_prompt(
                task=task,
                changes_summary=worker_output.explanation,
                test_output=test_result.stdout or test_result.summary
            )
            review_result = reviewer.review_task(task, reviewer_prompt)
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
                    self._handle_circuit_breaker(task, review_result.summary)
                    return False

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

    def _handle_circuit_breaker(self, task: Task, failure_reason: str):
        escalation = self.circuit_breaker.generate_escalation_report(task, failure_reason)
        escalation_file = self.root_dir / ".ramazan" / f"ESCALATION_{task.id}.json"
        with open(escalation_file, "w", encoding="utf-8") as f:
            f.write(escalation.model_dump_json(indent=2))

        self.task_engine.update_task_status(task.id, TaskStatus.ESCALATED.value)
        self.state_manager.block_task(task.id)
        logger.critical(
            f"Escalation logged to {escalation_file.name}. Task {task.id} is marked ESCALATED."
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
