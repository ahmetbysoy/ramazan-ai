from pathlib import Path
from typer.testing import CliRunner
from ramazan.cli import app

runner = CliRunner()


def test_cli_init_and_status(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Test init
    result_init = runner.invoke(app, ["init", "--name", "TestApp"])
    assert result_init.exit_code == 0
    assert "RAMAZAN AI Initialized Successfully" in result_init.stdout
    assert (tmp_path / ".ramazan").exists()

    # Test status
    result_status = runner.invoke(app, ["status"])
    assert result_status.exit_code == 0
    assert "TestApp" in result_status.stdout


def test_cli_test_runner(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    # Run passing test command
    res = runner.invoke(app, ["test", "--command", "python3 -c 'print(\"CLI Test OK\"); exit(0)'"])
    assert res.exit_code == 0
    assert "CLI Test OK" in res.stdout
