import pytest
import shutil
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from pathlib import Path
from ramazan.ui.server import create_app


def test_ui_endpoints(tmp_path: Path):
    # Copy games and tests to tmp_path for test isolation
    for fname in ["monkey_game.html", "cops_robbers_game.html"]:
        src = Path(fname)
        if src.exists():
            shutil.copy(src, tmp_path / fname)

    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    for tname in ["test_monkey_game.py", "test_cops_game.py"]:
        src = Path("tests") / tname
        if src.exists():
            shutil.copy(src, tmp_path / "tests" / tname)

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

    # 7. Games endpoints
    res_mg = client.get("/game")
    assert res_mg.status_code == 200
    assert "Zıplayan Maymun" in res_mg.text

    res_cg = client.get("/game/cops")
    assert res_cg.status_code == 200
    assert "Hırsız Polis" in res_cg.text

    # 8. Chat API POST for Cops & Robbers game
    res_cops_chat = client.post("/api/chat", json={"message": "kanka hırsız polis oyunu yap . mobil tasarım olsun. tek dosya html JavaScript olarak kodla"})
    assert res_cops_chat.status_code == 200
    cops_resp = res_cops_chat.json()
    assert "response" in cops_resp
    assert "Hırsız Polis Mobil Oyunu" in cops_resp["response"]["text"]
    assert any(a.get("gameUrl") == "/game/cops" for a in cops_resp["response"].get("actions", []))

    # 9. Preview endpoint
    res_prev = client.get("/preview/cops_robbers_game.html")
    assert res_prev.status_code == 200
    assert "Hırsız Polis" in res_prev.text

    # 10. Task Reset endpoint
    res_reset = client.post("/api/task/TASK-005/reset")
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert reset_data["success"] is True
    assert reset_data["task"]["status"] == "READY"
    assert reset_data["task"]["retryCount"] == 0

    # 11. ADR API GET & POST
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
