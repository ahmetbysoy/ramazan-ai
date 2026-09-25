import pytest

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

    # 4. Chat API POST (Requirement planning)
    res_post_chat = client.post("/api/chat", json={"message": "Kullanıcı kayıt ve giriş servisi oluştur"})
    assert res_post_chat.status_code == 200
    chat_data = res_post_chat.json()
    assert "response" in chat_data
    assert "Planlanan Görevler" in chat_data["response"]["text"]

    # 5. Architecture API
    res_arch = client.get("/api/architecture")
    assert res_arch.status_code == 200

    # 6. Configure API
    res_cfg = client.post("/api/configure", json={"key": "AIzaSyD-1234567890abcdef1234567890abcdef", "mode": "step_by_step"})
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert cfg_data["success"] is True
    assert cfg_data["detected"]["provider"] == "gemini"
