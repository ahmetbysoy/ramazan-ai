import pytest
import json
from pathlib import Path
from typer.testing import CliRunner
from ramazan.audit.doctor import RamazanDoctor
from ramazan.config import RamazanConfig
from ramazan.cli import app

runner = CliRunner()


def test_doctor_passes_on_valid_configuration(tmp_path: Path):
    doc = RamazanDoctor(root_dir=Path.cwd())
    success, results = doc.run_diagnostics()
    assert success is True
    assert len(results) >= 8

    # Ensure every model has a result
    roles = {r.name for r in results if r.category == "Models"}
    assert "orchestrator" in roles
    assert "architect" in roles
    assert "worker.low" in roles
    assert "worker.medium" in roles
    assert "worker.high" in roles
    assert "worker.critical" in roles
    assert "reviewer" in roles

    # CLI invocation prints PASS and exits 0
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert "PASS Schema Validation" in res.stdout
    assert "PASS orchestrator" in res.stdout
    assert "All doctor diagnostics passed successfully" in res.stdout


def test_doctor_fails_and_exits_1_on_invalid_model(tmp_path: Path, monkeypatch):
    base_config = Path(__file__).resolve().parent.parent / ".ramazan" / "config.json"
    cfg_data = json.loads(base_config.read_text(encoding="utf-8"))

    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".ramazan"
    config_dir.mkdir(parents=True)

    # Inject an invalid deprecated or broken model
    cfg_data["models"]["worker"]["low"]["model"] = "deprecated-nonexistent-model-v0"
    (config_dir / "config.json").write_text(json.dumps(cfg_data), encoding="utf-8")

    doc = RamazanDoctor(root_dir=tmp_path)
    success, results = doc.run_diagnostics()
    assert success is False

    failed_item = [r for r in results if r.name == "worker.low"][0]
    assert failed_item.passed is False
    assert "Unrecognized model identifier" in failed_item.message

    # CLI invocation must exit with status code 1
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 1
    assert "FAIL" in res.stdout
    assert "Doctor reported failures" in res.stdout


def test_doctor_fails_on_unknown_config_field(tmp_path: Path, monkeypatch):
    base_config = Path(__file__).resolve().parent.parent / ".ramazan" / "config.json"
    cfg_data = json.loads(base_config.read_text(encoding="utf-8"))

    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".ramazan"
    config_dir.mkdir(parents=True)

    # Inject forbidden extra field
    cfg_data["unknown_rogue_field"] = "malicious_payload"
    (config_dir / "config.json").write_text(json.dumps(cfg_data), encoding="utf-8")

    doc = RamazanDoctor(root_dir=tmp_path)
    success, results = doc.run_diagnostics()
    assert success is False
    assert any("unknown" in r.message.lower() for r in results)

    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 1
