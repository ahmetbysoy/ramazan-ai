"""
CLI Entry Point for RAMAZAN AI.
Multi-Agent Autonomous Software Engineering System.
Features dual execution: native Typer & Rich when available, with an automatic
built-in argparse & standard-library fallback for minimal environments (Termux, Alpine, clean containers).
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from typing import List, Optional

# --- DUAL BACKEND IMPORT (TYPER & RICH WITH ZERO-DEPENDENCY FALLBACKS) ---
try:
    import typer
    from typer import Typer, Option, Argument, Exit
    HAS_TYPER = True
except ImportError:
    HAS_TYPER = False
    typer = None

    class Exit(SystemExit):
        def __init__(self, code: int = 0):
            super().__init__(code)

    def Option(default=None, *args, **kwargs):
        return default

    def Argument(default=None, *args, **kwargs):
        return None if default is ... else default

    class Typer:
        def __init__(self, *args, **kwargs):
            self.commands = {}
            self.sub_typers = {}

        def command(self, name=None, *args, **kwargs):
            def decorator(f):
                cmd_name = name or f.__name__.replace("cmd_", "").replace("_", "-")
                self.commands[cmd_name] = f
                return f
            return decorator

        def add_typer(self, sub, name=None, *args, **kwargs):
            self.sub_typers[name] = sub

        def __call__(self, *args, **kwargs):
            return run_argparse_cli()


try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

    class Console:
        def print(self, *args, **kwargs):
            for a in args:
                cleaned = re.sub(r'\[/?[a-zA-Z0-9_\s#=:\-\.\/\(\)]+\]', '', str(a))
                print(cleaned)

    class Table:
        def __init__(self, title="", show_lines=False):
            self.title = title
            self.columns = []
            self.rows = []

        def add_column(self, name, **kwargs):
            self.columns.append(name)

        def add_row(self, *row):
            self.rows.append([str(c) for c in row])

        def __str__(self):
            lines = [f"\n=== {self.title} ==="]
            if self.columns:
                lines.append(" | ".join(self.columns))
                lines.append("-" * 60)
            for r in self.rows:
                cleaned = [re.sub(r'\[/?[a-zA-Z0-9_\s#=:\-\.\/\(\)]+\]', '', c) for c in r]
                lines.append(" | ".join(cleaned))
            lines.append("=" * (len(lines[0]) if lines else 40) + "\n")
            return "\n".join(lines)

    class Panel:
        def __init__(self, content, title="", border_style=""):
            self.content = content
            self.title = title

        def __str__(self):
            cleaned = re.sub(r'\[/?[a-zA-Z0-9_\s#=:\-\.\/\(\)]+\]', '', str(self.content))
            return f"\n┌── {self.title} ──┐\n{cleaned}\n└{'─' * (len(self.title) + 8)}┘\n"


def prompt_input(text: str, hide_input: bool = False) -> str:
    if HAS_TYPER and typer is not None:
        try:
            return typer.prompt(text, hide_input=hide_input)
        except Exception:
            pass
    import getpass
    if hide_input:
        return getpass.getpass(f"{text}: ")
    return input(f"{text}: ")


from ramazan.config import RamazanConfig, find_project_root
from ramazan.core.orchestrator import Orchestrator
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.audit.final_audit import FinalAuditor
from ramazan.tools.test_runner import TestEngine
from ramazan.tools.git_manager import GitManager
from ramazan.schemas.task import Task
from ramazan.schemas.adr import ADRManager

app = Typer(
    name="ramazan",
    help="RAMAZAN AI - Multi-Agent Autonomous Software Engineering Orchestrator",
)
task_app = Typer(name="task", help="Task management and inspection commands")
adr_app = Typer(name="adr", help="Architecture Decision Record (ADR) commands")

app.add_typer(task_app, name="task")
app.add_typer(adr_app, name="adr")
console = Console()


@app.command()
def init(
    project_name: Optional[str] = Option(None, "--name", "-n", help="Name of the project"),
):
    """
    Initialize the .ramazan orchestration directory structure in current directory.
    """
    root_dir = Path.cwd()
    ramazan_dir = root_dir / ".ramazan"

    subdirs = ["decisions", "tasks", "memory", "reviews", "tests", "logs"]
    for sd in subdirs:
        (ramazan_dir / sd).mkdir(parents=True, exist_ok=True)

    # Config
    config = RamazanConfig()
    config.save(root_dir)

    # State
    p_name = project_name or root_dir.name
    state_mgr = StateManager(root_dir)
    state = state_mgr.load()
    state.project = p_name
    state_mgr.save()

    # Git
    git_mgr = GitManager(root_dir)
    git_mgr.init_if_needed()

    # Architecture & Requirements templates
    arch_file = ramazan_dir / "architecture.md"
    if not arch_file.exists():
        arch_file.write_text(
            "# System Architecture\n\n## Principles\n- Clean modular code\n- Full unit tests\n- Immutability\n",
            encoding="utf-8"
        )

    req_file = ramazan_dir / "requirements.md"
    if not req_file.exists():
        req_file.write_text(
            "# Project Requirements\n\nDescribe your feature or application requirements here.\n",
            encoding="utf-8"
        )

    console.print(Panel(
        f"[bold green]RAMAZAN AI Initialized Successfully![/bold green]\n"
        f"Project: [cyan]{p_name}[/cyan]\n"
        f"Directory: [yellow]{ramazan_dir}[/yellow]\n"
        f"State: [magenta]{state.status}[/magenta]",
        title="RAMAZAN AI",
        border_style="green"
    ))


@app.command(name="doctor")
def doctor():
    """
    Run environment and configuration diagnostics, model validation, and schema verification.
    """
    from ramazan.audit.doctor import RamazanDoctor
    root_dir = find_project_root()
    doc = RamazanDoctor(root_dir)
    success, results = doc.run_diagnostics()

    console.print("[bold cyan]RAMAZAN AI - System & Model Diagnostics[/bold cyan]\n")
    for r in results:
        status_tag = "[bold green]PASS[/bold green]" if r.passed else "[bold red]FAIL[/bold red]"
        console.print(f"{status_tag} {r.name}: {r.message}")

    if not success:
        console.print("\n[bold red]Doctor reported failures. Please check your configuration.[/bold red]")
        raise Exit(1)
    else:
        console.print("\n[bold green]All doctor diagnostics passed successfully![/bold green]")


@app.command(name="version")
def version():
    """
    Print the RAMAZAN AI version.
    """
    import ramazan
    ver = getattr(ramazan, "__version__", "0.1.0")
    console.print(f"[bold cyan]RAMAZAN AI[/bold cyan] v{ver} (Autonomous Software Engineering Agent)")


@app.command()
def status():
    """
    Display current project status, task progress, and system health.
    """
    root_dir = find_project_root()
    state_mgr = StateManager(root_dir)
    task_engine = TaskEngine(root_dir)
    state = state_mgr.load()

    # Status panel
    color = "green" if state.status in ["COMPLETED", "TASKS_COMPLETED"] else ("yellow" if state.status == "IN_PROGRESS" else "cyan")
    console.print(Panel(
        f"[bold]Project:[/bold] {state.project} | [bold]Status:[/bold] [{color}]{state.status}[/{color}]\n"
        f"[bold]Current Task:[/bold] {state.currentTask or 'None'} | [bold]Last Updated:[/bold] {state.lastUpdated}\n"
        f"[bold]Progress:[/bold] {state.progress}% ({len(state.completedTasks)}/{state.totalTasks} tasks completed)",
        title=f"RAMAZAN AI - Project Status",
        border_style=color
    ))

    # Tasks Table
    table = Table(title="Task Graph & States", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Priority", style="yellow")
    table.add_column("Complexity", style="magenta")
    table.add_column("Dependencies", style="blue")
    table.add_column("Status", style="bold", no_wrap=True)
    table.add_column("Retries", justify="right")

    for t_id, task in task_engine.tasks.items():
        st_color = "green" if task.status == "COMPLETED" else ("yellow" if task.status == "IN_PROGRESS" else ("red" if task.status in ["FAILED", "ESCALATED"] else "dim"))
        deps = ", ".join(task.dependencies) if task.dependencies else "-"
        table.add_row(
            task.id,
            task.title,
            task.priority.upper(),
            task.complexity.upper(),
            deps,
            f"[{st_color}]{task.status}[/{st_color}]",
            f"{task.retryCount}/{task.maxRetries}"
        )

    console.print(table)


# ---------------- TASK SUBCOMMANDS ----------------

@task_app.command(name="add")
def cmd_task_add(
    title: str = Argument(..., help="Task title"),
    desc: str = Option("", "--desc", "-d", help="Task description"),
    task_type: str = Option("implementation", "--type", "-t", help="Task type (implementation, bugfix, test, refactor, documentation)"),
    priority: str = Option("medium", "--priority", "-p", help="Priority (critical, high, medium, low)"),
    complexity: str = Option("medium", "--complexity", "-c", help="Complexity (low, medium, high, critical)"),
    deps: Optional[str] = Option(None, "--deps", help="Comma-separated dependency task IDs (e.g. TASK-001,TASK-002)"),
    files: Optional[str] = Option(None, "--files", help="Comma-separated file paths in scope"),
    criteria: Optional[str] = Option(None, "--criteria", help="Comma-separated acceptance criteria"),
):
    """
    Create and register a new deterministic engineering task.
    """
    root_dir = find_project_root()
    task_engine = TaskEngine(root_dir)
    config = RamazanConfig.load(root_dir)

    dependencies_list = [d.strip() for d in deps.split(",") if d.strip()] if deps else []
    files_list = [f.strip() for f in files.split(",") if f.strip()] if files else []
    criteria_list = [c.strip() for c in criteria.split(",") if c.strip()] if criteria else []

    task_id = task_engine.next_task_id()
    task = Task(
        id=task_id,
        title=title,
        description=desc or title,
        type=task_type,
        priority=priority,
        complexity=complexity,
        dependencies=dependencies_list,
        files=files_list,
        acceptanceCriteria=criteria_list,
        maxRetries=config.system.maxRetries,
    )
    task_engine.add_task(task)

    state_mgr = StateManager(root_dir)
    state_mgr.recompute(task_engine)

    console.print(f"[bold green]Created task {task.id}:[/bold green] {task.title}")
    if not task.acceptanceCriteria:
        console.print("[yellow]Warning: Task has no measurable acceptance criteria (Section 11).[/yellow]")


@task_app.command(name="list")
def cmd_task_list():
    """
    List all tasks, states, dependencies, and retry counters.
    """
    status()


@task_app.command(name="reset")
def cmd_task_reset(
    task_id: str = Argument(..., help="Task ID to reset, e.g. TASK-001"),
):
    """
    Section 23 & Spec: Reset an ESCALATED, BLOCKED, or FAILED task back to READY
    after human-in-the-loop inspection or code resolution.
    """
    root_dir = find_project_root()
    task_engine = TaskEngine(root_dir)
    try:
        task = task_engine.reset_task(task_id)
        state_mgr = StateManager(root_dir)
        state = state_mgr.load()
        if task_id in state.blockedTasks:
            state.blockedTasks.remove(task_id)
        if task_id in state.failedTasks:
            state.failedTasks.remove(task_id)
        if state.status == "BLOCKED":
            state.status = "IN_PROGRESS"
        state_mgr.save()

        console.print(Panel(
            f"[bold green]Task {task.id} successfully reset to READY![/bold green]\n"
            f"Title: {task.title}\n"
            f"Retries reset to: 0\n"
            f"Pipeline can now proceed with `ramazan step` or `ramazan run`.",
            title="RAMAZAN AI - Task Reset",
            border_style="green"
        ))
    except KeyError:
        console.print(f"[bold red]Task '{task_id}' not found.[/bold red]")
        raise Exit(1)


@app.command(name="reset")
def alias_task_reset(
    task_id: str = Argument(..., help="Task ID to reset"),
):
    """
    Quick alias to reset an ESCALATED task back to READY (ramazan reset TASK-XXX).
    """
    cmd_task_reset(task_id=task_id)


# ---------------- ADR SUBCOMMANDS ----------------

@adr_app.command(name="new")
def cmd_adr_new(
    decision: str = Argument(..., help="Core architecture decision"),
    context: str = Option("", "--context", "-c", help="Context and problem motivation"),
    alternatives: Optional[str] = Option(None, "--alternatives", "-a", help="Comma-separated alternatives considered"),
    reason: str = Option("", "--reason", "-r", help="Reason for choosing this option"),
    consequences: str = Option("", "--consequences", help="Positive and negative trade-offs"),
    title: str = Option("", "--title", help="ADR Title (optional)"),
):
    """
    Section 16: Create and append a new Architecture Decision Record (ADR).
    Old ADRs are immutable and never deleted.
    """
    root_dir = find_project_root()
    alts_list = [a.strip() for a in alternatives.split(",") if a.strip()] if alternatives else []
    adr = ADRManager.create_adr(
        root_dir=root_dir,
        decision=decision,
        context=context or "Architectural evolution requirement.",
        alternatives=alts_list,
        reason=reason or "Selected for optimal modularity and specification compliance.",
        consequences=consequences or "Enhances determinism and system resilience.",
        title=title or decision
    )
    console.print(Panel(
        f"[bold green]ADR Recorded Successfully: {adr.id}[/bold green]\n"
        f"Title: [cyan]{adr.title}[/cyan]\n"
        f"Decision: {adr.decision}\n"
        f"File: [yellow].ramazan/decisions/{adr.id}.md[/yellow]",
        title="RAMAZAN AI - Architecture Decision",
        border_style="green"
    ))


@adr_app.command(name="list")
def cmd_adr_list():
    """
    List all recorded Architecture Decision Records (ADRs).
    """
    root_dir = find_project_root()
    adrs = ADRManager.list_adrs(root_dir)
    if not adrs:
        console.print("[yellow]No ADRs recorded yet. Create one with `ramazan adr new ...`[/yellow]")
        return

    table = Table(title="Architecture Decision Records (ADRs)", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title / Decision", style="white")
    table.add_column("Reason", style="green")
    table.add_column("Alternatives", style="magenta")

    for adr in adrs:
        alts = ", ".join(adr.alternatives) if adr.alternatives else "-"
        table.add_row(adr.id, adr.title or adr.decision, adr.reason or "-", alts)

    console.print(table)


@app.command()
def plan(
    prompt: Optional[str] = Argument(None, help="Inline requirement or project description to plan"),
    req_file: Optional[Path] = Option(None, "--file", "-f", help="Path to requirements file"),
    use_mock: bool = Option(False, "--mock", help="Use deterministic mock model for offline planning"),
):
    """
    Break down requirements into deterministic tasks using the Orchestrator Agent.
    """
    if not (Path.cwd() / ".ramazan").exists():
        init()
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)
    orchestrator = Orchestrator(root_dir, config, use_mock_llm=use_mock)

    req_path = req_file or (root_dir / ".ramazan" / "requirements.md")
    if prompt:
        req_path.parent.mkdir(parents=True, exist_ok=True)
        req_path.write_text(f"# Proje Gereksinimleri\n\n## Kullanıcı Talebi\n{prompt}\n", encoding="utf-8")
    elif not req_path.exists():
        console.print(f"[red]Requirements file not found at {req_path}. Provide an inline prompt: ramazan plan 'proje talebi'[/red]")
        raise Exit(1)

    requirements = req_path.read_text(encoding="utf-8")
    arch = orchestrator.context_builder.load_architecture_rules()

    console.print("[cyan]Orchestrator Agent analyzing requirements and planning task graph...[/cyan]")

    from ramazan.agents.orchestrator_agent import OrchestratorAgent
    orch_agent = OrchestratorAgent(
        model_config=orchestrator.router.get_orchestrator_model(),
        llm_client=orchestrator.llm_client,
        cost_tracker=orchestrator.cost_tracker
    )

    planned_tasks = orch_agent.plan_project(requirements, arch)

    for t in planned_tasks:
        orchestrator.task_engine.add_task(t)

    orchestrator.state_manager.recompute(orchestrator.task_engine)

    console.print(f"[bold green]Successfully generated {len(planned_tasks)} deterministic tasks![/bold green]")
    for t in planned_tasks:
        console.print(f"- [cyan]{t.id}[/cyan]: {t.title} [dim]({t.complexity} complexity)[/dim]")


@app.command(name="start")
def start_project(
    prompt: str = Argument(..., help="Feature or project description to plan and build autonomously"),
    mock: bool = Option(False, "--mock", help="Run with deterministic simulation for development/testing"),
):
    """
    All-in-one command: Plan and execute a software engineering project end-to-end.
    """
    if not (Path.cwd() / ".ramazan").exists():
        init()
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)
    orchestrator = Orchestrator(root_dir, config, use_mock_llm=mock)

    req_path = root_dir / ".ramazan" / "requirements.md"
    req_path.parent.mkdir(parents=True, exist_ok=True)
    req_path.write_text(f"# Proje Gereksinimleri\n\n## Kullanıcı Talebi\n{prompt}\n", encoding="utf-8")

    requirements = req_path.read_text(encoding="utf-8")
    arch = orchestrator.context_builder.load_architecture_rules()

    console.print(f"[bold cyan]RAMAZAN AI - Starting Autonomous Engineering for:[/bold cyan] {prompt}")
    console.print("[cyan]1. Orchestrator Agent planning DAG task graph...[/cyan]")

    from ramazan.agents.orchestrator_agent import OrchestratorAgent
    orch_agent = OrchestratorAgent(
        model_config=orchestrator.router.get_orchestrator_model(),
        llm_client=orchestrator.llm_client,
        cost_tracker=orchestrator.cost_tracker
    )

    planned_tasks = orch_agent.plan_project(requirements, arch)

    for t in planned_tasks:
        orchestrator.task_engine.add_task(t)

    orchestrator.state_manager.recompute(orchestrator.task_engine)

    console.print(f"[green]Planned {len(planned_tasks)} atomic tasks. Executing autonomous pipeline...[/green]")
    result = orchestrator.run_all()

    if result.success:
        console.print(Panel(
            f"[bold green]PROJECT COMPLETED SUCCESSFULLY![/bold green]\n\n"
            f"{result.message}\n"
            f"Tasks Completed: {len(result.state.completedTasks)}/{result.state.totalTasks}\n"
            f"Total Cost: ${orchestrator.cost_tracker.total_cost_usd:.4f}",
            title="RAMAZAN AI - SUCCESS",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]PROJECT EXECUTION STOPPED / BLOCKED[/bold red]\n\n"
            f"{result.message}\n"
            f"State: {result.state.status}",
            title="RAMAZAN AI - BLOCKED",
            border_style="red"
        ))
        raise Exit(1)


@app.command()
def run(
    mock: bool = Option(False, "--mock", help="Run with deterministic simulation for development/testing"),
    max_steps: int = Option(50, "--max-steps", help="Maximum task iterations"),
):
    """
    Execute the master orchestration loop until all tasks are complete or blocked.
    """
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)
    orchestrator = Orchestrator(root_dir, config, use_mock_llm=mock)

    console.print("[bold cyan]Starting RAMAZAN AI Autonomous Orchestration...[/bold cyan]")
    result = orchestrator.run_all(max_iterations=max_steps)

    if result.success:
        console.print(Panel(
            f"[bold green]PROJECT COMPLETED SUCCESSFULLY![/bold green]\n\n"
            f"{result.message}\n"
            f"Tasks Completed: {len(result.state.completedTasks)}/{result.state.totalTasks}\n"
            f"Total Cost: ${orchestrator.cost_tracker.total_cost_usd:.4f}",
            title="RAMAZAN AI - SUCCESS",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]PROJECT EXECUTION STOPPED / BLOCKED[/bold red]\n\n"
            f"{result.message}\n"
            f"State: {result.state.status}",
            title="RAMAZAN AI - BLOCKED",
            border_style="red"
        ))
        raise Exit(1)


@app.command()
def step(
    mock: bool = Option(False, "--mock", help="Run step with deterministic simulation"),
):
    """
    Execute a single next ready task through the full lifecycle.
    """
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)
    orchestrator = Orchestrator(root_dir, config, use_mock_llm=mock)

    task = orchestrator.run_next_task()
    if task:
        console.print(f"[green]Executed task {task.id}: {task.status}[/green]")
    else:
        console.print("[yellow]No tasks ready to run.[/yellow]")


@app.command()
def test(
    command: Optional[str] = Option(None, "--command", "-c", help="Test command to execute"),
):
    """
    Execute the objective non-LLM Test Engine.
    """
    root_dir = find_project_root()
    test_engine = TestEngine(root_dir)
    console.print("[cyan]Running objective test suite...[/cyan]")
    res = test_engine.run_tests(command=command)

    if res.passed:
        console.print(f"[bold green]PASSED[/bold green] (Exit: {res.exitCode}, Duration: {res.duration}s)")
        console.print(res.stdout)
    else:
        console.print(f"[bold red]FAILED[/bold red] (Exit: {res.exitCode}, Duration: {res.duration}s)")
        console.print(res.stderr or res.stdout)
        raise Exit(res.exitCode)


@app.command()
def audit():
    """
    Run the comprehensive Final Audit quality gate.
    """
    root_dir = find_project_root()
    auditor = FinalAuditor(root_dir)
    console.print("[cyan]Executing Final Audit quality checks...[/cyan]")
    report = auditor.run_audit()

    console.print(Panel(
        report.to_markdown(),
        title="RAMAZAN AI - FINAL AUDIT",
        border_style="green" if report.passed else "red"
    ))
    if not report.passed:
        raise Exit(1)


from ramazan.llm.key_detector import SmartKeyDetector


@app.command()
def configure(
    key: Optional[str] = Option(None, "--key", "-k", help="API key to automatically identify and configure"),
    mode: Optional[str] = Option(None, "--mode", "-m", help="Autonomy mode: step_by_step, semi_autonomous, fully_autonomous"),
):
    """
    Auto-detect API key provider, configure dynamic agent routing, and set autonomy mode.
    """
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)

    if mode:
        valid_modes = ["step_by_step", "semi_autonomous", "fully_autonomous"]
        if mode.lower() not in valid_modes:
            console.print(f"[red]Invalid mode '{mode}'. Choose from: {', '.join(valid_modes)}[/red]")
            raise Exit(1)
        config.system.autonomyMode = mode.lower()
        console.print(f"[green]Autonomy mode updated to:[/green] [bold cyan]{config.system.autonomyMode}[/bold cyan]")

    target_key = key
    if not target_key and not mode:
        target_key = prompt_input("Enter AI Provider API Key or Endpoint (Gemini, Claude, OpenAI, DeepSeek, Groq, Ollama)", hide_input=True)

    if target_key:
        detected = SmartKeyDetector.detect_provider(target_key)
        if detected:
            provider, env_var, models = detected
            console.print(f"[bold green]Detected Provider:[/bold green] [cyan]{provider.upper()}[/cyan] (Env: {env_var})")

            # Save in environment and .ramazan/.env
            os.environ[env_var] = target_key
            env_file = root_dir / ".ramazan" / ".env"
            env_lines = []
            if env_file.exists():
                env_lines = [l for l in env_file.read_text().splitlines() if not l.startswith(f"{env_var}=")]
            env_lines.append(f"{env_var}={target_key}")
            env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")

            # Auto re-map agents dynamically based on available key
            config = SmartKeyDetector.auto_map_providers({provider: target_key}, config)
            console.print(Panel(
                f"[bold]Orchestrator:[/bold] {config.models.orchestrator.model} ({config.models.orchestrator.provider})\n"
                f"[bold]Architect:[/bold] {config.models.architect.model} ({config.models.architect.provider})\n"
                f"[bold]Worker (High):[/bold] {config.models.worker.high.model} ({config.models.worker.high.provider})\n"
                f"[bold]Worker (Medium):[/bold] {config.models.worker.medium.model} ({config.models.worker.medium.provider})\n"
                f"[bold]Worker (Low):[/bold] {config.models.worker.low.model} ({config.models.worker.low.provider})\n"
                f"[bold]Reviewer:[/bold] {config.models.reviewer.model} ({config.models.reviewer.provider})\n"
                f"[bold]Autonomy Mode:[/bold] {config.system.autonomyMode}",
                title=f"RAMAZAN AI - Dynamic Model Mapping for {provider.upper()}",
                border_style="green"
            ))
        else:
            console.print("[yellow]Could not automatically identify provider from key prefix. You can configure manually in .ramazan/config.json[/yellow]")

    config.save(root_dir)
    try:
        config.save(Path.home())
    except Exception:
        pass
    console.print("[green]Configuration saved to .ramazan/config.json successfully.[/green]")


@app.command(name="ui")
def launch_ui(
    host: str = Option("0.0.0.0", "--host", "-h", help="Bind host address"),
    port: int = Option(8000, "--port", "-p", help="Bind port number"),
):
    """
    Launch the interactive RAMAZAN AI Web Dashboard.
    """
    try:
        import uvicorn
        from ramazan.ui.server import create_app
    except ImportError:
        console.print(Panel(
            "[bold red]Web Dashboard dependencies missing![/bold red]\n\n"
            "FastAPI or Uvicorn is not installed in this environment.\n\n"
            "Install with:\n"
            "  [bold yellow]pip install fastapi uvicorn[/bold yellow]\n"
            "or in Termux / Ubuntu:\n"
            "  [bold yellow]pip install --break-system-packages fastapi uvicorn[/bold yellow]",
            title="RAMAZAN AI - Missing Dependencies",
            border_style="red"
        ))
        raise Exit(1)

    root_dir = find_project_root()
    web_app = create_app(root_dir)
    console.print(Panel(
        f"[bold green]Starting RAMAZAN AI Web Dashboard...[/bold green]\n"
        f"URL: [bold cyan]http://{host}:{port}[/bold cyan]\n"
        f"Binding: [yellow]{host}:{port}[/yellow]\n\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop server.",
        title="RAMAZAN AI - Web UI",
        border_style="green"
    ))
    uvicorn.run(web_app, host=host, port=port, log_level="info")


@app.command(name="web")
def launch_web(
    host: str = Option("0.0.0.0", "--host", "-h", help="Bind host address"),
    port: int = Option(8000, "--port", "-p", help="Bind port number"),
):
    """
    Alias for 'ramazan ui'.
    """
    launch_ui(host=host, port=port)


# --- BUILT-IN STANDARD LIBRARY ARGPARSE RUNNER (FOR MINIMAL ENVIRONMENTS) ---

def run_argparse_cli(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="ramazan",
        description="RAMAZAN AI - Multi-Agent Autonomous Software Engineering Orchestrator"
    )
    parser.add_argument("--version", "-v", action="version", version="RAMAZAN AI v0.1.0")
    subparsers = parser.add_subparsers(dest="command")

    # version
    subparsers.add_parser("version", help="Print RAMAZAN AI version")

    # init
    p_init = subparsers.add_parser("init", help="Initialize .ramazan directory")
    p_init.add_argument("--name", "-n", dest="project_name", default=None, help="Project name")

    # status
    subparsers.add_parser("status", help="Show project status")

    # plan
    p_plan = subparsers.add_parser("plan", help="Plan tasks from requirements")
    p_plan.add_argument("--file", "-f", dest="req_file", default=None, help="Requirements file")
    p_plan.add_argument("--mock", action="store_true", default=False, help="Offline mock planning")

    # run
    p_run = subparsers.add_parser("run", help="Run orchestration loop")
    p_run.add_argument("--mock", action="store_true", default=False, help="Offline simulation")
    p_run.add_argument("--max-steps", dest="max_steps", type=int, default=50, help="Max steps")

    # step
    p_step = subparsers.add_parser("step", help="Run single step")
    p_step.add_argument("--mock", action="store_true", default=False, help="Offline simulation")

    # test
    p_test = subparsers.add_parser("test", help="Run test suite")
    p_test.add_argument("--command", "-c", dest="test_cmd", default=None, help="Test command")

    # audit
    subparsers.add_parser("audit", help="Run final audit gate")

    # doctor
    subparsers.add_parser("doctor", help="Run system & model diagnostics")

    # ui / web
    p_ui = subparsers.add_parser("ui", help="Launch Web UI dashboard")
    p_ui.add_argument("--host", default="0.0.0.0", help="Host address")
    p_ui.add_argument("--port", "-p", type=int, default=8000, help="Port")

    p_web = subparsers.add_parser("web", help="Launch Web UI dashboard")
    p_web.add_argument("--host", default="0.0.0.0", help="Host address")
    p_web.add_argument("--port", "-p", type=int, default=8000, help="Port")

    # reset
    p_reset = subparsers.add_parser("reset", help="Reset task back to READY")
    p_reset.add_argument("task_id", help="Task ID e.g. TASK-001")

    # configure
    p_cfg = subparsers.add_parser("configure", help="Auto-detect API key or configure mode")
    p_cfg.add_argument("--key", "-k", default=None, help="API key")
    p_cfg.add_argument("--mode", "-m", default=None, help="Autonomy mode")

    # task
    p_task = subparsers.add_parser("task", help="Task operations")
    task_subs = p_task.add_subparsers(dest="task_command")
    task_subs.add_parser("list", help="List tasks")
    p_t_add = task_subs.add_parser("add", help="Add new task")
    p_t_add.add_argument("title", help="Task title")
    p_t_add.add_argument("--desc", "-d", default="", help="Task description")
    p_t_add.add_argument("--type", "-t", default="implementation", help="Task type")
    p_t_add.add_argument("--priority", "-p", default="medium", help="Priority")
    p_t_add.add_argument("--complexity", "-c", default="medium", help="Complexity")
    p_t_add.add_argument("--deps", default=None, help="Dependencies")
    p_t_add.add_argument("--files", default=None, help="Files")
    p_t_add.add_argument("--criteria", default=None, help="Acceptance criteria")

    p_t_res = task_subs.add_parser("reset", help="Reset task")
    p_t_res.add_argument("task_id", help="Task ID")

    # adr
    p_adr = subparsers.add_parser("adr", help="ADR operations")
    adr_subs = p_adr.add_subparsers(dest="adr_command")
    adr_subs.add_parser("list", help="List ADRs")
    p_adr_new = adr_subs.add_parser("new", help="New ADR")
    p_adr_new.add_argument("decision", help="ADR Decision")
    p_adr_new.add_argument("--context", "-c", default="", help="Context")
    p_adr_new.add_argument("--alternatives", "-a", default=None, help="Alternatives")
    p_adr_new.add_argument("--reason", "-r", default="", help="Reason")
    p_adr_new.add_argument("--consequences", default="", help="Consequences")
    p_adr_new.add_argument("--title", default="", help="Title")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return

    cmd = args.command
    if cmd == "version":
        version()
    elif cmd == "init":
        init(project_name=args.project_name)
    elif cmd == "status":
        status()
    elif cmd == "plan":
        plan(req_file=Path(args.req_file) if args.req_file else None, use_mock=args.mock)
    elif cmd == "run":
        run(mock=args.mock, max_steps=args.max_steps)
    elif cmd == "step":
        step(mock=args.mock)
    elif cmd == "test":
        test(command=args.test_cmd)
    elif cmd == "audit":
        audit()
    elif cmd == "doctor":
        doctor()
    elif cmd == "configure":
        configure(key=args.key, mode=args.mode)
    elif cmd in ["ui", "web"]:
        launch_ui(host=args.host, port=args.port)
    elif cmd == "reset":
        cmd_task_reset(task_id=args.task_id)
    elif cmd == "task":
        if args.task_command == "list" or not args.task_command:
            cmd_task_list()
        elif args.task_command == "add":
            cmd_task_add(
                title=args.title,
                desc=args.desc,
                task_type=args.type,
                priority=args.priority,
                complexity=args.complexity,
                deps=args.deps,
                files=args.files,
                criteria=args.criteria,
            )
        elif args.task_command == "reset":
            cmd_task_reset(task_id=args.task_id)
    elif cmd == "adr":
        if args.adr_command == "list" or not args.adr_command:
            cmd_adr_list()
        elif args.adr_command == "new":
            cmd_adr_new(
                decision=args.decision,
                context=args.context,
                alternatives=args.alternatives,
                reason=args.reason,
                consequences=args.consequences,
                title=args.title,
            )


def main():
    if HAS_TYPER and typer is not None:
        try:
            app()
            return
        except SystemExit:
            raise
        except Exception:
            run_argparse_cli()
    else:
        run_argparse_cli()


if __name__ == "__main__":
    main()
