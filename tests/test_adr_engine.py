import pytest
from pathlib import Path
from ramazan.schemas.adr import ADRManager, ArchitectureDecisionRecord


def test_adr_lifecycle(tmp_path: Path):
    # 1. Initial ID should be ADR-001
    first_id = ADRManager.next_adr_id(tmp_path)
    assert first_id == "ADR-001"

    # 2. Create first ADR
    adr1 = ADRManager.create_adr(
        root_dir=tmp_path,
        decision="Use FastAPI for backend services",
        context="High performance and async capabilities needed",
        alternatives=["Flask", "Django"],
        reason="FastAPI has built-in OpenAPI docs and native Pydantic validation",
        consequences="Requires async-aware libraries",
        title="ADR-001 FastAPI Adoption"
    )
    assert adr1.id == "ADR-001"
    assert (tmp_path / ".ramazan" / "decisions" / "ADR-001.md").exists()

    # 3. Next ID should be ADR-002
    second_id = ADRManager.next_adr_id(tmp_path)
    assert second_id == "ADR-002"

    # 4. Create second ADR
    adr2 = ADRManager.create_adr(
        root_dir=tmp_path,
        decision="Implement Strict File Scope in Worker Agent",
        context="Prevent LLM agent drift from touching unrelated files",
        alternatives=["Permissive worker", "Post-commit lint only"],
        reason="Prevents regressions and unwanted code changes",
        consequences="Worker must request task expansion if new files needed",
        title="ADR-002 Strict Scope Enforcement"
    )
    assert adr2.id == "ADR-002"

    # 5. List all ADRs (immutability check)
    all_adrs = ADRManager.list_adrs(tmp_path)
    assert len(all_adrs) == 2
    assert all_adrs[0].id == "ADR-001"
    assert all_adrs[1].id == "ADR-002"
    assert "FastAPI" in all_adrs[0].decision
    assert "Strict" in all_adrs[1].decision
