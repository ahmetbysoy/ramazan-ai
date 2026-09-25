import pytest
import shutil
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from pathlib import Path
from ramazan.ui.server import create_app


def test_ui_endpoints(tmp_path: Path):
    app = create_app(root_dir=tmp_path)
    client = TestClient(app)

    # 1. Mobile HTML Dashboard
    res_html = client.get("/")
    assert res_html.status_code == 200
    assert "RAMAZAN AI" in res_html.text
    assert "bottom-nav" in res_html.text

    # 2. Status API
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "state" in data
    assert "tasks" in data

    # 3. Chat API GET
    res_chat = client.get("/api/chat")
    assert res_chat.status_code == 200
    assert "messages" in res_chat.json()

    # 4. Chat API POST (Greeting)
    res_greet = client.post("/api/chat", json={"message": "selam kanka"})
    assert res_greet.status_code == 200
    greet_data = res_greet.json()
    assert "Merhaba kanka" in greet_data["response"]["text"]

    # 5. Chat API POST (Requirement planning)
    res_post_chat = client.post("/api/chat", json={"message": "Kullanıcı kayıt ve giriş servisi oluştur"})
    assert res_post_chat.status_code == 200
    chat_data = res_post_chat.json()
    assert "response" in chat_data
    assert "Planlanan Görevler" in chat_data["response"]["text"]

    # 6. Architecture API
    res_arch = client.get("/api/architecture")
    assert res_arch.status_code == 200

    # 7. Configure API (Gemini Key)
    res_cfg = client.post("/api/configure", json={"key": "AQ.test_mock_gemini_key_for_unit_tests_abcdef1234567890", "mode": "step_by_step"})
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert cfg_data["success"] is True
    assert cfg_data["detected"]["provider"] == "gemini"

    # 8. Preview endpoint
    (tmp_path / "README.md").write_text("# Hello World\n", encoding="utf-8")
    res_prev = client.get("/preview/README.md")
    assert res_prev.status_code == 200
    assert "Hello World" in res_prev.text

    # 9. ADR API GET & POST
    res_adr_post = client.post("/api/adrs", json={
        "decision": "Use SQLite for lightweight local persistence",
        "context": "Need simple zero-dependency local storage",
        "alternatives": ["PostgreSQL", "JSON files"],
        "reason": "SQLite requires no separate database daemon",
        "consequences": "Single file storage",
        "title": "ADR-001 Local Database"
    })
    assert res_adr_post.status_code == 200
    adr_post_data = res_adr_post.json()
    assert adr_post_data["success"] is True
    assert adr_post_data["adr"]["id"] == "ADR-001"

    res_adr_get = client.get("/api/adrs")
    assert res_adr_get.status_code == 200
    adr_get_data = res_adr_get.json()
    assert len(adr_get_data["adrs"]) >= 1
