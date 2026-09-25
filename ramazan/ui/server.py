"""
FastAPI Server and Mobile-First Web Dashboard for RAMAZAN AI.
Designed for mobile phones (Termux) and modern browsers.
Features:
- Bottom Navigation Toolbar
- Interactive Chat Tab for natural language requirements & orchestration
- Visual Pipeline / Tasks Tab with 1-tap Step and Run controls
- Smart API Key Auto-Detection Tab
- Real-time Test & Audit Tab
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse

from ramazan.config import RamazanConfig, find_project_root
from ramazan.core.orchestrator import Orchestrator
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.schemas.task import Task
from ramazan.schemas.memory import TaskMemory
from ramazan.llm.key_detector import SmartKeyDetector
from ramazan.tools.test_runner import TestEngine
from ramazan.audit.final_audit import FinalAuditor

logger = logging.getLogger("ramazan.ui")


def create_app(root_dir: Optional[Path] = None) -> FastAPI:
    proj_root = (root_dir or find_project_root()).resolve()
    app = FastAPI(title="RAMAZAN AI Mobile Dashboard", version="2.0.0")

    def _get_chat_history_path() -> Path:
        chat_dir = proj_root / ".ramazan"
        chat_dir.mkdir(parents=True, exist_ok=True)
        return chat_dir / "chat_history.json"

    def _load_chat_history() -> List[dict]:
        path = _get_chat_history_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Default welcome message
        return [
            {
                "id": "msg-1",
                "sender": "ramazan",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": "Selam kanka! Ben **RAMAZAN AI**, senin otonom yazılım mühendisliği orkestratörünüm. 🚀\n\nNeye ihtiyacın var? Aklındaki yazılım projesini veya eklemek istediğin bir özelliği buraya yaz; mimarisini çıkarıp görevlere böleyim, kodlarını yazıp test edelim!",
                "actions": [
                    {"label": "🚨 Hırsız Polis Oyunu Kodla", "prompt": "kanka hırsız polis oyunu yap . mobil tasarım olsun. tek dosya html JavaScript olarak kodla"},
                    {"label": "🐒 Zıplayan Maymun Oyunu Kodla", "prompt": "Zıplayan maymun oyunu kodla tek dosya html JavaScript olarak kodla mobil tasarım olsun"},
                    {"label": "🚀 REST API & CRUD Projesi", "prompt": "FastAPI ile kullanıcı ve ürün yönetimi yapan bir REST API servisi tasarla"},
                    {"label": "🧪 Tüm Testleri Koş", "prompt": "Mevcut sistemin tüm testlerini çalıştır ve doğrula"}
                ]
            }
        ]

    def _save_chat_history(messages: List[dict]):
        path = _get_chat_history_path()
        path.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")

    @app.get("/preview/{file_path:path}")
    def preview_file(file_path: str):
        target = proj_root / file_path
        if target.exists() and target.is_file():
            content = target.read_text(encoding="utf-8", errors="replace")
            if target.suffix in [".html", ".htm"]:
                return HTMLResponse(content)
            return JSONResponse({"path": file_path, "content": content})
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

    @app.get("/api/status")
    def get_status():
        state_mgr = StateManager(proj_root)
        task_eng = TaskEngine(proj_root)
        config = RamazanConfig.load(proj_root)
        state = state_mgr.load()

        tasks_list = [t.model_dump() for t in task_eng.tasks.values()]

        # Latest test result
        test_file = proj_root / ".ramazan" / "tests" / "latest.json"
        latest_test = None
        if test_file.exists():
            try:
                latest_test = json.loads(test_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Final audit
        audit_file = proj_root / ".ramazan" / "FINAL_AUDIT.md"
        audit_summary = audit_file.read_text(encoding="utf-8") if audit_file.exists() else None

        return {
            "state": state.model_dump(),
            "tasks": tasks_list,
            "config": config.model_dump(),
            "latestTest": latest_test,
            "auditSummary": audit_summary,
        }

    @app.get("/api/chat")
    def get_chat():
        return {"messages": _load_chat_history()}

    @app.post("/api/chat")
    def post_chat(payload: dict = Body(...)):
        history = _load_chat_history()
        try:
            user_message = payload.get("message", "").strip()
            if not user_message:
                raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

            # Add user message
            user_entry = {
                "id": f"msg-{len(history)+1}",
                "sender": "user",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": user_message
            }
            history.append(user_entry)

            config = RamazanConfig.load(proj_root)
            orch = Orchestrator(proj_root, config)

            msg_lower = user_message.lower()

            # 1. Selamlaşma ve Genel Sohbet
            if re.search(r"\b(merhaba|selam|selamlar|günaydın|iyi günler|iyi akşamlar|sa|as|hey|hi|hello|nasılsın|naber)\b", msg_lower):
                resp_text = (
                    "👋 **Merhaba kanka! Hoş geldin!**\n\n"
                    "Ben **RAMAZAN AI**, senin çoklu ajan mimarisine sahip otonom yazılım mühendisliği orkestratörünüm. 🤖\n\n"
                    "Bana geliştirmek istediğin herhangi bir yazılımı, servisi, aracı veya oyunu yazabilirsin. Ben senin için:\n"
                    "- 🧠 **Gereksinimleri planlayıp** atomik görevlere ve DAG grafiğine bölerim,\n"
                    "- 👷 **Worker ajanıyla** dosyaları ve testleri kodlarım,\n"
                    "- 🧪 **Test Engine ile** nesnel testleri (`pytest`) çalıştırırım,\n"
                    "- 🕵️ **Reviewer ajanıyla** güvenlik ve mimari denetimi yapıp Git'e commit ederim!\n\n"
                    "Şimdi ne geliştirmemi istersin kanka?"
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "🚀 Hesap Makinesi Servisi Planla", "prompt": "Python ile 4 işlem ve hafıza yönetimi yapan bir Hesap Makinesi modülü tasarla"},
                        {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
                        {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"}
                    ]
                }

            # 2. API Key ve Ücretsizlik Soruları
            elif any(w in msg_lower for w in ["api key", "apikey", "anahtar", "şart mı", "gerekli mi", "ücretsiz", "bedava"]):
                resp_text = (
                    "🔑 **API Anahtarı Durumu:**\n\n"
                    "RAMAZAN AI iki farklı modda çalışabilir:\n\n"
                    "1. **Çevrimdışı / Simülasyon Modu:**\n"
                    "   - API anahtarına hiç gerek yoktur.\n"
                    "   - Deterministik mock motoru ile görev planlama, test motoru, kod denetleme ve tüm kontrol paneli %100 yerel ve ücretsiz çalışır.\n\n"
                    "2. **Canlı LLM Modu:**\n"
                    "   - Gemini, Claude veya OpenAI anahtarını eklediğinde tüm görevleri canlı yapay zeka ajanları yazar ve inceler.\n"
                    "   - Terminalden `ramazan configure --key <API_KEY>` ile veya Ayarlar sekmesinden kolayca tanımlayabilirsin."
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
                        {"label": "📋 Görevleri Gör", "tab": "tasks"}
                    ]
                }

            # 3. Kimsin / Yardım
            elif any(w in msg_lower for w in ["kimsin", "yardım", "help", "ne yapabilirsin", "neler yapabilirsin"]):
                resp_text = (
                    "🤖 **RAMAZAN AI Nedir?**\n\n"
                    "RAMAZAN AI, tek bir sohbet botundan ibaret değildir; çoklu ajan mimarisine sahip bir **Chief Software Engineering Orchestrator** sistemidir:\n\n"
                    "- 🧠 **Orchestrator:** Gereksinimleri küçük, atomik görevlere ve DAG grafiğine böler.\n"
                    "- 🏛️ **Architect:** Sistem mimarisi ve değişmez ADR kararlarını yönetir.\n"
                    "- 👷 **Worker:** Belirlenen dosyalarda kod ve birim testlerini yazar.\n"
                    "- 🧪 **Test Engine:** Kodu nesnel test motorunda (`pytest`) doğrular.\n"
                    "- 🕵️ **Reviewer:** Güvenlik ve kalite denetimi yapar.\n"
                    "- 🛡️ **Circuit Breaker:** Sonsuz döngüleri ve güvenlik açıklarını engeller."
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "📋 Görevleri İncele", "tab": "tasks"},
                        {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"}
                    ]
                }

            # 4. Testleri Çalıştır
            elif any(w in msg_lower for w in ["testleri çalıştır", "test et", "test koş", "testler"]):
                test_res = orch.test_engine.run_tests()
                resp_text = (
                    f"🧪 **Test Motoru Sonucu:**\n\n"
                    f"- Durum: {'✅ **BAŞARILI (PASSED)**' if test_res.passed else '❌ **BAŞARISIZ (FAILED)**'}\n"
                    f"- Çıkış Kodu: `{test_res.exitCode}`\n"
                    f"- Süre: `{test_res.duration}s`\n"
                    f"- Özet: {test_res.summary}"
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [{"label": "📋 Görevleri Gör", "tab": "tasks"}]
                }

            # 5. Adım At / Yürüt
            elif any(w in msg_lower for w in ["çalıştır", "yürüt", "adım at", "başlat"]) and "tüm" not in msg_lower:
                task = orch.run_next_task()
                if task:
                    resp_text = (
                        f"▶️ **Sıradaki Görev Yürütüldü!**\n\n"
                        f"- **Görev:** `{task.id}`: {task.title}\n"
                        f"- **Durum:** `{task.status}`\n"
                        f"- **Test Durumu:** `{task.testStatus}`\n"
                        f"- **İnceleme:** `{task.reviewStatus}`\n\n"
                        f"Görev hafızası ve Git commit'i oluşturuldu. Bir sonraki göreve geçmeye hazırız!"
                    )
                else:
                    resp_text = "Şu anda çalıştırılmaya hazır bekleyen yeni bir görev bulunmuyor. Yeni bir özellik isteyebilirsin kanka!"
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [{"label": "▶️ Sonraki Adım", "action": "step"}, {"label": "📋 Görevler", "tab": "tasks"}]
                }

            # 9. Genel Yazılım Talebi / Mimari Planlama
            else:
                req_file = proj_root / ".ramazan" / "requirements.md"
                req_file.parent.mkdir(parents=True, exist_ok=True)
                req_content = f"# Proje Gereksinimleri\n\n## Kullanıcı Talebi\n{user_message}\n\n## Tarih\n{datetime.now(timezone.utc).isoformat()}\n"
                req_file.write_text(req_content, encoding="utf-8")

                arch = orch.context_builder.load_architecture_rules()

                from ramazan.agents.orchestrator_agent import OrchestratorAgent
                orch_agent = OrchestratorAgent(
                    model_config=orch.router.get_orchestrator_model(),
                    llm_client=orch.llm_client,
                    cost_tracker=orch.cost_tracker
                )
                planned = orch_agent.plan_project(req_content, arch)

                # Avoid overwriting existing tasks by remapping IDs if needed
                existing_tasks = orch.task_engine.get_all_tasks()
                existing_ids = {t.id for t in existing_tasks}
                conflict = any(t.id in existing_ids for t in planned)
                if conflict:
                    max_num = 0
                    for t in existing_tasks:
                        try:
                            num = int(t.id.replace("TASK-", ""))
                            if num > max_num:
                                max_num = num
                        except Exception:
                            pass
                    id_map = {}
                    for idx, t in enumerate(planned):
                        new_id = f"TASK-{max_num + idx + 1:03d}"
                        id_map[t.id] = new_id

                    for t in planned:
                        t.id = id_map[t.id]
                        t.dependencies = [id_map.get(dep, dep) for dep in t.dependencies]

                # Add tasks to engine
                for t in planned:
                    orch.task_engine.add_task(t)

                orch.state_manager.recompute(orch.task_engine)

                task_bullets = "\n".join([f"- **`{t.id}`**: {t.title} *(Öncelik: {t.priority.upper()}, Karmaşıklık: {t.complexity.upper()})*" for t in planned])

                resp_text = (
                    f"Harika fikir kanka! Talebini analiz ettim ve deterministik bir görev grafiği oluşturdum: 🎯\n\n"
                    f"**Planlanan Görevler ({len(planned)} adet):**\n"
                    f"{task_bullets}\n\n"
                    f"Pipeline kuruldu! İster aşağıdaki butondan **ilk görevi adım adım başlat**, istersen **Görevler** sekmesine geçip tüm planı incele."
                )

                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "▶️ İlk Görevi Başlat (Step)", "action": "step"},
                        {"label": "⚡ Hepsini Otonom Yap (Run)", "action": "run"},
                        {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"}
                    ]
                }

            history.append(bot_entry)
            _save_chat_history(history)
            return {"response": bot_entry, "messages": history}

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error in post_chat: {e}")
            err_entry = {
                "id": f"msg-{len(history)+1}",
                "sender": "ramazan",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": f"⚠️ Bir işlem sırasında durum oluştu:\n`{str(e)}`\n\nDetayları inceleyip tekrar deneyebilirsin kanka!",
                "actions": [
                    {"label": "🚨 Hırsız Polis Oyunu Oyna", "gameUrl": "/game/cops", "gameTitle": "🚨 Hırsız Polis Oyunu"},
                    {"label": "🐒 Maymun Oyunu Oyna", "gameUrl": "/game", "gameTitle": "🐒 Zıplayan Maymun"},
                    {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"}
                ]
            }
            history.append(err_entry)
            _save_chat_history(history)
            return {"response": err_entry, "messages": history}

    @app.post("/api/step")
    def execute_step():
        config = RamazanConfig.load(proj_root)
        orch = Orchestrator(proj_root, config)
        task = orch.run_next_task()
        if not task:
            return {"success": False, "message": "Çalıştırılmaya hazır görev kalmadı."}
        return {"success": True, "task": task.model_dump(), "message": f"{task.id} başarıyla yürütüldü: {task.status}"}

    @app.post("/api/run")
    def execute_run(max_steps: int = 20):
        config = RamazanConfig.load(proj_root)
        orch = Orchestrator(proj_root, config)
        res = orch.run_all(max_iterations=max_steps)
        return {
            "success": res.success,
            "message": res.message,
            "state": res.state.model_dump(),
        }

    @app.post("/api/plan")
    def execute_plan():
        config = RamazanConfig.load(proj_root)
        orch = Orchestrator(proj_root, config)
        req_file = proj_root / ".ramazan" / "requirements.md"
        if not req_file.exists():
            raise HTTPException(status_code=400, detail="requirements.md dosyası bulunamadı.")

        requirements = req_file.read_text(encoding="utf-8")
        arch = orch.context_builder.load_architecture_rules()

        from ramazan.agents.orchestrator_agent import OrchestratorAgent
        orch_agent = OrchestratorAgent(
            model_config=orch.router.get_orchestrator_model(),
            llm_client=orch.llm_client,
            cost_tracker=orch.cost_tracker
        )
        planned = orch_agent.plan_project(requirements, arch)
        for t in planned:
            orch.task_engine.add_task(t)

        orch.state_manager.recompute(orch.task_engine)
        return {"success": True, "count": len(planned), "tasks": [t.model_dump() for t in planned]}

    @app.post("/api/test")
    def run_tests():
        test_eng = TestEngine(proj_root)
        res = test_eng.run_tests()
        return res.model_dump()

    @app.post("/api/audit")
    def run_audit():
        auditor = FinalAuditor(proj_root)
        report = auditor.run_audit()
        return report.model_dump()

    @app.post("/api/configure")
    def configure_key(payload: dict = Body(...)):
        key = payload.get("key", "").strip()
        mode = payload.get("mode", "").strip()

        config = RamazanConfig.load(proj_root)

        if mode:
            config.system.autonomyMode = mode

        detected_info = None
        if key:
            detected = SmartKeyDetector.detect_provider(key)
            if detected:
                provider, env_var, models = detected
                os.environ[env_var] = key

                env_file = proj_root / ".ramazan" / ".env"
                lines = []
                if env_file.exists():
                    lines = [l for l in env_file.read_text().splitlines() if not l.startswith(f"{env_var}=")]
                lines.append(f"{env_var}={key}")
                env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

                config = SmartKeyDetector.auto_map_providers({provider: key}, config)
                detected_info = {
                    "provider": provider,
                    "envVar": env_var,
                }

        config.save(proj_root)
        return {
            "success": True,
            "detected": detected_info,
            "config": config.model_dump()
        }

    @app.get("/api/task/{task_id}")
    def get_task_details(task_id: str):
        task_eng = TaskEngine(proj_root)
        task = task_eng.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Görev bulunamadı.")

        mem_file = proj_root / ".ramazan" / "memory" / f"{task_id}.md"
        mem = mem_file.read_text(encoding="utf-8") if mem_file.exists() else None

        rev_file = proj_root / ".ramazan" / "reviews" / f"{task_id}.md"
        rev = rev_file.read_text(encoding="utf-8") if rev_file.exists() else None

        esc_md = proj_root / ".ramazan" / "logs" / f"ESCALATION-{task_id}.md"
        esc = esc_md.read_text(encoding="utf-8") if esc_md.exists() else None

        return {
            "task": task.model_dump(),
            "memory": mem,
            "review": rev,
            "escalation": esc,
        }

    @app.post("/api/task/{task_id}/reset")
    def reset_task(task_id: str):
        task_eng = TaskEngine(proj_root)
        state_mgr = StateManager(proj_root)
        try:
            task = task_eng.reset_task(task_id)
            state = state_mgr.load()
            if task_id in state.blockedTasks:
                state.blockedTasks.remove(task_id)
            if task_id in state.failedTasks:
                state.failedTasks.remove(task_id)
            if state.status == "BLOCKED":
                state.status = "IN_PROGRESS"
            state_mgr.save()
            return {"success": True, "task": task.model_dump(), "message": f"{task_id} başarıyla READY durumuna sıfırlandı."}
        except KeyError:
            raise HTTPException(status_code=404, detail="Görev bulunamadı.")

    @app.get("/api/adrs")
    def get_adrs():
        from ramazan.schemas.adr import ADRManager
        adrs = ADRManager.list_adrs(proj_root)
        return {"adrs": [a.model_dump() for a in adrs]}

    @app.post("/api/adrs")
    def post_adr(payload: dict = Body(...)):
        from ramazan.schemas.adr import ADRManager
        decision = payload.get("decision", "").strip()
        context = payload.get("context", "").strip()
        if not decision:
            raise HTTPException(status_code=400, detail="Karar boş olamaz.")
        adr = ADRManager.create_adr(
            root_dir=proj_root,
            decision=decision,
            context=context,
            alternatives=payload.get("alternatives", []),
            reason=payload.get("reason", ""),
            consequences=payload.get("consequences", ""),
            title=payload.get("title", "")
        )
        return {"success": True, "adr": adr.model_dump()}

    @app.get("/api/architecture")
    def get_architecture():
        arch_file = proj_root / ".ramazan" / "architecture.md"
        arch_content = arch_file.read_text(encoding="utf-8") if arch_file.exists() else ""

        decisions_dir = proj_root / ".ramazan" / "decisions"
        adrs = []
        if decisions_dir.exists():
            for f in sorted(decisions_dir.glob("ADR-*.md")):
                adrs.append({
                    "id": f.stem,
                    "content": f.read_text(encoding="utf-8")
                })

        return {
            "architecture": arch_content,
            "adrs": adrs
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return MOBILE_HTML_DASHBOARD

    return app


MOBILE_HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>RAMAZAN AI Mobile</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #121826;
      --card-border: #1f293d;
      --card-hover: #1a2337;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --emerald: #10b981;
      --emerald-bg: rgba(16, 185, 129, 0.15);
      --amber: #f59e0b;
      --rose: #f43f5e;
      --cyan: #06b6d4;
      --bottom-nav-height: 64px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
    }

    /* Top App Bar */
    .app-header {
      background: rgba(18, 24, 38, 0.95);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.75rem 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 40;
    }
    .header-brand {
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }
    .header-logo {
      background: linear-gradient(135deg, #3b82f6, #10b981);
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 1rem;
      color: #fff;
    }
    .header-title {
      font-size: 1.05rem;
      font-weight: 800;
      letter-spacing: -0.01em;
    }
    .status-badge {
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.25rem 0.55rem;
      border-radius: 9999px;
      background: var(--emerald-bg);
      color: var(--emerald);
      border: 1px solid rgba(16, 185, 129, 0.3);
      text-transform: uppercase;
    }

    /* Main Content Container */
    .content-area {
      flex: 1;
      overflow-y: auto;
      padding-bottom: calc(var(--bottom-nav-height) + 1rem);
      -webkit-overflow-scrolling: touch;
    }
    .tab-pane {
      display: none;
      padding: 1rem;
      max-width: 650px;
      margin: 0 auto;
    }
    .tab-pane.active {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* Card */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1rem;
      box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }

    /* Buttons */
    .btn {
      appearance: none;
      border: none;
      border-radius: 10px;
      padding: 0.65rem 1rem;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
      color: #fff;
    }
    .btn-primary { background: var(--primary); }
    .btn-primary:active { background: var(--primary-hover); transform: scale(0.98); }
    .btn-emerald { background: var(--emerald); }
    .btn-emerald:active { filter: brightness(1.1); transform: scale(0.98); }
    .btn-outline {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text);
    }
    .btn-block { width: 100%; }

    /* TAB 1: Chat Styles */
    .chat-container {
      display: flex;
      flex-direction: column;
      height: calc(100dvh - 54px - var(--bottom-nav-height));
      max-width: 650px;
      margin: 0 auto;
      width: 100%;
    }
    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }
    .chat-bubble {
      max-width: 86%;
      padding: 0.8rem 1rem;
      border-radius: 16px;
      font-size: 0.9rem;
      line-height: 1.45;
      word-break: break-word;
    }
    .chat-bubble.ramazan {
      align-self: flex-start;
      background: #151f33;
      border: 1px solid var(--card-border);
      border-bottom-left-radius: 4px;
    }
    .chat-bubble.user {
      align-self: flex-end;
      background: var(--primary);
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .bubble-actions {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
      margin-top: 0.6rem;
    }
    .chip-btn {
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 20px;
      padding: 0.3rem 0.65rem;
      font-size: 0.75rem;
      color: #fff;
      cursor: pointer;
    }
    .chip-btn:active { background: var(--primary); }

    .chat-input-bar {
      padding: 0.6rem 0.8rem;
      background: var(--card-bg);
      border-top: 1px solid var(--card-border);
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-shrink: 0;
    }
    .chat-input {
      flex: 1;
      background: #0a0f1c;
      border: 1px solid var(--card-border);
      border-radius: 24px;
      padding: 0.65rem 1rem;
      color: #fff;
      font-size: 0.9rem;
      outline: none;
    }
    .chat-input:focus { border-color: var(--primary); }
    .chat-send-btn {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: var(--primary);
      border: none;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
    }
    .chat-send-btn:active { transform: scale(0.92); }

    /* TAB 2: Task Cards */
    .task-item {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 0.9rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      cursor: pointer;
    }
    .task-item.completed { border-left: 4px solid var(--emerald); }
    .task-item.in_progress { border-left: 4px solid var(--amber); }
    .task-item.pending { border-left: 4px solid var(--muted); }

    .task-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .task-title {
      font-size: 0.95rem;
      font-weight: 700;
    }

    /* Bottom Navigation Toolbar */
    .bottom-nav {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: var(--bottom-nav-height);
      background: rgba(18, 24, 38, 0.95);
      backdrop-filter: blur(16px);
      border-top: 1px solid var(--card-border);
      display: flex;
      justify-content: space-around;
      align-items: center;
      z-index: 50;
      padding-bottom: env(safe-area-inset-bottom);
    }
    .nav-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.2rem;
      color: var(--muted);
      text-decoration: none;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 0.4rem 0.8rem;
      border-radius: 12px;
      border: none;
      background: transparent;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .nav-item svg {
      width: 22px;
      height: 22px;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
    }
    .nav-item.active {
      color: var(--primary);
    }
    .nav-item.active svg {
      stroke: var(--primary);
    }

    /* Modal */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.8);
      backdrop-filter: blur(4px);
      display: none;
      justify-content: center;
      align-items: flex-end;
      z-index: 100;
    }
    .modal-bottom-sheet {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px 20px 0 0;
      max-height: 85vh;
      width: 100%;
      max-width: 600px;
      overflow-y: auto;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      animation: slideUp 0.2s ease;
    }
    @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

    /* Toast */
    .toast {
      position: fixed;
      top: 1rem;
      left: 50%;
      transform: translateX(-50%);
      background: var(--card-bg);
      border: 1px solid var(--emerald);
      color: #fff;
      padding: 0.6rem 1.1rem;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 600;
      display: none;
      z-index: 200;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    }
  </style>
</head>
<body>

  <!-- App Header -->
  <header class="app-header">
    <div class="header-brand">
      <div class="header-logo">R</div>
      <div class="header-title">RAMAZAN AI</div>
    </div>
    <div style="display: flex; align-items: center; gap: 0.5rem;">
      <span class="status-badge" id="header-status">HAZIR</span>
    </div>
  </header>

  <!-- Content Tabs -->
  <div class="content-area">

    <!-- TAB 1: Chat (Default) -->
    <div id="tab-chat" class="tab-pane active" style="padding: 0;">
      <div class="chat-container">
        <div class="chat-messages" id="chat-messages">
          <!-- Dynamically populated -->
        </div>

        <div class="chat-input-bar">
          <input type="text" id="chat-input" class="chat-input" placeholder="Ne yapmak istiyorsun kanka? Yaz..." onkeypress="handleKey(event)">
          <button class="chat-send-btn" onclick="sendChat()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- TAB 2: Tasks (Pipeline) -->
    <div id="tab-tasks" class="tab-pane">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
          <span style="font-size: 0.8rem; font-weight: 700; color: var(--muted); text-transform: uppercase;">İlerleme</span>
          <span style="font-size: 0.85rem; font-weight: 800; color: var(--emerald);" id="pipeline-progress-text">0%</span>
        </div>
        <div style="background: rgba(255,255,255,0.08); height: 8px; border-radius: 9999px; overflow: hidden;">
          <div id="pipeline-progress-bar" style="background: linear-gradient(90deg, #3b82f6, #10b981); width: 0%; height: 100%;"></div>
        </div>
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
          <button class="btn btn-emerald btn-block" onclick="executeStep()">
            ▶️ Sonraki Adım (Step)
          </button>
          <button class="btn btn-primary btn-block" onclick="executeRun()">
            ⚡ Tümünü Otonom Koş
          </button>
        </div>
      </div>

      <div style="font-size: 0.85rem; font-weight: 700; color: var(--muted); margin-top: 0.5rem;">GÖREV LİSTESİ (DAG)</div>
      <div id="tasks-list" style="display: flex; flex-direction: column; gap: 0.75rem;">
        <!-- Populated dynamically -->
      </div>
    </div>

    <!-- TAB 3: API & Models -->
    <div id="tab-api" class="tab-pane">
      <div class="card">
        <h3 style="font-size: 1.05rem; font-weight: 800; margin-bottom: 0.4rem;">🔑 Akıllı API Yapılandırması</h3>
        <p style="font-size: 0.82rem; color: var(--muted); margin-bottom: 1rem;">
          API anahtarını yapıştır; sistem Gemini, Claude, OpenAI veya DeepSeek olduğunu kendisi tanır ve ajan rollerine dağıtır.
        </p>

        <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.8rem;">
          <label style="font-size: 0.8rem; font-weight: 600; color: var(--muted);">API Anahtarı / Endpoint:</label>
          <input type="password" id="api-key-box" style="background: #0a0f1c; border: 1px solid var(--card-border); border-radius: 10px; padding: 0.7rem; color: #fff; font-size: 0.9rem;" placeholder="sk-ant-... veya AIza... veya sk-...">
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem;">
          <label style="font-size: 0.8rem; font-weight: 600; color: var(--muted);">Çalışma Modu (Human-in-the-Loop):</label>
          <select id="api-mode-box" style="background: #0a0f1c; border: 1px solid var(--card-border); border-radius: 10px; padding: 0.7rem; color: #fff; font-size: 0.85rem;">
            <option value="step_by_step">Adım Adım (Önerilen: Her görevde durur)</option>
            <option value="semi_autonomous">Yarı Otonom (Kritik durumlarda onay ister)</option>
            <option value="fully_autonomous">Tam Otonom (Sonuna kadar otomatik çalışır)</option>
          </select>
        </div>

        <button class="btn btn-emerald btn-block" onclick="saveApiKey()">
          💾 Algıla ve Kaydet
        </button>

        <div id="key-detect-alert" style="display: none; margin-top: 1rem; padding: 0.75rem; border-radius: 10px; background: rgba(16, 185, 129, 0.1); border: 1px solid var(--emerald); font-size: 0.85rem;"></div>
      </div>

      <div class="card">
        <h4 style="font-size: 0.9rem; font-weight: 700; margin-bottom: 0.5rem; color: var(--muted);">AKTİF AJAN MODELLERİ</h4>
        <div id="model-mappings" style="font-size: 0.82rem; line-height: 1.6;">
          Yükleniyor...
        </div>
      </div>
    </div>

    <!-- TAB 4: Report & Test -->
    <div id="tab-report" class="tab-pane">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <h4 style="font-size: 0.95rem; font-weight: 800;">🧪 Nesnel Test Motoru</h4>
          <button class="btn btn-outline" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" onclick="runTestButton()">Testleri Koş</button>
        </div>
        <div id="test-report-box" style="font-size: 0.85rem; color: var(--muted);">
          Henüz test çalıştırılmadı.
        </div>
      </div>

      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
          <h4 style="font-size: 0.95rem; font-weight: 800;">🛡️ Final Audit Raporu</h4>
          <button class="btn btn-emerald" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;" onclick="runAuditButton()">Denetle</button>
        </div>
        <pre id="audit-report-box" style="font-size: 0.8rem; background: #060a12; padding: 0.75rem; border-radius: 8px; overflow-x: auto; color: #cbd5e1; max-height: 250px;">Yükleniyor...</pre>
      </div>
    </div>

  </div>

  <!-- Bottom Navigation Toolbar -->
  <nav class="bottom-nav">
    <button class="nav-item active" onclick="switchNav('tab-chat', this)">
      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
      <span>Sohbet</span>
    </button>
    <button class="nav-item" onclick="switchNav('tab-tasks', this)">
      <svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
      <span>Görevler</span>
    </button>
    <button class="nav-item" onclick="switchNav('tab-api', this)">
      <svg viewBox="0 0 24 24"><circle cx="7.5" cy="15.5" r="5.5"></circle><path d="M21 2l-9.6 9.6"></path><path d="M15.5 7.5l3 3L22 7l-3-3"></path></svg>
      <span>API & Model</span>
    </button>
    <button class="nav-item" onclick="switchNav('tab-report', this)">
      <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
      <span>Raporlar</span>
    </button>
  </nav>

  <!-- Modal Bottom Sheet for Tasks -->
  <div class="modal-backdrop" id="modal" onclick="closeModal(event)">
    <div class="modal-bottom-sheet" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h4 id="modal-title" style="font-size: 1rem; font-weight: 800;">Görev Detayı</h4>
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem;" onclick="closeModal()">✕</button>
      </div>
      <div id="modal-content" style="font-size: 0.85rem; line-height: 1.5;"></div>
    </div>
  </div>

  <!-- Modal Game Sheet -->
  <div class="modal-backdrop" id="game-modal" onclick="closeGameModal(event)">
    <div class="modal-bottom-sheet" style="max-height: 94vh; padding: 0.8rem;" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; padding: 0 0.5rem;">
        <h4 id="game-modal-title" style="font-size: 1rem; font-weight: 800;">🎮 Canlı Oyun</h4>
        <div style="display: flex; gap: 0.4rem;">
          <a id="game-modal-link" href="/game" target="_blank" class="btn btn-outline" style="padding: 0.25rem 0.6rem; font-size: 0.75rem; text-decoration: none;">Tam Ekran ↗</a>
          <button class="btn btn-outline" style="padding: 0.2rem 0.5rem;" onclick="closeGameModal()">✕</button>
        </div>
      </div>
      <iframe id="game-iframe" src="" style="width: 100%; height: 78vh; border: none; border-radius: 12px; background: #000;"></iframe>
    </div>
  </div>

  <!-- Modal Code Viewer -->
  <div class="modal-backdrop" id="code-modal" onclick="closeCodeModal(event)">
    <div class="modal-bottom-sheet" style="max-height: 85vh;" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h4 id="code-modal-title" style="font-size: 0.95rem; font-weight: 800;">Dosya İçeriği</h4>
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem;" onclick="closeCodeModal()">✕</button>
      </div>
      <pre id="code-modal-content" style="background: #060a12; padding: 0.8rem; border-radius: 8px; font-size: 0.78rem; overflow: auto; max-height: 65vh; color: #cbd5e1; white-space: pre-wrap;"></pre>
    </div>
  </div>

  <div class="toast" id="toast">Bildirim</div>

  <script>
    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 2800);
    }

    function switchNav(tabId, el) {
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      el.classList.add('active');

      if (tabId === 'tab-tasks' || tabId === 'tab-report' || tabId === 'tab-api') {
        refreshStatus();
      }
    }

    function handleKey(e) {
      if (e.key === 'Enter') sendChat();
    }

    async function loadChat() {
      try {
        const res = await fetch('/api/chat');
        const data = await res.json();
        renderChatMessages(data.messages || []);
      } catch (e) {
        console.error(e);
      }
    }

    function formatMessageText(txt) {
      if (!txt) return '';
      let s = txt
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/\\*(.*?)\\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.14);padding:0.15rem 0.35rem;border-radius:4px;font-size:0.86em;font-family:monospace;">$1</code>')
        .replace(/\\n/g, '<br>')
        .replace(/\n/g, '<br>');
      return s;
    }

    function renderChatMessages(messages) {
      const box = document.getElementById('chat-messages');
      box.innerHTML = '';
      messages.forEach(m => {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${m.sender}`;
        
        let html = `<div>${formatMessageText(m.text)}</div>`;
        if (m.actions && m.actions.length > 0) {
          html += `<div class="bubble-actions">`;
          m.actions.forEach(a => {
            if (a.prompt) {
              html += `<button class="chip-btn" onclick="sendCustomPrompt('${a.prompt}')">${a.label}</button>`;
            } else if (a.gameUrl) {
              html += `<button class="chip-btn" style="background: linear-gradient(135deg, #10b981, #059669); font-weight: 700; padding: 0.4rem 0.8rem;" onclick="openGameModal('${a.gameUrl}', '${a.gameTitle || 'Canlı Oyun'}')">${a.label}</button>`;
            } else if (a.game) {
              html += `<button class="chip-btn" style="background: linear-gradient(135deg, #10b981, #059669); font-weight: 700; padding: 0.4rem 0.8rem;" onclick="openGameModal('/game', '🐒 Zıplayan Maymun')">${a.label}</button>`;
            } else if (a.file) {
              html += `<button class="chip-btn" style="background: rgba(59, 130, 246, 0.25); border-color: var(--primary);" onclick="openFileModal('${a.file}')">${a.label}</button>`;
            } else if (a.action === 'step') {
              html += `<button class="chip-btn" style="background: var(--emerald);" onclick="executeStep()">${a.label}</button>`;
            } else if (a.action === 'run') {
              html += `<button class="chip-btn" style="background: var(--primary);" onclick="executeRun()">${a.label}</button>`;
            } else if (a.tab === 'tasks') {
              html += `<button class="chip-btn" onclick="switchNav('tab-tasks', document.querySelectorAll('.nav-item')[1])">${a.label}</button>`;
            }
          });
          html += `</div>`;
        }
        bubble.innerHTML = html;
        box.appendChild(bubble);
      });
      box.scrollTop = box.scrollHeight;
    }

    async function sendChat() {
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';

      // Optimistic append
      const box = document.getElementById('chat-messages');
      const uBubble = document.createElement('div');
      uBubble.className = 'chat-bubble user';
      uBubble.innerText = text;
      box.appendChild(uBubble);
      box.scrollTop = box.scrollHeight;

      showToast("Düşünülüyor & Planlanıyor...");

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        renderChatMessages(data.messages || []);
      } catch (err) {
        showToast("Hata oluştu kanka!");
      }
    }

    function sendCustomPrompt(p) {
      document.getElementById('chat-input').value = p;
      sendChat();
    }

    async function refreshStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // Header
        const st = data.state || {};
        document.getElementById('header-status').innerText = st.status || 'HAZIR';

        // Pipeline Tab
        const prog = st.progress || 0;
        document.getElementById('pipeline-progress-text').innerText = `${prog}%`;
        document.getElementById('pipeline-progress-bar').style.width = `${prog}%`;

        renderTaskList(data.tasks || [], st.completedTasks || []);

        // Models
        if (data.config && data.config.models) {
          const m = data.config.models;
          document.getElementById('model-mappings').innerHTML = `
            <div><strong>Orchestrator:</strong> <code>${m.orchestrator.model}</code></div>
            <div><strong>Architect:</strong> <code>${m.architect.model}</code></div>
            <div><strong>Worker (Genel):</strong> <code>${m.worker.medium.model}</code></div>
            <div><strong>Reviewer:</strong> <code>${m.reviewer.model}</code></div>
            <div style="margin-top: 0.3rem;"><strong>Mod:</strong> <code>${data.config.system.autonomyMode}</code></div>
          `;
        }

        // Test Summary
        if (data.latestTest) {
          const lt = data.latestTest;
          document.getElementById('test-report-box').innerHTML = `
            <div style="font-weight: 700; color: ${lt.passed ? 'var(--emerald)' : 'var(--rose)'};">
              ${lt.passed ? '✅ TÜM TESTLER BAŞARILI' : '❌ TESTLER BAŞARISIZ'} (Kod: ${lt.exitCode})
            </div>
            <div style="font-size: 0.78rem; margin-top: 0.2rem;">Süre: ${lt.duration}s | ${lt.summary}</div>
          `;
        }

        // Audit Summary
        if (data.auditSummary) {
          document.getElementById('audit-report-box').innerText = data.auditSummary;
        }

      } catch (e) {
        console.error(e);
      }
    }

    function renderTaskList(tasks, completed) {
      const box = document.getElementById('tasks-list');
      box.innerHTML = '';
      if (!tasks.length) {
        box.innerHTML = '<div style="text-align: center; color: var(--muted); padding: 1.5rem;">Henüz görev yok. Sohbet sekmesinden istediğin yazılımı yazabilirsin!</div>';
        return;
      }
      tasks.forEach(t => {
        const isDone = completed.includes(t.id) || t.status === 'COMPLETED';
        const isEscalated = ['ESCALATED', 'FAILED', 'BLOCKED'].includes(t.status);
        const cardClass = isDone ? 'completed' : (t.status === 'IN_PROGRESS' ? 'in_progress' : (isEscalated ? 'failed' : 'pending'));
        const stColor = isDone ? 'var(--emerald)' : (t.status === 'IN_PROGRESS' ? 'var(--amber)' : (isEscalated ? 'var(--rose)' : 'var(--muted)'));

        const el = document.createElement('div');
        el.className = `task-item ${cardClass}`;
        el.onclick = () => openTaskDetails(t.id);

        let resetBtn = '';
        if (isEscalated) {
          resetBtn = `<button class="chip-btn" style="background: var(--amber); color: #000; font-weight: 700; margin-top: 0.4rem; padding: 0.25rem 0.6rem;" onclick="resetTask('${t.id}', event)">🔄 Sıfırla (Reset)</button>`;
        }

        el.innerHTML = `
          <div class="task-top">
            <span style="font-size: 0.75rem; font-weight: 800; color: var(--cyan);">${t.id}</span>
            <span style="font-size: 0.72rem; font-weight: 700; color: ${stColor};">${t.status}</span>
          </div>
          <div class="task-title">${t.title}</div>
          <div style="font-size: 0.75rem; color: var(--muted);">${t.description}</div>
          ${resetBtn}
        `;
        box.appendChild(el);
      });
    }

    async function resetTask(taskId, e) {
      if (e) e.stopPropagation();
      showToast("Görev sıfırlanıyor...");
      try {
        const res = await fetch(`/api/task/${taskId}/reset`, { method: 'POST' });
        const d = await res.json();
        if (d.success) {
          showToast(`Görev ${taskId} READY olarak sıfırlandı!`);
          closeModal();
          refreshStatus();
        } else {
          showToast("Sıfırlanamadı.");
        }
      } catch (err) {
        showToast("Hata oluştu.");
      }
    }

    async function openTaskDetails(taskId) {
      try {
        const res = await fetch(`/api/task/${taskId}`);
        const data = await res.json();
        const t = data.task;

        document.getElementById('modal-title').innerText = `[${t.id}] ${t.title}`;
        let html = `
          <div><strong>Açıklama:</strong> ${t.description}</div>
          <div style="margin-top: 0.4rem;"><strong>Öncelik:</strong> ${t.priority.toUpperCase()} | <strong>Karmaşıklık:</strong> ${t.complexity.toUpperCase()}</div>
          <div style="margin-top: 0.4rem;"><strong>Kabul Kriterleri:</strong></div>
          <ul style="margin-left: 1rem; color: var(--muted);">
            ${t.acceptanceCriteria.map(c => `<li>${c}</li>`).join('')}
          </ul>
        `;
        if (data.escalation) {
          html += `<div style="margin-top: 0.8rem; border: 1px solid var(--rose); padding: 0.6rem; border-radius: 8px; background: rgba(244, 63, 94, 0.1);">
            <strong style="color: var(--rose);">⚠️ Human Escalation Raporu:</strong>
            <pre style="background: #060a12; padding: 0.5rem; border-radius: 6px; font-size: 0.75rem; max-height: 140px; overflow: auto; margin-top: 0.4rem;">${data.escalation}</pre>
            <button class="btn btn-emerald btn-block" style="margin-top: 0.6rem;" onclick="resetTask('${t.id}')">🔄 Görevi Sıfırla ve Devam Et (Reset to READY)</button>
          </div>`;
        }
        if (data.memory) {
          html += `<div style="margin-top: 0.8rem;"><strong>Hafıza Kaydı:</strong><pre style="background: #060a12; padding: 0.5rem; border-radius: 6px; font-size: 0.75rem; max-height: 140px; overflow: auto;">${data.memory}</pre></div>`;
        }
        document.getElementById('modal-content').innerHTML = html;
        document.getElementById('modal').style.display = 'flex';
      } catch (e) {
        showToast("Detay alınamadı.");
      }
    }

    function closeModal() {
      document.getElementById('modal').style.display = 'none';
    }

    function openGameModal(url = '/game', title = '🎮 Canlı Oyun') {
      const modal = document.getElementById('game-modal');
      const iframe = document.getElementById('game-iframe');
      const titleEl = document.getElementById('game-modal-title');
      const linkEl = document.getElementById('game-modal-link');
      if (titleEl) titleEl.innerText = title;
      if (linkEl) linkEl.href = url;
      iframe.src = url;
      modal.style.display = 'flex';
    }

    function closeGameModal() {
      const modal = document.getElementById('game-modal');
      const iframe = document.getElementById('game-iframe');
      iframe.src = '';
      modal.style.display = 'none';
    }

    async function openFileModal(filePath) {
      try {
        const res = await fetch(`/preview/${filePath}`);
        const cType = res.headers.get("content-type") || "";
        let content = "";
        if (cType.includes("json")) {
          const data = await res.json();
          content = data.content || JSON.stringify(data, null, 2);
        } else {
          content = await res.text();
        }
        document.getElementById('code-modal-title').innerText = filePath;
        document.getElementById('code-modal-content').innerText = content;
        document.getElementById('code-modal').style.display = 'flex';
      } catch (e) {
        window.open(`/preview/${filePath}`, '_blank');
      }
    }

    function closeCodeModal() {
      document.getElementById('code-modal').style.display = 'none';
    }

    async function executeStep() {
      showToast("Adım yürütülüyor...");
      try {
        const res = await fetch('/api/step', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Görev tamamlandı!");
        refreshStatus();
        loadChat();
      } catch (e) {
        showToast("Hata oluştu.");
      }
    }

    async function executeRun() {
      showToast("Tüm görevler yürütülüyor...");
      try {
        const res = await fetch('/api/run', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Tamamlandı!");
        refreshStatus();
        loadChat();
      } catch (e) {
        showToast("Hata oluştu.");
      }
    }

    async function runTestButton() {
      showToast("Testler koşuluyor...");
      try {
        await fetch('/api/test', { method: 'POST' });
        showToast("Testler tamamlandı!");
        refreshStatus();
      } catch (e) {
        showToast("Test hatası!");
      }
    }

    async function runAuditButton() {
      showToast("Final Audit denetleniyor...");
      try {
        await fetch('/api/audit', { method: 'POST' });
        showToast("Audit tamamlandı!");
        refreshStatus();
      } catch (e) {
        showToast("Audit hatası!");
      }
    }

    async function saveApiKey() {
      const key = document.getElementById('api-key-box').value.trim();
      const mode = document.getElementById('api-mode-box').value;
      try {
        const res = await fetch('/api/configure', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ key, mode })
        });
        const data = await res.json();
        const alertBox = document.getElementById('key-detect-alert');
        alertBox.style.display = 'block';
        if (data.detected) {
          alertBox.innerHTML = `✅ <strong>${data.detected.provider.toUpperCase()}</strong> otomatik algılandı ve tüm ajanlara bağlandı!`;
        } else {
          alertBox.innerHTML = `✅ Yapılandırma ve çalışma modu güncellendi!`;
        }
        showToast("Ayarlar kaydedildi!");
        refreshStatus();
      } catch (e) {
        showToast("Kayıt hatası!");
      }
    }

    // Init
    loadChat();
    refreshStatus();
    setInterval(refreshStatus, 4000);
  </script>
</body>
</html>
"""
