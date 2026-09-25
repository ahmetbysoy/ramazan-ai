"""
CLI Entry Point for RAMAZAN AI.
Multi-Agent Autonomous Software Engineering System.
"""

import json
import os
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn

from ramazan.config import RamazanConfig, find_project_root
from ramazan.core.orchestrator import Orchestrator
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.audit.final_audit import FinalAuditor
from ramazan.tools.test_runner import TestEngine
from ramazan.tools.git_manager import GitManager
from ramazan.schemas.task import Task

app = typer.Typer(
    name="ramazan",
    help="RAMAZAN AI - Multi-Agent Autonomous Software Engineering Orchestrator",
    add_completion=False,
)
console = Console()


@app.command()
def init(
    project_name: str = typer.Option(None, "--name", "-n", help="Name of the project"),
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
    table.add_column("Status", style="bold")
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


@app.command()
def plan(
    req_file: Optional[Path] = typer.Option(None, "--file", "-f", help="Path to requirements file"),
    use_mock: bool = typer.Option(False, "--mock", help="Use deterministic mock model for offline planning"),
):
    """
    Break down requirements into deterministic tasks using the Orchestrator Agent.
    """
    root_dir = find_project_root()
    config = RamazanConfig.load(root_dir)
    orchestrator = Orchestrator(root_dir, config, use_mock_llm=use_mock)

    req_path = req_file or (root_dir / ".ramazan" / "requirements.md")
    if not req_path.exists():
        console.print(f"[red]Requirements file not found at {req_path}[/red]")
        raise typer.Exit(1)

    requirements = req_path.read_text(encoding="utf-8")
    arch = orchestrator.context_builder.load_architecture_rules()

    console.print("[cyan]Orchestrator Agent analyzing requirements and planning task graph...[/cyan]")
    tasks = orchestrator.orchestrator_agent = orchestrator.router.get_orchestrator_model()

    from ramazan.agents.orchestrator_agent import OrchestratorAgent
    orch_agent = OrchestratorAgent(
        model_config=orchestrator.router.get_orchestrator_model(),
        llm_client=orchestrator.llm_client,
        cost_tracker=orchestrator.cost_tracker
    )

    planned_tasks = orch_agent.plan_project(requirements, arch)

    for t in planned_tasks:
        orchestrator.task_engine.add_task(t)

    orchestrator.state_manager.set_total_tasks(len(orchestrator.task_engine.tasks))

    console.print(f"[bold green]Successfully generated {len(planned_tasks)} deterministic tasks![/bold green]")
    for t in planned_tasks:
        console.print(f"- [cyan]{t.id}[/cyan]: {t.title} [dim]({t.complexity} complexity)[/dim]")


@app.command()
def run(
    mock: bool = typer.Option(False, "--mock", help="Run with deterministic simulation for development/testing"),
    max_steps: int = typer.Option(50, "--max-steps", help="Maximum task iterations"),
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
        raise typer.Exit(1)


@app.command()
def step(
    mock: bool = typer.Option(False, "--mock", help="Run step with deterministic simulation"),
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
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Test command to execute"),
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
        raise typer.Exit(res.exitCode)


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
        raise typer.Exit(1)


from ramazan.llm.key_detector import SmartKeyDetector

@app.command()
def configure(
    key: Optional[str] = typer.Option(None, "--key", "-k", help="API key to automatically identify and configure"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Autonomy mode: step_by_step, semi_autonomous, fully_autonomous"),
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
            raise typer.Exit(1)
        config.system.autonomyMode = mode.lower()
        console.print(f"[green]Autonomy mode updated to:[/green] [bold cyan]{config.system.autonomyMode}[/bold cyan]")

    target_key = key
    if not target_key and not mode:
        target_key = typer.prompt("Enter AI Provider API Key or Endpoint (Gemini, Claude, OpenAI, DeepSeek, Groq, Ollama)", hide_input=True)

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
    console.print("[green]Configuration saved to .ramazan/config.json successfully.[/green]")


@app.command(name="ui")
def launch_ui(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port number"),
):
    """
    Launch the interactive RAMAZAN AI Web Dashboard.
    """
    import uvicorn
    from ramazan.ui.server import create_app

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
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port number"),
):
    """
    Alias for 'ramazan ui'.
    """
    launch_ui(host=host, port=port)


if __name__ == "__main__":
    app()

