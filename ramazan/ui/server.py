"""
FastAPI Server and Web UI Dashboard for RAMAZAN AI.
Provides modern responsive interface and REST API for orchestration control.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ramazan.config import RamazanConfig, find_project_root
from ramazan.core.orchestrator import Orchestrator
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.llm.key_detector import SmartKeyDetector
from ramazan.tools.test_runner import TestEngine
from ramazan.audit.final_audit import FinalAuditor


def create_app(root_dir: Optional[Path] = None) -> FastAPI:
    proj_root = (root_dir or find_project_root()).resolve()
    app = FastAPI(title="RAMAZAN AI Dashboard", version="1.0.0")

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

    @app.post("/api/step")
    def execute_step():
        config = RamazanConfig.load(proj_root)
        orch = Orchestrator(proj_root, config)
        task = orch.run_next_task()
        if not task:
            return {"success": False, "message": "No ready tasks available."}
        return {"success": True, "task": task.model_dump()}

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
            raise HTTPException(status_code=400, detail="requirements.md not found.")

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

        orch.state_manager.set_total_tasks(len(orch.task_engine.tasks))
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
            raise HTTPException(status_code=404, detail="Task not found")

        # Memory
        mem_file = proj_root / ".ramazan" / "memory" / f"{task_id}.md"
        mem = mem_file.read_text(encoding="utf-8") if mem_file.exists() else None

        # Review
        rev_file = proj_root / ".ramazan" / "reviews" / f"{task_id}.md"
        rev = rev_file.read_text(encoding="utf-8") if rev_file.exists() else None

        return {
            "task": task.model_dump(),
            "memory": mem,
            "review": rev,
        }

    @app.get("/api/architecture")
    def get_architecture():
        arch_file = proj_root / ".ramazan" / "architecture.md"
        arch_content = arch_file.read_text(encoding="utf-8") if arch_file.exists() else ""

        # Collect ADRs
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
        return HTML_DASHBOARD

    return app


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RAMAZAN AI - Multi-Agent Software Engineering Orchestrator</title>
  <style>
    :root {
      --bg-main: #0b0f19;
      --bg-card: #131b2e;
      --bg-card-hover: #18223a;
      --border: #23314e;
      --border-focus: #3b82f6;
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --emerald: #10b981;
      --emerald-bg: rgba(16, 185, 129, 0.12);
      --amber: #f59e0b;
      --amber-bg: rgba(245, 158, 11, 0.12);
      --rose: #f43f5e;
      --rose-bg: rgba(244, 63, 94, 0.12);
      --cyan: #06b6d4;
      --purple: #a855f7;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg-main);
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: rgba(19, 27, 46, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 0.85rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .logo-badge {
      background: linear-gradient(135deg, #3b82f6, #10b981);
      color: #fff;
      font-weight: 900;
      font-size: 1.15rem;
      width: 40px;
      height: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35);
    }
    .brand h1 {
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }
    .brand span {
      color: var(--cyan);
      font-size: 0.8rem;
      font-weight: 600;
      background: rgba(6, 182, 212, 0.12);
      padding: 2px 8px;
      border-radius: 9999px;
      margin-left: 0.5rem;
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .btn {
      appearance: none;
      border: 1px solid transparent;
      padding: 0.5rem 0.9rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.18s ease;
      color: #fff;
    }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-primary { background: var(--primary); }
    .btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
    .btn-emerald { background: var(--emerald); }
    .btn-emerald:hover:not(:disabled) { filter: brightness(1.1); }
    .btn-outline {
      background: transparent;
      border-color: var(--border);
      color: var(--text);
    }
    .btn-outline:hover:not(:disabled) {
      background: var(--bg-card);
      border-color: var(--text-muted);
    }
    .btn-sm { padding: 0.35rem 0.65rem; font-size: 0.78rem; }

    main {
      flex: 1;
      padding: 1.5rem;
      max-width: 1400px;
      margin: 0 auto;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
    }
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.2rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .stat-label {
      color: var(--text-muted);
      font-size: 0.78rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.4rem;
    }
    .stat-value {
      font-size: 1.5rem;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .progress-bar-bg {
      background: rgba(255, 255, 255, 0.08);
      height: 8px;
      border-radius: 9999px;
      overflow: hidden;
      margin-top: 0.6rem;
    }
    .progress-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #10b981);
      transition: width 0.4s ease;
      width: 0%;
    }
    .badge {
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .badge-success { background: var(--emerald-bg); color: var(--emerald); border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-warning { background: var(--amber-bg); color: var(--amber); border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-danger { background: var(--rose-bg); color: var(--rose); border: 1px solid rgba(244, 63, 94, 0.3); }
    .badge-info { background: rgba(59, 130, 246, 0.12); color: var(--primary); border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-gray { background: rgba(148, 163, 184, 0.12); color: var(--text-muted); border: 1px solid rgba(148, 163, 184, 0.25); }

    .nav-tabs {
      display: flex;
      gap: 0.5rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.5rem;
      overflow-x: auto;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 0.5rem 1rem;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      border-radius: 8px;
      transition: all 0.2s;
      white-space: nowrap;
    }
    .tab-btn.active {
      background: var(--bg-card);
      color: #fff;
      border: 1px solid var(--border);
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .task-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1rem;
    }
    .task-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.1rem;
      display: flex;
      flex-direction: column;
      gap: 0.7rem;
      transition: transform 0.15s ease, border-color 0.15s ease;
      cursor: pointer;
    }
    .task-card:hover {
      border-color: var(--border-focus);
      transform: translateY(-2px);
    }
    .task-card.completed { border-left: 4px solid var(--emerald); }
    .task-card.in_progress { border-left: 4px solid var(--amber); }
    .task-card.failed { border-left: 4px solid var(--rose); }
    .task-card.pending { border-left: 4px solid var(--text-muted); }

    .task-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
    }
    .task-id {
      font-size: 0.8rem;
      font-family: monospace;
      font-weight: 700;
      color: var(--cyan);
    }
    .task-title {
      font-size: 0.95rem;
      font-weight: 700;
      color: #fff;
    }
    .task-desc {
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.4;
    }
    .task-meta {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
      margin-top: auto;
      padding-top: 0.5rem;
      border-top: 1px solid rgba(255, 255, 255, 0.05);
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      margin-bottom: 1rem;
    }
    .form-group label {
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
    }
    .form-input {
      background: #090e18;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: #fff;
      padding: 0.65rem 0.85rem;
      font-size: 0.9rem;
      width: 100%;
    }
    .form-input:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
    }
    pre {
      background: #060a12;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      overflow-x: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.85rem;
      line-height: 1.45;
      color: #cbd5e1;
    }
    .banner {
      background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(16, 185, 129, 0.08));
      border: 1px solid rgba(59, 130, 246, 0.25);
      border-radius: 12px;
      padding: 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .banner-title {
      font-size: 1.1rem;
      font-weight: 800;
      margin-bottom: 0.25rem;
    }
    .banner-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .toast {
      position: fixed;
      bottom: 1.5rem;
      right: 1.5rem;
      padding: 0.8rem 1.2rem;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: #fff;
      font-size: 0.88rem;
      font-weight: 600;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      display: none;
      z-index: 999;
      animation: fadeIn 0.2s ease;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    /* Modal */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      display: none;
      justify-content: center;
      align-items: center;
      z-index: 100;
      padding: 1rem;
    }
    .modal-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      max-width: 700px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo-badge">R</div>
      <div>
        <h1>RAMAZAN AI <span>v1.0 Orchestrator</span></h1>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn btn-outline btn-sm" onclick="triggerAction('/api/step', 'Sıradaki Görev Çalıştırılıyor...')">
        ▶️ Adım Yürüt (Step)
      </button>
      <button class="btn btn-emerald btn-sm" onclick="triggerAction('/api/run', 'Tam Otonom Orkestrasyon Başlatıldı...')">
        ⚡ Tümünü Çalıştır (Run)
      </button>
      <button class="btn btn-outline btn-sm" onclick="triggerAction('/api/test', 'Testler Çalıştırılıyor...')">
        🧪 Testleri Koş
      </button>
      <button class="btn btn-outline btn-sm" onclick="triggerAction('/api/audit', 'Nihai Kalite Denetimi Yapılıyor...')">
        🛡️ Final Audit
      </button>
      <button class="btn btn-outline btn-sm" onclick="refreshData()">
        🔄 Yenile
      </button>
    </div>
  </header>

  <main>
    <!-- Status Banner -->
    <div class="banner">
      <div>
        <div class="banner-title" id="banner-title">Proje Durumu: Yükleniyor...</div>
        <div class="banner-desc" id="banner-desc">Deterministik Multi-Agent Yazılım Mühendisliği Ekibi devrede.</div>
      </div>
      <div style="display: flex; gap: 0.5rem;">
        <span class="badge badge-info" id="badge-autonomy">MOD: ADIM ADIM</span>
        <span class="badge badge-success" id="badge-status">DURUM: HAZIR</span>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
      <div class="card">
        <div class="stat-label">Toplam İlerleme</div>
        <div class="stat-value" id="stat-progress">0%</div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" id="progress-fill"></div>
        </div>
      </div>
      <div class="card">
        <div class="stat-label">Görev Sayısı</div>
        <div class="stat-value" id="stat-tasks">0 / 0</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.4rem;" id="stat-tasks-detail">
          0 Tamamlandı, 0 Bekliyor
        </div>
      </div>
      <div class="card">
        <div class="stat-label">Aktif Görev</div>
        <div class="stat-value" style="font-size: 1.1rem;" id="stat-active-task">Yok (Boşta)</div>
        <div style="font-size: 0.78rem; color: var(--emerald); margin-top: 0.4rem;" id="stat-active-agent">
          Agent: Hazırda Bekliyor
        </div>
      </div>
      <div class="card">
        <div class="stat-label">Nesnel Test Motoru</div>
        <div class="stat-value" style="font-size: 1.15rem;" id="stat-test-summary">Henüz Koşulmadı</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.4rem;" id="stat-test-time">-</div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="nav-tabs">
      <button class="tab-btn active" onclick="openTab('tasks-tab', this)">📋 Görev Grafiği (Tasks)</button>
      <button class="tab-btn" onclick="openTab('keys-tab', this)">🔑 Akıllı API & Model Yapılandırması</button>
      <button class="tab-btn" onclick="openTab('arch-tab', this)">🏛️ Sistem Mimarisi & ADR</button>
      <button class="tab-btn" onclick="openTab('audit-tab', this)">🛡️ Final Audit Raporu</button>
    </div>

    <!-- TAB 1: Tasks -->
    <div id="tasks-tab" class="tab-content active">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 style="font-size: 1.1rem; font-weight: 700;">Deterministik Görev Listesi</h3>
        <button class="btn btn-primary btn-sm" onclick="triggerAction('/api/plan', 'Gereksinimler analiz edilip görevlere bölünüyor...')">
          ➕ Gereksinimlerden Görev Üret (Plan)
        </button>
      </div>
      <div class="task-grid" id="task-container">
        <!-- Rendered dynamically -->
      </div>
    </div>

    <!-- TAB 2: Smart API Key Setup -->
    <div id="keys-tab" class="tab-content">
      <div class="card" style="max-width: 800px; margin: 0 auto;">
        <h3 style="font-size: 1.15rem; font-weight: 700; margin-bottom: 0.5rem;">Akıllı API Anahtarı Tanımlama</h3>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.25rem;">
          API anahtarını aşağıdaki kutuya yapıştır. Sistem anahtarın kime ait olduğunu (Gemini, Claude, OpenAI, DeepSeek, Groq) otomatik tanır ve ajan rollerini (Orchestrator, Worker, Reviewer) ideal şekilde eşleştirir.
        </p>

        <div class="form-group">
          <label>API Anahtarı veya Yerel Endpoint:</label>
          <input type="password" id="api-key-input" class="form-input" placeholder="sk-ant-... veya AIza... veya sk-proj-... veya http://localhost:11434">
        </div>

        <div class="form-group">
          <label>Otonomi Düzeyi (Human-in-the-Loop):</label>
          <select id="autonomy-mode-select" class="form-input">
            <option value="step_by_step">Adım Adım (step_by_step) - Önerilen: Her görevde onay bekle</option>
            <option value="semi_autonomous">Yarı Otonom (semi_autonomous) - Kritik kararlarda ve Circuit Breaker'da onay bekle</option>
            <option value="fully_autonomous">Tam Otonom (fully_autonomous) - Final Audit'e kadar kesintisiz çalış</option>
          </select>
        </div>

        <button class="btn btn-primary" onclick="saveConfiguration()">
          💾 Algıla ve Yapılandırmayı Kaydet
        </button>

        <div id="config-result" style="margin-top: 1.2rem; display: none;"></div>
      </div>
    </div>

    <!-- TAB 3: Architecture & ADR -->
    <div id="arch-tab" class="tab-content">
      <div class="card" style="margin-bottom: 1rem;">
        <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem;">Sistem Mimarisi (.ramazan/architecture.md)</h3>
        <pre id="arch-content">Yükleniyor...</pre>
      </div>
      <div class="card">
        <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem;">Mimari Karar Kayıtları (ADR)</h3>
        <div id="adr-container">Yükleniyor...</div>
      </div>
    </div>

    <!-- TAB 4: Final Audit -->
    <div id="audit-tab" class="tab-content">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <h3 style="font-size: 1.1rem; font-weight: 700;">Nihai Kalite Kapısı (Final Audit)</h3>
          <button class="btn btn-emerald btn-sm" onclick="triggerAction('/api/audit', 'Final Audit Koşuluyor...')">
            🛡️ Denetimi Şimdi Çalıştır
          </button>
        </div>
        <pre id="audit-content">Henüz audit raporu oluşturulmadı.</pre>
      </div>
    </div>
  </main>

  <!-- Modal for Task Details -->
  <div class="modal-backdrop" id="task-modal" onclick="closeModal(event)">
    <div class="modal-card" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h3 id="modal-title" style="font-size: 1.15rem; font-weight: 800;">Görev Detayı</h3>
        <button class="btn btn-outline btn-sm" onclick="document.getElementById('task-modal').style.display='none'">✕</button>
      </div>
      <div id="modal-body"></div>
    </div>
  </div>

  <div class="toast" id="toast">Bildirim</div>

  <script>
    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.style.display = 'block';
      toast.style.borderColor = isError ? 'var(--rose)' : 'var(--emerald)';
      setTimeout(() => { toast.style.display = 'none'; }, 3200);
    }

    function openTab(tabId, btn) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      btn.classList.add('active');

      if (tabId === 'arch-tab') loadArchitecture();
    }

    async function refreshData() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // Banner
        const state = data.state || {};
        document.getElementById('banner-title').innerText = `Proje: ${state.project || 'RAMAZAN AI'} | Durum: ${state.status}`;
        document.getElementById('badge-status').innerText = `DURUM: ${state.status}`;
        document.getElementById('badge-status').className = `badge ${state.status === 'COMPLETED' ? 'badge-success' : (state.status === 'IN_PROGRESS' ? 'badge-warning' : 'badge-info')}`;

        const autonomy = (data.config?.system?.autonomyMode || 'step_by_step').toUpperCase();
        document.getElementById('badge-autonomy').innerText = `MOD: ${autonomy}`;

        // Progress
        const prog = state.progress || 0;
        document.getElementById('stat-progress').innerText = `${prog}%`;
        document.getElementById('progress-fill').style.width = `${prog}%`;

        // Tasks count
        const total = state.totalTasks || 0;
        const comp = (state.completedTasks || []).length;
        document.getElementById('stat-tasks').innerText = `${comp} / ${total}`;
        document.getElementById('stat-tasks-detail').innerText = `${comp} Tamamlandı, ${total - comp} Bekliyor`;

        // Active task
        document.getElementById('stat-active-task').innerText = state.currentTask || 'Yok (Boşta)';
        document.getElementById('stat-active-agent').innerText = state.currentTask ? 'Worker & Test Engine devrede' : 'Agent: Beklemede';

        // Test status
        if (data.latestTest) {
          const pass = data.latestTest.passed;
          document.getElementById('stat-test-summary').innerText = pass ? '✅ Testler Başarılı' : '❌ Testler Başarısız';
          document.getElementById('stat-test-summary').style.color = pass ? 'var(--emerald)' : 'var(--rose)';
          document.getElementById('stat-test-time').innerText = `Son Test: ${data.latestTest.timestamp.slice(11, 19)} (Süre: ${data.latestTest.duration}s)`;
        }

        // Render Task Cards
        renderTasks(data.tasks || [], state.completedTasks || []);

        // Audit Summary
        if (data.auditSummary) {
          document.getElementById('audit-content').innerText = data.auditSummary;
        }

      } catch (err) {
        console.error("Failed to load status:", err);
      }
    }

    function renderTasks(tasks, completedIds) {
      const container = document.getElementById('task-container');
      container.innerHTML = '';

      if (tasks.length === 0) {
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">Henüz planlanmış görev yok. Yukarıdaki 'Gereksinimlerden Görev Üret' butonuna tıklayabilirsiniz.</div>`;
        return;
      }

      tasks.forEach(t => {
        const isDone = completedIds.includes(t.id) || t.status === 'COMPLETED';
        const cardClass = isDone ? 'completed' : (t.status === 'IN_PROGRESS' ? 'in_progress' : (t.status === 'FAILED' ? 'failed' : 'pending'));
        const badgeClass = isDone ? 'badge-success' : (t.status === 'IN_PROGRESS' ? 'badge-warning' : (t.status === 'FAILED' ? 'badge-danger' : 'badge-gray'));

        const card = document.createElement('div');
        card.className = `task-card ${cardClass}`;
        card.onclick = () => openTaskModal(t.id);
        card.innerHTML = `
          <div class="task-header">
            <span class="task-id">${t.id}</span>
            <span class="badge ${badgeClass}">${t.status}</span>
          </div>
          <div class="task-title">${t.title}</div>
          <div class="task-desc">${t.description || ''}</div>
          <div class="task-meta">
            <span class="badge badge-info">Öncelik: ${t.priority.toUpperCase()}</span>
            <span class="badge badge-gray">Karmaşıklık: ${t.complexity.toUpperCase()}</span>
            <span class="badge badge-gray">Tekrar: ${t.retryCount}/${t.maxRetries}</span>
          </div>
        `;
        container.appendChild(card);
      });
    }

    async function openTaskModal(taskId) {
      try {
        const res = await fetch(`/api/task/${taskId}`);
        const data = await res.json();
        const t = data.task;

        document.getElementById('modal-title').innerText = `[${t.id}] ${t.title}`;
        let bodyHtml = `
          <div><strong>Açıklama:</strong> ${t.description}</div>
          <div style="margin-top: 0.5rem;"><strong>Hedef Dosyalar:</strong> ${t.files.map(f => `<code>${f}</code>`).join(', ') || 'Yok'}</div>
          <div style="margin-top: 0.5rem;"><strong>Kabul Kriterleri:</strong></div>
          <ul style="margin-left: 1.2rem; font-size: 0.85rem; color: var(--text-muted);">
            ${t.acceptanceCriteria.map(c => `<li>${c}</li>`).join('')}
          </ul>
        `;

        if (data.memory) {
          bodyHtml += `
            <div style="margin-top: 1rem;">
              <strong>Görev Hafızası (.ramazan/memory/${taskId}.md):</strong>
              <pre style="margin-top: 0.4rem; max-height: 200px;">${data.memory}</pre>
            </div>
          `;
        }

        if (data.review) {
          bodyHtml += `
            <div style="margin-top: 1rem;">
              <strong>Denetim Raporu (.ramazan/reviews/${taskId}.md):</strong>
              <pre style="margin-top: 0.4rem; max-height: 200px;">${data.review}</pre>
            </div>
          `;
        }

        document.getElementById('modal-body').innerHTML = bodyHtml;
        document.getElementById('task-modal').style.display = 'flex';
      } catch (err) {
        showToast("Görev detayı alınamadı", true);
      }
    }

    function closeModal(e) {
      document.getElementById('task-modal').style.display = 'none';
    }

    async function triggerAction(endpoint, loadingMsg) {
      showToast(loadingMsg);
      try {
        const res = await fetch(endpoint, { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "İşlem başarıyla tamamlandı!");
        refreshData();
      } catch (err) {
        showToast("İşlem sırasında hata oluştu!", true);
      }
    }

    async function saveConfiguration() {
      const key = document.getElementById('api-key-input').value;
      const mode = document.getElementById('autonomy-mode-select').value;

      try {
        const res = await fetch('/api/configure', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, mode })
        });
        const data = await res.json();
        if (data.success) {
          showToast("Yapılandırma başarıyla güncellendi!");
          const resDiv = document.getElementById('config-result');
          resDiv.style.display = 'block';

          if (data.detected) {
            resDiv.innerHTML = `
              <div class="card" style="background: rgba(16, 185, 129, 0.1); border-color: var(--emerald);">
                <div style="font-weight: 800; color: var(--emerald);">✅ Sağlayıcı Otomatik Tanındı: ${data.detected.provider.toUpperCase()}</div>
                <div style="font-size: 0.85rem; margin-top: 0.3rem;">Ortam değişkeni: <code>${data.detected.envVar}</code></div>
                <div style="font-size: 0.85rem; margin-top: 0.3rem;">Ajanlar bu sağlayıcının en uygun modellerine bağlandı.</div>
              </div>
            `;
          }
          refreshData();
        }
      } catch (err) {
        showToast("Yapılandırma kaydedilemedi!", true);
      }
    }

    async function loadArchitecture() {
      try {
        const res = await fetch('/api/architecture');
        const data = await res.json();
        document.getElementById('arch-content').innerText = data.architecture || "Henüz mimari dosyası yok.";

        const adrContainer = document.getElementById('adr-container');
        if (data.adrs && data.adrs.length > 0) {
          adrContainer.innerHTML = data.adrs.map(a => `
            <div style="margin-bottom: 0.75rem;">
              <strong>${a.id}</strong>
              <pre style="margin-top: 0.3rem;">${a.content}</pre>
            </div>
          `).join('');
        } else {
          adrContainer.innerText = "Kayıtlı ADR bulunamadı.";
        }
      } catch (err) {
        console.error("Architecture load failed:", err);
      }
    }

    // Auto-refresh every 5 seconds
    refreshData();
    setInterval(refreshData, 5000);
  </script>
</body>
</html>
"""
