"""
FastAPI Server and Mobile-First Web Dashboard for RAMAZAN AI.
Designed for mobile phones (Termux) and modern desktop browsers.
Features:
- Multi-project workspace switcher (auto-detects isolated projects in projects/)
- Autonomous playable game & web preview auto-detection
- Correct MIME type serving for JS, CSS, HTML, SVG, audio, and code
- Asynchronous non-blocking background workers for Step and Run execution
- Real-time in-memory log streaming and live console drawer
- Smart API key auto-detection and role mapping
- Interactive Chat with transparent reasoning and action chips
- Objective pytest test engine and final architecture audit
- Keyboard-aware, touch-friendly mobile UI
"""

import json
import logging
import mimetypes
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from ramazan.audit.final_audit import FinalAuditor
from ramazan.config import RamazanConfig, find_project_root
from ramazan.core.orchestrator import Orchestrator
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.llm.key_detector import SmartKeyDetector
from ramazan.schemas.adr import ADRManager
from ramazan.schemas.memory import TaskMemory
from ramazan.schemas.task import Task
from ramazan.tools.test_runner import TestEngine

logger = logging.getLogger("ramazan.ui")


def _scrub_secrets(text: str) -> str:
    """Masks API keys and personal access tokens to prevent credential leaks."""
    if not text:
        return ""
    text = re.sub(r'ghp_[A-Za-z0-9]{30,}', '[REDACTED_GH_TOKEN]', text)
    text = re.sub(r'AQ\.[A-Za-z0-9-_]{35,}', '[REDACTED_GEMINI_KEY]', text)
    text = re.sub(r'AIza[A-Za-z0-9-_]{35}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'sk-[A-Za-z0-9-_]{20,}', '[REDACTED_API_KEY]', text)
    return text


def _analyze_error_log(text: str) -> Dict[str, Any]:
    """Smart diagnostic engine that identifies the root cause of failures and provides actionable solutions."""
    if not text:
        return {"hasError": False}

    # 1. ImportError / JS imported into Python test
    if "ImportError" in text and ("test_" in text or ".js" in text or "game" in text):
        return {
            "hasError": True,
            "errorType": "Yanlış Modül İçe Aktarımı (ImportError)",
            "severity": "CRITICAL",
            "rootCause": "Python test dosyası (pytest), JavaScript (.js) veya HTML dosyasını Python modülü gibi 'import' etmeye çalıştı.",
            "recommendation": "Test dosyasında 'import' yerine 'Path(file).read_text()' ile dosya içeriği ve DOM/canvas yapıları denetlenmelidir.",
            "quickAction": "reset_task",
            "suggestedCommand": "ramazan reset <TASK_ID>",
            "matchSnippet": "ImportError while importing test module",
        }

    # 2. Ubuntu / Debian PEP 668 externally-managed-environment
    if "externally-managed-environment" in text or "PEP 668" in text:
        return {
            "hasError": True,
            "errorType": "Sistem Paket Yöneticisi Koruması (PEP 668)",
            "severity": "CRITICAL",
            "rootCause": "Ubuntu 24.04+ veya Debian ortamında pip doğrudan sistem geneline paket kurulumunu kısıtlıyor.",
            "recommendation": "Komutun sonuna '--break-system-packages' ekleyin: pip install <paket> --break-system-packages",
            "quickAction": "copy_cmd",
            "suggestedCommand": "pip install <paket> --break-system-packages",
            "matchSnippet": "error: externally-managed-environment",
        }

    # 3. Missing package
    no_mod = re.search(r"No module named '([a-zA-Z0-9_\-]+)'", text)
    if no_mod:
        mod_name = no_mod.group(1)
        return {
            "hasError": True,
            "errorType": f"Eksik Python Kütüphanesi: '{mod_name}'",
            "severity": "WARNING",
            "rootCause": f"Çalışma ortamında '{mod_name}' paketi yüklü değil.",
            "recommendation": f"Paketi terminalde kurun: pip install {mod_name} --break-system-packages",
            "quickAction": "copy_cmd",
            "suggestedCommand": f"pip install {mod_name} --break-system-packages",
            "matchSnippet": f"No module named '{mod_name}'",
        }

    # 4. Circuit Breaker tripped
    if "CIRCUIT BREAKER TRIPPED" in text or "Maximum retries" in text:
        cb_task = re.search(r"for (TASK-\d+)", text)
        task_id = cb_task.group(1) if cb_task else "TASK-001"
        return {
            "hasError": True,
            "errorType": f"Circuit Breaker Devreye Girdi ({task_id})",
            "severity": "CRITICAL",
            "rootCause": f"{task_id} görevi üst üste 3 denemede testleri geçemediği için sonsuz döngüyü engellemek amacıyla askıya alındı.",
            "recommendation": f"Görevi sıfırlayıp yeniden denemek için: ramazan reset {task_id}",
            "quickAction": "reset_task",
            "targetTaskId": task_id,
            "suggestedCommand": f"ramazan reset {task_id}",
            "matchSnippet": "CIRCUIT BREAKER TRIPPED",
        }

    # 5. SyntaxError
    syntax_err = re.search(r"SyntaxError:\s*([^\n\r]+)", text)
    if syntax_err:
        err_msg = syntax_err.group(1)
        return {
            "hasError": True,
            "errorType": "Sözdizimi Hatası (SyntaxError)",
            "severity": "WARNING",
            "rootCause": f"Python kodunda sözdizimi hatası: {err_msg}",
            "recommendation": "Kod dosyasındaki parantez, tırnak veya girinti kapatmalarını kontrol edin.",
            "quickAction": "view_logs",
            "matchSnippet": f"SyntaxError: {err_msg}",
        }

    # 6. WebSocket Connection Failure
    if "WebSocket connection failed" in text or "HTTP 451" in text:
        return {
            "hasError": True,
            "errorType": "WebSocket Bağlantı / IP Kısıtlaması (HTTP 451)",
            "severity": "WARNING",
            "rootCause": "Borsa WebSocket sunucusu bağlantıyı reddetti veya coğrafi IP kısıtlaması uyguladı.",
            "recommendation": "Sistem yüksek sadakatli sentetik fallback motoruna geçti. İsterseniz VPN / proxy kullanabilirsiniz.",
            "quickAction": "view_logs",
            "matchSnippet": "server rejected WebSocket connection",
        }

    # 7. Generic Test Failure
    if "Tests FAILED" in text:
        return {
            "hasError": True,
            "errorType": "Birim Test Başarısızlığı",
            "severity": "WARNING",
            "rootCause": "Kodlanan mantık kabul kriterleri veya pytest testlerinden geçemedi.",
            "recommendation": "Ajan otomatik retry adımında testi inceleyip düzeltecektir.",
            "quickAction": "view_logs",
            "matchSnippet": "Tests FAILED",
        }

    return {"hasError": False}


# ---------------------------------------------------------------------------
# In-Memory Live Log Handler with Instant File Flushing
# ---------------------------------------------------------------------------
class UIInMemoryLogHandler(logging.Handler):
    """Ring buffer handler that stores recent logs and flushes immediately to .ramazan/logs/live_session.log."""

    def __init__(self, capacity: int = 3000, root_dir: Optional[Path] = None):
        super().__init__()
        self.capacity = capacity
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._log_file = self.root_dir / ".ramazan" / "logs" / "live_session.log"
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            entry = {
                "id": len(self.logs) + 1,
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
            }
            with self._lock:
                self.logs.append(entry)
                if len(self.logs) > self.capacity:
                    self.logs.pop(0)

                # Instantly write & flush to live_session.log
                try:
                    clean_msg = _scrub_secrets(msg)
                    with open(self._log_file, "a", encoding="utf-8") as f:
                        f.write(f"[{entry['time']}] [{entry['level']}] {clean_msg}\n")
                        f.flush()
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_logs(self, since: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            if since >= len(self.logs):
                return []
            return list(self.logs[since:])

    def clear(self):
        with self._lock:
            self.logs.clear()


# Global Log Handler instance attached to ramazan logger
log_handler = UIInMemoryLogHandler()
log_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger("ramazan").addHandler(log_handler)
logging.getLogger("ramazan").setLevel(logging.INFO)


def _append_chat_task_milestone(proj_root: Path, task: Any):
    """Adds a rich, interactive task completion card to chat history."""
    try:
        path = proj_root / ".ramazan" / "chat_history.json"
        history = []
        if path.exists():
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                history = []

        file_cards = []
        for f in getattr(task, "files", []):
            full_f = proj_root / f
            if full_f.exists() and full_f.is_file():
                try:
                    content_str = full_f.read_text(encoding="utf-8", errors="replace")
                    lines_cnt = len(content_str.splitlines())
                    snippet = content_str[:1200]
                    file_cards.append({
                        "path": f,
                        "lines": lines_cnt,
                        "snippet": snippet,
                    })
                except Exception:
                    pass

        entry = {
            "id": f"msg-{len(history)+1}",
            "sender": "ramazan",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "task_milestone",
            "task": {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "testStatus": getattr(task, "testStatus", "PASSED"),
                "reviewStatus": getattr(task, "reviewStatus", "APPROVED"),
                "files": file_cards,
            },
            "text": (
                f"🎉 **[{task.id}] {task.title} Başarıyla Tamamlandı!**\n\n"
                f"📁 **Kodlanan Dosyalar & Konumları:**\n" +
                ("\n".join([f"- `📄 {fc['path']}` *({fc['lines']} satır)*" for fc in file_cards]) if file_cards else "Belirtilen görev dosyaları güncellendi.") + "\n\n"
                f"🧪 **Test Motoru:** `{getattr(task, 'testStatus', 'PASSED')}` ✅\n"
                f"🕵️ **Reviewer Onayı:** `{getattr(task, 'reviewStatus', 'APPROVED')}` ✅\n"
                f"📦 **Git:** Otomatik commit edildi ve GitHub'a push yapıldı 🚀"
            ),
            "actions": [
                {"label": "▶️ Sıradaki Görevi Başlat (Step)", "action": "step"},
                {"label": "⚡ Tümünü Otonom Koş (Run)", "action": "run"},
                {"label": "📋 Görev Listesi", "tab": "tasks"},
                {"label": "📡 Canlı Loglar", "tab": "logs"},
            ]
        }
        history.append(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Error appending chat milestone: {e}")


def _append_chat_project_delivery(proj_root: Path):
    """Adds a clear project delivery card with exact location, test commands, and quick reset."""
    try:
        path = proj_root / ".ramazan" / "chat_history.json"
        history = []
        if path.exists():
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                history = []

        proj_name = proj_root.name
        rel_folder = f"projects/{proj_name}"

        commands = []
        if (proj_root / "tests").exists():
            commands.append(f"pytest {rel_folder}/tests -v")
        if (proj_root / "src" / "server.py").exists():
            commands.append(f"cd {rel_folder} && python -m src.server")
        elif (proj_root / "main.py").exists():
            commands.append(f"python {rel_folder}/main.py")

        cmd_block = "\n".join([f"```bash\n{c}\n```" for c in commands]) if commands else f"```bash\ncd {rel_folder}\n```"
        game_f = _detect_game_file(proj_root)

        delivery_text = (
            f"🏆 **Proje Başarıyla Tamamlandı ve Teslim Edildi!**\n\n"
            f"📁 **Proje Konumu:** `{rel_folder}/`\n\n"
            f"⚡ **Çalıştırma / Test Komutu:**\n{cmd_block}\n\n"
            f"🛡️ **İzolasyon Durumu:** Ana orkestratör reposu temiz tutuldu. Tüm kodlar, testler ve incelemeler izole klasörde güvende.\n\n"
            f"✨ Yeni bir proje planlamak istediğinde aşağıdaki butona tıklayabilir veya **'yeni proje'** yazabilirsin!"
        )

        actions = [
            {"label": "✨ Yeni Projeye Başla (Sıfırla)", "prompt": "yeni proje"},
            {"label": "🧪 Proje Testlerini Çalıştır", "prompt": "testleri çalıştır"},
            {"label": "📋 Görev Özeti", "tab": "tasks"},
        ]
        if game_f:
            actions.insert(1, {"label": f"🎮 {proj_name} Başlat", "playProject": rel_folder, "projectTitle": proj_name})

        entry = {
            "id": f"msg-{len(history)+1}",
            "sender": "ramazan",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "project_delivery",
            "text": delivery_text,
            "actions": actions,
        }
        history.append(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Error appending project delivery: {e}")


def _append_chat_task_error(proj_root: Path, task: Any):
    """Adds a clear diagnostic and recovery card to chat history when a task is escalated or fails."""
    try:
        path = proj_root / ".ramazan" / "chat_history.json"
        history = []
        if path.exists():
            try:
                history = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                history = []

        diag = _analyze_error_log(getattr(task, "testOutput", "") or getattr(task, "lastError", "") or "")
        err_entry = {
            "id": f"msg-{len(history)+1}",
            "sender": "ramazan",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "task_error",
            "text": (
                f"⚠️ **[{task.id}] Görevinde Bir Durum Oluştu ({task.status})**\n\n"
                f"🛑 **Teşhis:** {diag.get('errorType', 'Birim Test veya Döngü Hatası')}\n"
                f"🔍 **Neden:** {diag.get('rootCause', getattr(task, 'lastError', '') or 'Test kriterleri henüz karşılanamadı.')}\n"
                f"💡 **Öneri:** {diag.get('recommendation', 'Görevi sıfırlayıp tekrar çalıştırmayı deneyebilirsiniz.')}"
            ),
            "actions": [
                {"label": f"🔄 {task.id} Sıfırla (Reset)", "prompt": f"ramazan reset {task.id}"},
                {"label": "📡 Canlı Logları İncele", "tab": "logs"},
            ]
        }
        history.append(err_entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Error appending chat error: {e}")


# ---------------------------------------------------------------------------
# Background Execution Manager (Non-blocking Step & Run)
# ---------------------------------------------------------------------------
class ExecutionManager:
    """Manages asynchronous background execution for tasks and pipelines."""

    def __init__(self):
        self.is_running = False
        self.action: Optional[str] = None  # "step" | "run" | "plan"
        self.current_task_id: Optional[str] = None
        self.message: str = "Hazır"
        self.last_result: Optional[Dict[str, Any]] = None
        self.started_at: Optional[float] = None
        self.cancel_requested: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = round(time.time() - self.started_at, 1) if self.started_at and self.is_running else 0.0
            return {
                "isRunning": self.is_running,
                "action": self.action,
                "currentTaskId": self.current_task_id,
                "message": self.message,
                "lastResult": self.last_result,
                "elapsed": elapsed,
            }

    def start_step(self, proj_root: Path, config: RamazanConfig) -> bool:
        with self._lock:
            if self.is_running:
                return False
            self.is_running = True
            self.action = "step"
            self.message = "Sıradaki görev yürütülüyor..."
            self.started_at = time.time()
            self.cancel_requested = False

        def _worker():
            try:
                orch = Orchestrator(proj_root, config)
                task = orch.run_next_task()
                with self._lock:
                    if task:
                        self.last_result = {
                            "success": True,
                            "task": task.model_dump(),
                            "message": f"Görev {task.id} tamamlandı: {task.status}",
                        }
                        self.message = f"{task.id} tamamlandı."
                        if task.status == "COMPLETED":
                            _append_chat_task_milestone(proj_root, task)
                        elif task.status in ["ESCALATED", "FAILED", "BLOCKED"]:
                            _append_chat_task_error(proj_root, task)
                    else:
                        self.last_result = {
                            "success": False,
                            "message": "Çalıştırılmaya hazır bekleyen görev bulunamadı.",
                        }
                        self.message = "Çalıştırılmaya hazır görev kalmadı."
            except Exception as e:
                logger.exception("Error executing step in background")
                with self._lock:
                    self.last_result = {"success": False, "error": str(e), "message": f"Hata: {str(e)}"}
                    self.message = f"Hata: {str(e)}"
            finally:
                with self._lock:
                    self.is_running = False
                    self.action = None

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return True

    def start_run(self, proj_root: Path, config: RamazanConfig, max_steps: int = 30) -> bool:
        with self._lock:
            if self.is_running:
                return False
            self.is_running = True
            self.action = "run"
            self.message = "Otonom pipeline yürütülüyor..."
            self.started_at = time.time()
            self.cancel_requested = False

        def _worker():
            try:
                orch = Orchestrator(proj_root, config)
                res = orch.run_all(max_iterations=max_steps)
                with self._lock:
                    self.last_result = {
                        "success": res.success,
                        "message": res.message,
                        "state": res.state.model_dump(),
                    }
                    self.message = res.message
                    if res.success:
                        proj_name = proj_root.name
                        _append_chat_task_milestone(proj_root, type("SimpleTask", (), {"id": "FINAL_AUDIT", "title": f"'{proj_name.replace('_', ' ').title()}' Tüm Görevler & Final Audit Tamamlandı", "status": "COMPLETED", "files": [], "testStatus": "PASSED", "reviewStatus": "APPROVED"})())
                        _append_chat_project_delivery(proj_root)
            except Exception as e:
                logger.exception("Error executing run in background")
                with self._lock:
                    self.last_result = {"success": False, "error": str(e), "message": f"Hata: {str(e)}"}
                    self.message = f"Hata: {str(e)}"
            finally:
                with self._lock:
                    self.is_running = False
                    self.action = None

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()
        return True


execution_manager = ExecutionManager()


# ---------------------------------------------------------------------------
# Project Scanner and Switcher Helper Functions
# ---------------------------------------------------------------------------
def _detect_game_file(folder: Path) -> Optional[Path]:
    """Finds index.html or entrypoint for playable web deliverables."""
    candidates = [
        folder / "index.html",
        folder / "src" / "index.html",
        folder / "dist" / "index.html",
        folder / "public" / "index.html",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _generate_project_slug(prompt: str, base_dir: Path) -> str:
    """Generates a clean directory slug for newly created isolated projects."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    clean = prompt.translate(tr_map).lower()
    words = re.findall(r'[a-z0-9]+', clean)
    stops = {"bir", "ve", "ile", "icin", "bu", "yap", "kodla", "tasarla", "proje", "uygulama", "lutfen", "istiyorum", "bana", "yaz"}
    keywords = [w for w in words if w not in stops][:3]
    if not keywords:
        keywords = ["yeni_proje"]
    slug = "_".join(keywords)
    projects_dir = base_dir / "projects"
    target = projects_dir / slug
    if target.exists():
        slug = f"{slug}_{int(time.time()) % 1000}"
    return slug


def scan_workspace_projects(ws_root: Path) -> List[Dict[str, Any]]:
    """Scans root directory and projects/ subdirectories for RAMAZAN AI projects."""
    projects: List[Dict[str, Any]] = []
    candidates: List[Path] = [ws_root]

    # Check projects/ subfolder
    projects_dir = ws_root / "projects"
    if projects_dir.exists() and projects_dir.is_dir():
        try:
            for sub in projects_dir.iterdir():
                if sub.is_dir() and not sub.name.startswith((".", "__")):
                    candidates.append(sub)
        except Exception:
            pass

    try:
        for p in ws_root.iterdir():
            if (
                p.is_dir()
                and not p.name.startswith((".", "__"))
                and p.name not in ["node_modules", "uploads", "tests", "src", "ramazan_ai.egg-info", "build", "dist", "projects"]
            ):
                candidates.append(p)
    except Exception:
        pass

    for d in candidates:
        has_ramazan = (d / ".ramazan").exists()
        game_path = _detect_game_file(d)

        # Include if it has .ramazan or game or is workspace root
        if has_ramazan or game_path or d == ws_root:
            task_count = 0
            progress = 0
            status = "HAZIR"
            title = d.name

            # Dynamic title formatting
            if d == ws_root:
                title = "Çalışma Alanı (Kök Dizin)"
            else:
                title = d.name.replace("_", " ").title()

            st_file = d / ".ramazan" / "state.json"
            if st_file.exists():
                try:
                    data = json.loads(st_file.read_text(encoding="utf-8"))
                    task_count = data.get("totalTasks", 0)
                    progress = int(data.get("progress", 0))
                    status = data.get("status", "HAZIR")
                except Exception:
                    pass

            projects.append({
                "name": title,
                "folder": str(d.relative_to(ws_root)) if d != ws_root else "",
                "path": str(d.resolve()),
                "hasRamazan": has_ramazan,
                "hasGame": game_path is not None,
                "gamePath": str(game_path.relative_to(d)) if game_path else None,
                "taskCount": task_count,
                "progress": progress,
                "status": status,
            })

    # Sort projects: root workspace first, then projects sorted by name
    projects.sort(key=lambda x: (x["folder"] != "", x["name"]))
    return projects


def create_app(root_dir: Optional[Path] = None) -> FastAPI:
    base_ws_root = (root_dir or find_project_root()).resolve()

    # Active project root pointer defaults to the meta-orchestrator factory
    active_root = {"path": base_ws_root}

    app = FastAPI(title="RAMAZAN AI Mobile Dashboard", version="2.5.0")

    def get_current_proj() -> Path:
        return active_root["path"]

    def set_current_proj(target: Path):
        active_root["path"] = target.resolve()

    def _get_chat_history_path() -> Path:
        chat_dir = get_current_proj() / ".ramazan"
        chat_dir.mkdir(parents=True, exist_ok=True)
        return chat_dir / "chat_history.json"

    def _load_chat_history() -> List[dict]:
        path = _get_chat_history_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Build dynamic welcome message with real available projects
        available_projects = scan_workspace_projects(base_ws_root)
        dynamic_actions = []

        for p in available_projects:
            if p["hasGame"]:
                dynamic_actions.append({
                    "label": f"🎮 {p['name']} Oyna",
                    "playProject": p["folder"],
                    "projectTitle": p["name"],
                })

        dynamic_actions.extend([
            {"label": "🚀 Yeni Yazılım / Oyun Planla", "prompt": "Mobil uyumlu tek dosya HTML canvas ve Web Audio API ile bir retro labirent oyunu planla ve kodla"},
            {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
            {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"},
        ])

        return [
            {
                "id": "msg-1",
                "sender": "ramazan",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": "Selam kanka! Ben **RAMAZAN AI**, senin otonom yazılım mühendisliği orkestratörünüm. 🚀\n\nNeye ihtiyacın var? Aklındaki yazılım projesini veya eklemek istediğin bir özelliği buraya yaz; mimarisini çıkarıp görevlere böleyim, kodlarını yazıp test edelim!",
                "actions": dynamic_actions,
            }
        ]

    def _save_chat_history(messages: List[dict]):
        path = _get_chat_history_path()
        path.write_text(json.dumps(messages, indent=2, ensure_ascii=False), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Multi-Project API Endpoints
    # -----------------------------------------------------------------------
    @app.get("/api/projects")
    def list_projects():
        current_p = get_current_proj()
        projects = scan_workspace_projects(base_ws_root)
        active_game = _detect_game_file(current_p)
        return {
            "currentPath": str(current_p.resolve()),
            "currentFolder": current_p.name if current_p != base_ws_root else "",
            "hasGame": active_game is not None,
            "gameUrl": f"/play/{current_p.name}" if (current_p != base_ws_root and active_game) else ("/play" if active_game else None),
            "projects": projects,
        }

    @app.post("/api/projects/switch")
    def switch_project(payload: dict = Body(...)):
        target_path_str = payload.get("path", "").strip()
        if not target_path_str:
            raise HTTPException(status_code=400, detail="Proje yolu belirtilmedi.")

        target = Path(target_path_str).resolve()
        if not target.exists() or not target.is_dir():
            raise HTTPException(status_code=404, detail="Hedef proje klasörü bulunamadı.")

        active_root["path"] = target
        logger.info(f"Switched active project to: {target}")
        return {
            "success": True,
            "currentPath": str(target),
            "currentFolder": target.name if target != base_ws_root else "",
            "message": f"Aktif proje değiştirildi: {target.name}",
        }

    # -----------------------------------------------------------------------
    # Static & Live File Preview with Proper MIME Types
    # -----------------------------------------------------------------------
    @app.get("/preview/{file_path:path}")
    def preview_file(file_path: str):
        curr = get_current_proj()
        target = (curr / file_path).resolve()

        # Fallback to base workspace root if not found in subproject
        if not target.exists():
            fallback = (base_ws_root / file_path).resolve()
            if fallback.exists():
                target = fallback

        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail=f"Dosya bulunamadı: {file_path}")

        # Correct MIME Types to allow browser script/style execution
        mime_type, _ = mimetypes.guess_type(str(target))
        suffix = target.suffix.lower()

        if suffix in [".html", ".htm"]:
            mime_type = "text/html; charset=utf-8"
        elif suffix in [".js", ".mjs"]:
            mime_type = "application/javascript; charset=utf-8"
        elif suffix in [".css"]:
            mime_type = "text/css; charset=utf-8"
        elif suffix in [".json"]:
            mime_type = "application/json; charset=utf-8"
        elif suffix in [".svg"]:
            mime_type = "image/svg+xml"
        elif suffix in [".png"]:
            mime_type = "image/png"
        elif suffix in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif suffix in [".mp3"]:
            mime_type = "audio/mpeg"
        elif suffix in [".wav"]:
            mime_type = "audio/wav"
        elif suffix in [".ts", ".tsx", ".py", ".md", ".txt", ".yaml", ".yml", ".toml"]:
            mime_type = "text/plain; charset=utf-8"
        elif not mime_type:
            mime_type = "application/octet-stream"

        return FileResponse(target, media_type=mime_type)

    @app.get("/api/file")
    def get_file_content(path: str = Query(...)):
        """Returns raw text content for the code inspection modal."""
        curr = get_current_proj()
        target = (curr / path).resolve()
        if not target.exists():
            target = (base_ws_root / path).resolve()

        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Dosya bulunamadı.")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            return {
                "path": path,
                "content": content,
                "size": target.stat().st_size,
                "extension": target.suffix.lower(),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dosya okunamadı: {str(e)}")

    # -----------------------------------------------------------------------
    # Playable Deliverable Direct Launchers
    # -----------------------------------------------------------------------
    @app.get("/play/{project_name:path}")
    def play_project(project_name: str):
        target_dir = (base_ws_root / project_name).resolve()
        if not target_dir.exists():
            target_dir = (base_ws_root / "projects" / project_name).resolve()
        if target_dir.exists() and target_dir.is_dir():
            game = _detect_game_file(target_dir)
            if game:
                return FileResponse(game, media_type="text/html; charset=utf-8")
        raise HTTPException(status_code=404, detail=f"'{project_name}' için çalıştırılabilir web arayüzü bulunamadı.")

    @app.get("/play")
    def play_active():
        game = _detect_game_file(get_current_proj())
        if game:
            return FileResponse(game, media_type="text/html; charset=utf-8")

        # Fallback to first project with a game
        for p in scan_workspace_projects(base_ws_root):
            if p["hasGame"] and p["folder"]:
                g = _detect_game_file(base_ws_root / p["folder"])
                if g:
                    return FileResponse(g, media_type="text/html; charset=utf-8")

        raise HTTPException(status_code=404, detail="Çalıştırılabilir oyun veya web sayfası bulunamadı.")

    @app.get("/game")
    @app.get("/game/cops")
    def legacy_game_redirect():
        """Redirect legacy URLs to active playable game."""
        return play_active()

    # -----------------------------------------------------------------------
    # Live Log Streaming, Diagnostic & Download Endpoints
    # -----------------------------------------------------------------------
    @app.get("/api/logs")
    def get_logs(since: int = Query(0)):
        new_logs = log_handler.get_logs(since=since)
        return {
            "logs": new_logs,
            "total": len(log_handler.logs),
            "since": since,
        }

    @app.get("/api/logs/download")
    def download_logs():
        """Downloads full live_session.log file."""
        curr = get_current_proj()
        log_file = curr / ".ramazan" / "logs" / "live_session.log"
        if not log_file.exists():
            log_file.parent.mkdir(parents=True, exist_ok=True)
            content = "\n".join([f"[{l['time']}] [{l['level']}] {_scrub_secrets(l['message'])}" for l in log_handler.logs])
            log_file.write_text(content, encoding="utf-8")
        return FileResponse(
            str(log_file),
            filename="live_session.log",
            media_type="text/plain; charset=utf-8"
        )

    @app.get("/api/logs/diagnose")
    def diagnose_logs():
        """Analyzes recent logs and returns smart error diagnostics and root cause solutions."""
        recent_logs = log_handler.get_logs(since=max(0, len(log_handler.logs) - 80))
        full_text = "\n".join([l["message"] for l in recent_logs])
        return _analyze_error_log(full_text)

    @app.post("/api/logs/clear")
    def clear_logs():
        log_handler.clear()
        return {"success": True}

    # -----------------------------------------------------------------------
    # Core Dashboard Status Endpoint
    # -----------------------------------------------------------------------
    @app.get("/api/status")
    def get_status():
        curr = get_current_proj()
        state_mgr = StateManager(curr)
        task_eng = TaskEngine(curr)
        config = RamazanConfig.load(curr)
        state = state_mgr.load()

        tasks_list = [t.model_dump() for t in task_eng.tasks.values()]

        # Latest test result
        test_file = curr / ".ramazan" / "tests" / "latest.json"
        latest_test = None
        if test_file.exists():
            try:
                latest_test = json.loads(test_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Final audit
        audit_file = curr / ".ramazan" / "FINAL_AUDIT.md"
        audit_summary = audit_file.read_text(encoding="utf-8") if audit_file.exists() else None

        active_game = _detect_game_file(curr)

        return {
            "currentProject": curr.name if curr != base_ws_root else "Root",
            "currentPath": str(curr),
            "hasGame": active_game is not None,
            "gameUrl": f"/play/{curr.name}" if (curr != base_ws_root and active_game) else ("/play" if active_game else None),
            "state": state.model_dump(),
            "tasks": tasks_list,
            "config": config.model_dump(),
            "latestTest": latest_test,
            "auditSummary": audit_summary,
            "execution": execution_manager.get_status(),
        }

    # -----------------------------------------------------------------------
    # Interactive Chat with Live LLM / Transparent Planning
    # -----------------------------------------------------------------------
    @app.get("/api/chat")
    def get_chat():
        return {"messages": _load_chat_history()}

    @app.post("/api/chat")
    def post_chat(payload: dict = Body(...)):
        history = _load_chat_history()
        curr = get_current_proj()
        try:
            user_message = payload.get("message", "").strip()
            if not user_message:
                raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

            user_entry = {
                "id": f"msg-{len(history)+1}",
                "sender": "user",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "text": user_message,
            }
            history.append(user_entry)

            config = RamazanConfig.load(curr)
            orch = Orchestrator(curr, config)

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
                detected_projects = scan_workspace_projects(base_ws_root)
                chat_actions = [
                    {"label": f"🎮 {p['name']}", "playProject": p["folder"], "projectTitle": p["name"]}
                    for p in detected_projects if p["hasGame"] and p["folder"]
                ]
                chat_actions.extend([
                    {"label": "🚀 Yeni Proje Başlat", "prompt": "Yeni bir proje planlamak istiyorum"},
                    {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
                    {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"},
                ])
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": chat_actions,
                }

            # 2. API Key ve Mod Durumu
            elif any(w in msg_lower for w in ["api key", "apikey", "anahtar", "şart mı", "gerekli mi", "ücretsiz", "bedava"]):
                is_live = not orch.llm_client.use_mock
                status_badge = "✅ Canlı LLM Modu Aktif" if is_live else "⚠️ Çevrimdışı / Simülasyon Modu"
                resp_text = (
                    f"🔑 **API Anahtarı ve LLM Durumu:** {status_badge}\n\n"
                    "RAMAZAN AI iki farklı modda çalışabilir:\n\n"
                    "1. **Çevrimdışı / Simülasyon Modu:**\n"
                    "   - API anahtarına gerek yoktur. Deterministik motorla yerel çalışır.\n\n"
                    "2. **Canlı LLM Modu:**\n"
                    "   - Gemini, Claude veya OpenAI anahtarını girdiğinde tüm kodlar ve mimari canlı yapay zeka ajanları tarafından üretilir.\n"
                    "   - Anahtarını **API & Model** sekmesinden hemen kaydedebilirsin."
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "🔑 API & Model Ayarlarına Git", "tab": "api"},
                        {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
                    ],
                }

            # 3. Testleri Çalıştır
            elif any(w in msg_lower for w in ["testleri çalıştır", "test et", "test koş", "testler"]):
                test_res = orch.test_engine.run_tests()
                resp_text = (
                    f"🧪 **Test Motoru Sonucu ({curr.name}):**\n\n"
                    f"- Durum: {'✅ **BAŞARILI (PASSED)**' if test_res.passed else '❌ **BAŞARISIZ (FAILED)**'}\n"
                    f"- Çıkış Kodu: `{test_res.exitCode}`\n"
                    f"- Süre: `{test_res.duration}s`\n"
                    f"- Koşulan Test Sayısı: `{test_res.testsRun}` (Hata: {test_res.failures})\n"
                    f"- Özet: {test_res.summary}"
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "📋 Görevleri Gör", "tab": "tasks"},
                        {"label": "📡 Canlı Logları İncele", "tab": "logs"},
                    ],
                }

            # 4. Adım At / Yürüt
            elif any(w in msg_lower for w in ["çalıştır", "yürüt", "adım at", "başlat"]) and "tüm" not in msg_lower and "yeni" not in msg_lower:
                execution_manager.start_step(curr, config)
                resp_text = (
                    "▶️ **Sıradaki görev arka planda başlatıldı!**\n\n"
                    "Worker ajanı kodları yazıyor, test motoru doğrulamaları yapıyor ve Reviewer denetimden geçiriyor.\n"
                    "Canlı ilerlemeyi ve terminal çıktılarını **Loglar** sekmesinden gerçek zamanlı izleyebilirsin."
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "📡 Canlı Logları Aç", "tab": "logs"},
                        {"label": "📋 Görev Listesi", "tab": "tasks"},
                    ],
                }

            # 5. Yeni Proje / Kök Dizine Dönüş
            elif any(w in msg_lower for w in ["yeni proje", "ana menü", "ana dizin", "kök dizin", "yeni görev", "yeni bir şey", "sıfırla", "temizle"]):
                set_current_proj(base_ws_root)
                resp_text = (
                    "✨ **Hazırım kanka! Çalışma alanı yeni bir proje için hazırlandı.**\n\n"
                    "Geliştirmek istediğin yeni oyunu, web uygulamasını veya servisi yazabilirsin.\n"
                    "Sen yazdığında `projects/` altında tertemiz yeni bir klasör açıp hemen kodlamaya başlayacağım! 🚀"
                )
                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "🎮 Retro Yılan Oyunu Planla", "prompt": "HTML canvas ile retro yılan oyunu yap"},
                        {"label": "📊 Kripto Takip Botu Planla", "prompt": "Basit bir kripto fiyat takip scripti yap"},
                        {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"},
                    ],
                }

            # 6. Genel Yazılım Talebi / Mimari Planlama
            else:
                # If currently at root, create an isolated directory in projects/<slug>/
                if curr == base_ws_root:
                    slug = _generate_project_slug(user_message, base_ws_root)
                    target_proj = base_ws_root / "projects" / slug
                    target_proj.mkdir(parents=True, exist_ok=True)

                    # Initialize target project with clean .ramazan config & architecture
                    p_ramazan = target_proj / ".ramazan"
                    p_ramazan.mkdir(parents=True, exist_ok=True)
                    (p_ramazan / "architecture.md").write_text("# Mimari Standartlar\nTemiz modüler mimari ve birim testler zorunludur.\n", encoding="utf-8")

                    # Copy or generate config
                    p_config = RamazanConfig.load(base_ws_root)
                    p_config.system.name = slug.replace('_', ' ').title()
                    p_config.save(target_proj)

                    # Set active project
                    set_current_proj(target_proj)
                    curr = target_proj
                    orch = Orchestrator(curr, p_config)
                    is_new_isolated = True
                else:
                    is_new_isolated = False

                req_file = curr / ".ramazan" / "requirements.md"
                req_file.parent.mkdir(parents=True, exist_ok=True)
                req_content = (
                    f"# Proje Gereksinimleri: {curr.name}\n\n"
                    f"## Kullanıcı Talebi\n{user_message}\n\n"
                    f"## Tarih\n{datetime.now(timezone.utc).isoformat()}\n"
                )
                req_file.write_text(req_content, encoding="utf-8")

                arch = orch.context_builder.load_architecture_rules()

                from ramazan.agents.orchestrator_agent import OrchestratorAgent

                orch_agent = OrchestratorAgent(
                    model_config=orch.router.get_orchestrator_model(),
                    llm_client=orch.llm_client,
                    cost_tracker=orch.cost_tracker,
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

                for t in planned:
                    orch.task_engine.add_task(t)

                orch.state_manager.recompute(orch.task_engine)

                task_bullets = "\n".join([
                    f"- **`{t.id}`**: {t.title} *(Öncelik: {t.priority.upper()})*\n  📁 Hedef: {', '.join([f'`{f}`' for f in t.files])}"
                    for t in planned
                ])

                folder_note = f"📁 **İzole Proje Klasörü:** `projects/{curr.name}/`\n" if is_new_isolated else f"📁 **Aktif Proje:** `{curr.name}`\n"

                resp_text = (
                    f"🎯 **Talebini aldım kanka! Ajanlar için izole mimari plan hazırlandı:**\n\n"
                    f"{folder_note}\n"
                    f"📋 **Planlanan Görevler ({len(planned)} Adet):**\n"
                    f"{task_bullets}\n\n"
                    f"Ajanlar bu klasör içinde çalışacak; ana sistem temiz kalacak. İster **adım adım başlat**, ister **tümünü otonom koş**!"
                )

                bot_entry = {
                    "id": f"msg-{len(history)+1}",
                    "sender": "ramazan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "text": resp_text,
                    "actions": [
                        {"label": "▶️ İlk Görevi Başlat (Step)", "action": "step"},
                        {"label": "⚡ Hepsini Otonom Yap (Run)", "action": "run"},
                        {"label": "📋 Görevler Sekmesine Geç", "tab": "tasks"},
                    ],
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
                    {"label": "🧪 Testleri Çalıştır", "prompt": "testleri çalıştır"},
                    {"label": "📡 Logları Gör", "tab": "logs"},
                ],
            }
            history.append(err_entry)
            _save_chat_history(history)
            return {"response": err_entry, "messages": history}

    # -----------------------------------------------------------------------
    # Non-blocking Asynchronous Execution Endpoints
    # -----------------------------------------------------------------------
    @app.get("/api/execution/status")
    def execution_status():
        return execution_manager.get_status()

    @app.post("/api/step")
    def execute_step():
        curr = get_current_proj()
        config = RamazanConfig.load(curr)
        started = execution_manager.start_step(curr, config)
        if not started:
            return {"success": False, "status": "busy", "message": "Zaten aktif bir yürütme devam ediyor."}
        return {"success": True, "status": "started", "message": "Görev arka planda başlatıldı."}

    @app.post("/api/run")
    def execute_run(max_steps: int = 30):
        curr = get_current_proj()
        config = RamazanConfig.load(curr)
        started = execution_manager.start_run(curr, config, max_steps=max_steps)
        if not started:
            return {"success": False, "status": "busy", "message": "Zaten aktif bir yürütme devam ediyor."}
        return {"success": True, "status": "started", "message": "Otonom pipeline arka planda başlatıldı."}

    @app.post("/api/test")
    def run_tests():
        curr = get_current_proj()
        test_eng = TestEngine(curr)
        res = test_eng.run_tests()
        return res.model_dump()

    @app.post("/api/audit")
    def run_audit():
        curr = get_current_proj()
        auditor = FinalAuditor(curr)
        report = auditor.run_audit()
        return report.model_dump()

    @app.post("/api/configure")
    def configure_key(payload: dict = Body(...)):
        curr = get_current_proj()
        key = payload.get("key", "").strip()
        mode = payload.get("mode", "").strip()

        config = RamazanConfig.load(curr)

        if mode:
            config.system.autonomyMode = mode

        detected_info = None
        if key:
            detected = SmartKeyDetector.detect_provider(key)
            if detected:
                provider, env_var, models = detected
                os.environ[env_var] = key

                # Write to active project .env AND base workspace .env
                for target_env_dir in [curr / ".ramazan", base_ws_root / ".ramazan"]:
                    target_env_dir.mkdir(parents=True, exist_ok=True)
                    env_file = target_env_dir / ".env"
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

        config.save(curr)
        return {
            "success": True,
            "detected": detected_info,
            "config": config.model_dump(),
        }

    @app.get("/api/task/{task_id}")
    def get_task_details(task_id: str):
        curr = get_current_proj()
        task_eng = TaskEngine(curr)
        task = task_eng.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Görev bulunamadı.")

        mem_file = curr / ".ramazan" / "memory" / f"{task_id}.md"
        mem = mem_file.read_text(encoding="utf-8") if mem_file.exists() else None

        rev_file = curr / ".ramazan" / "reviews" / f"{task_id}.md"
        rev = rev_file.read_text(encoding="utf-8") if rev_file.exists() else None

        esc_md = curr / ".ramazan" / "logs" / f"ESCALATION-{task_id}.md"
        esc = esc_md.read_text(encoding="utf-8") if esc_md.exists() else None

        return {
            "task": task.model_dump(),
            "memory": mem,
            "review": rev,
            "escalation": esc,
        }

    @app.post("/api/task/{task_id}/reset")
    def reset_task(task_id: str):
        curr = get_current_proj()
        task_eng = TaskEngine(curr)
        state_mgr = StateManager(curr)
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
        curr = get_current_proj()
        adrs = ADRManager.list_adrs(curr)
        return {"adrs": [a.model_dump() for a in adrs]}

    @app.post("/api/adrs")
    def post_adr(payload: dict = Body(...)):
        curr = get_current_proj()
        decision = payload.get("decision", "").strip()
        context = payload.get("context", "").strip()
        if not decision:
            raise HTTPException(status_code=400, detail="Karar boş olamaz.")
        adr = ADRManager.create_adr(
            root_dir=curr,
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
        curr = get_current_proj()
        arch_file = curr / ".ramazan" / "architecture.md"
        arch_content = arch_file.read_text(encoding="utf-8") if arch_file.exists() else ""

        decisions_dir = curr / ".ramazan" / "decisions"
        adrs = []
        if decisions_dir.exists():
            for f in sorted(decisions_dir.glob("ADR-*.md")):
                adrs.append({
                    "id": f.stem,
                    "content": f.read_text(encoding="utf-8"),
                })

        return {
            "architecture": arch_content,
            "adrs": adrs,
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return MOBILE_HTML_DASHBOARD

    return app


# ---------------------------------------------------------------------------
# Mobile-First HTML/CSS/JavaScript Dashboard UI
# ---------------------------------------------------------------------------
MOBILE_HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content">
  <title>RAMAZAN AI Web Dashboard</title>
  <style>
    :root {
      --bg: #080d1a;
      --card-bg: #111827;
      --card-border: #1f293d;
      --card-hover: #1e293b;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --emerald: #10b981;
      --emerald-bg: rgba(16, 185, 129, 0.15);
      --amber: #f59e0b;
      --amber-bg: rgba(245, 158, 11, 0.15);
      --rose: #f43f5e;
      --cyan: #06b6d4;
      --purple: #8b5cf6;
      --bottom-nav-height: 60px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
    html, body {
      width: 100%;
      height: 100%;
      height: 100dvh;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    body {
      display: flex;
      flex-direction: column;
    }

    /* Top App Bar */
    .app-header {
      background: rgba(17, 24, 39, 0.96);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.6rem 0.9rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      z-index: 40;
      gap: 0.5rem;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      min-width: 0;
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
      font-size: 1.05rem;
      color: #fff;
      flex-shrink: 0;
    }
    .project-selector {
      background: #1e293b;
      color: #f8fafc;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 0.35rem 0.6rem;
      font-size: 0.82rem;
      font-weight: 700;
      outline: none;
      cursor: pointer;
      max-width: 160px;
      text-overflow: ellipsis;
    }
    .project-selector:focus { border-color: var(--primary); }
    .header-right {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-shrink: 0;
    }
    .btn-play-header {
      background: linear-gradient(135deg, #10b981, #059669);
      color: #fff;
      border: none;
      border-radius: 20px;
      padding: 0.35rem 0.75rem;
      font-size: 0.76rem;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      cursor: pointer;
      box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
      animation: pulse 2.2s infinite ease-in-out;
    }
    @keyframes pulse {
      0%, 100% { box-shadow: 0 0 8px rgba(16, 185, 129, 0.3); }
      50% { box-shadow: 0 0 18px rgba(16, 185, 129, 0.7); }
    }
    .status-badge {
      font-size: 0.68rem;
      font-weight: 800;
      padding: 0.22rem 0.5rem;
      border-radius: 9999px;
      background: var(--emerald-bg);
      color: var(--emerald);
      border: 1px solid rgba(16, 185, 129, 0.3);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .status-badge.working {
      background: var(--amber-bg);
      color: var(--amber);
      border-color: rgba(245, 158, 11, 0.4);
    }

    /* Content Area & Tabs */
    .content-area {
      flex: 1 1 0;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
    }
    .tab-pane {
      display: none;
      height: 100%;
      overflow-y: auto;
      padding: 1rem 0.9rem calc(var(--bottom-nav-height) + 1rem) 0.9rem;
      max-width: 720px;
      width: 100%;
      margin: 0 auto;
      -webkit-overflow-scrolling: touch;
    }
    .tab-pane.active {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* Card Component */
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
    #tab-chat.active {
      padding: 0;
      display: flex;
      flex-direction: column;
      height: calc(100% - var(--bottom-nav-height));
    }
    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      max-width: 720px;
      margin: 0 auto;
      width: 100%;
    }
    .chat-messages {
      flex: 1 1 0;
      min-height: 0;
      overflow-y: auto;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }
    .chat-bubble {
      max-width: 88%;
      padding: 0.8rem 1rem;
      border-radius: 16px;
      font-size: 0.9rem;
      line-height: 1.45;
      word-break: break-word;
    }
    .chat-bubble.ramazan {
      align-self: flex-start;
      background: #141e30;
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
      padding: 0.35rem 0.75rem;
      font-size: 0.76rem;
      color: #fff;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      transition: background 0.15s;
    }
    .chip-btn:active { background: var(--primary); }

    .chat-input-bar {
      padding: 0.55rem 0.8rem;
      background: var(--card-bg);
      border-top: 1px solid var(--card-border);
      display: flex;
      gap: 0.5rem;
      align-items: center;
      flex-shrink: 0;
    }
    .chat-input {
      flex: 1;
      background: #090e1a;
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
    .task-item.failed { border-left: 4px solid var(--rose); }

    .task-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .task-title {
      font-size: 0.95rem;
      font-weight: 700;
    }

    /* Code Windows & Accordions in Chat */
    .code-window {
      background: #060913;
      border: 1px solid #1e293b;
      border-radius: 8px;
      margin: 0.5rem 0;
      overflow: hidden;
    }
    .code-window-header {
      background: #0f172a;
      padding: 0.3rem 0.6rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #1e293b;
    }
    .code-lang-tag {
      font-size: 0.7rem;
      color: var(--cyan);
      font-weight: 700;
      text-transform: uppercase;
      font-family: monospace;
    }
    .mini-copy-btn {
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: #e2e8f0;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      font-size: 0.7rem;
      cursor: pointer;
      font-family: inherit;
    }
    .mini-copy-btn:active {
      background: var(--emerald);
      color: #000;
    }
    .code-accordion {
      background: #090e1a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      margin: 0.35rem 0;
      overflow: hidden;
    }
    .code-summary {
      padding: 0.45rem 0.65rem;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.78rem;
      background: #0f172a;
      user-select: none;
    }
    .code-summary::-webkit-details-marker {
      display: none;
    }
    .code-snippet-box {
      padding: 0.6rem;
      margin: 0;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      line-height: 1.4;
      color: #7dd3fc;
      background: #060913;
      overflow-x: auto;
      max-height: 280px;
      white-space: pre;
    }

    /* TAB 3: Live Logs Terminal */
    .terminal-box {
      background: #050811;
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 0.8rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.78rem;
      line-height: 1.5;
      color: #cbd5e1;
      height: calc(100vh - 220px);
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .log-entry { margin-bottom: 0.3rem; }
    .log-time { color: var(--muted); margin-right: 0.4rem; }
    .log-INFO { color: #38bdf8; }
    .log-WARNING { color: #fbbf24; font-weight: 700; }
    .log-ERROR { color: #f43f5e; font-weight: 800; }

    /* Bottom Navigation Toolbar */
    .bottom-nav {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      height: var(--bottom-nav-height);
      background: rgba(17, 24, 39, 0.97);
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
      gap: 0.15rem;
      color: var(--muted);
      text-decoration: none;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.35rem 0.6rem;
      border-radius: 10px;
      border: none;
      background: transparent;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .nav-item svg {
      width: 20px;
      height: 20px;
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

    /* Modals */
    .modal-backdrop {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.85);
      backdrop-filter: blur(5px);
      display: none;
      justify-content: center;
      align-items: flex-end;
      z-index: 100;
    }
    .modal-bottom-sheet {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 20px 20px 0 0;
      max-height: 90vh;
      width: 100%;
      max-width: 680px;
      overflow-y: auto;
      padding: 1.2rem;
      display: flex;
      flex-direction: column;
      gap: 0.9rem;
      animation: slideUp 0.2s ease;
    }
    @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }

    /* Toast Notification */
    .toast {
      position: fixed;
      top: 1rem;
      left: 50%;
      transform: translateX(-50%);
      background: var(--card-bg);
      border: 1px solid var(--emerald);
      color: #fff;
      padding: 0.55rem 1.1rem;
      border-radius: 20px;
      font-size: 0.82rem;
      font-weight: 700;
      display: none;
      z-index: 200;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    }
  </style>
</head>
<body>

  <!-- Top App Header -->
  <header class="app-header">
    <div class="header-left">
      <div class="header-logo">R</div>
      <select id="project-selector" class="project-selector" onchange="switchProject(this.value)">
        <option value="">Yükleniyor...</option>
      </select>
    </div>
    <div class="header-right">
      <button id="btn-header-play" class="btn-play-header" style="display: none;" onclick="openGameModal()">
        <span>🎮</span><span>Oyna</span>
      </button>
      <span class="status-badge" id="header-status">HAZIR</span>
    </div>
  </header>

  <!-- Main Content Container -->
  <div class="content-area">

    <!-- TAB 1: Chat -->
    <div id="tab-chat" class="tab-pane active">
      <div class="chat-container">
        <div class="chat-messages" id="chat-messages">
          <!-- Populated dynamically -->
        </div>

        <div class="chat-input-bar">
          <input type="text" id="chat-input" class="chat-input" placeholder="Ne yapmak istiyorsun kanka? Yaz..." onkeypress="handleKey(event)">
          <button class="chat-send-btn" onclick="sendChat()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- TAB 2: Tasks & Pipeline -->
    <div id="tab-tasks" class="tab-pane">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
          <span style="font-size: 0.8rem; font-weight: 700; color: var(--muted); text-transform: uppercase;">İlerleme</span>
          <span style="font-size: 0.85rem; font-weight: 800; color: var(--emerald);" id="pipeline-progress-text">0%</span>
        </div>
        <div style="background: rgba(255,255,255,0.08); height: 8px; border-radius: 9999px; overflow: hidden;">
          <div id="pipeline-progress-bar" style="background: linear-gradient(90deg, #3b82f6, #10b981); width: 0%; height: 100%; transition: width 0.3s ease;"></div>
        </div>
        <div style="display: flex; gap: 0.5rem; margin-top: 1rem;">
          <button id="btn-step" class="btn btn-emerald btn-block" onclick="executeStep()">
            ▶️ Sıradaki Adım (Step)
          </button>
          <button id="btn-run" class="btn btn-primary btn-block" onclick="executeRun()">
            ⚡ Tümünü Otonom Koş
          </button>
        </div>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.4rem;">
        <span style="font-size: 0.82rem; font-weight: 800; color: var(--muted);">GÖREV LİSTESİ (DAG)</span>
        <button id="btn-card-play" class="btn btn-outline" style="display: none; padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="openGameModal()">🎮 Canlı Oyun</button>
      </div>
      <div id="tasks-list" style="display: flex; flex-direction: column; gap: 0.75rem;">
        <!-- Populated dynamically -->
      </div>
    </div>

    <!-- TAB 3: Live Terminal & Agent Logs -->
    <div id="tab-logs" class="tab-pane">
      <div class="card" style="padding: 0.8rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.4rem;">
          <div style="font-size: 0.85rem; font-weight: 800; display: flex; align-items: center; gap: 0.4rem;">
            <span>📡 Canlı Terminal & Ajan Logları</span>
            <span id="log-count-badge" style="font-size: 0.7rem; background: #1e293b; padding: 0.15rem 0.45rem; border-radius: 12px; color: var(--cyan);">0</span>
            <span style="font-size: 0.68rem; color: var(--emerald); font-weight: 600;">(live_session.log ●)</span>
          </div>
          <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
            <button class="btn btn-outline" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="copyAllLogs()">📋 Tümünü Kopyala</button>
            <button class="btn btn-outline" style="padding: 0.25rem 0.55rem; font-size: 0.75rem; border-color: var(--amber); color: var(--amber);" onclick="copyLastError()">⚠️ Hatayı Kopyala</button>
            <a href="/api/logs/download" target="_blank" class="btn btn-outline" style="padding: 0.25rem 0.55rem; font-size: 0.75rem; text-decoration: none; display: inline-flex; align-items: center;">📥 .log İndir</a>
            <button class="btn btn-outline" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="clearLogsUI()">Temizle</button>
          </div>
        </div>

        <!-- Smart Diagnostic Banner -->
        <div id="error-diag-card" style="display: none; margin-bottom: 0.6rem; padding: 0.75rem; border-radius: 10px; background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.35);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.3rem;">
            <div style="font-weight: 800; font-size: 0.82rem; color: var(--amber); display: flex; align-items: center; gap: 0.35rem;">
              <span>💡 Akıllı Hata Teşhisi:</span>
              <span id="diag-type" style="color: #fff;">-</span>
            </div>
            <button onclick="document.getElementById('error-diag-card').style.display='none'" style="background:none; border:none; color:var(--muted); cursor:pointer; font-size:0.9rem;">&times;</button>
          </div>
          <div style="font-size: 0.76rem; color: #cbd5e1; margin-bottom: 0.4rem;" id="diag-cause">-</div>
          <div style="font-size: 0.76rem; color: var(--emerald); font-weight: 600; margin-bottom: 0.4rem;" id="diag-recommendation">-</div>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <button id="diag-action-btn" class="chip-btn" style="background: rgba(16, 185, 129, 0.2); border-color: var(--emerald); font-size: 0.72rem; display: none;">💡 Komutu Kopyala</button>
            <button class="chip-btn" style="background: rgba(245, 158, 11, 0.2); border-color: var(--amber); font-size: 0.72rem;" onclick="copyLastError()">📋 Teşhisi Kopyala</button>
          </div>
        </div>

        <div id="terminal-box" class="terminal-box">Yükleniyor...</div>
      </div>
    </div>

    <!-- TAB 4: API & Models -->
    <div id="tab-api" class="tab-pane">
      <div class="card">
        <h3 style="font-size: 1.05rem; font-weight: 800; margin-bottom: 0.4rem;">🔑 Akıllı API Yapılandırması</h3>
        <p style="font-size: 0.82rem; color: var(--muted); margin-bottom: 1rem;">
          API anahtarını yapıştır; sistem Gemini, Claude, OpenAI veya DeepSeek olduğunu kendisi tanır ve ajan rollerine otomatik dağıtır.
        </p>

        <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.8rem;">
          <label style="font-size: 0.8rem; font-weight: 600; color: var(--muted);">API Anahtarı / Endpoint:</label>
          <input type="password" id="api-key-box" style="background: #090e1a; border: 1px solid var(--card-border); border-radius: 10px; padding: 0.7rem; color: #fff; font-size: 0.9rem;" placeholder="sk-ant-... veya AIza... veya AQ....">
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem;">
          <label style="font-size: 0.8rem; font-weight: 600; color: var(--muted);">Çalışma Modu (Human-in-the-Loop):</label>
          <select id="api-mode-box" style="background: #090e1a; border: 1px solid var(--card-border); border-radius: 10px; padding: 0.7rem; color: #fff; font-size: 0.85rem;">
            <option value="step_by_step">Adım Adım (Her görevde durur ve onay bekler)</option>
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

    <!-- TAB 5: Report & Test -->
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
        <pre id="audit-report-box" style="font-size: 0.8rem; background: #050811; padding: 0.75rem; border-radius: 8px; overflow-x: auto; color: #cbd5e1; max-height: 250px;">Yükleniyor...</pre>
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
    <button class="nav-item" onclick="switchNav('tab-logs', this)">
      <svg viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
      <span>Loglar</span>
    </button>
    <button class="nav-item" onclick="switchNav('tab-api', this)">
      <svg viewBox="0 0 24 24"><circle cx="7.5" cy="15.5" r="5.5"></circle><path d="M21 2l-9.6 9.6"></path><path d="M15.5 7.5l3 3L22 7l-3-3"></path></svg>
      <span>API & Model</span>
    </button>
    <button class="nav-item" onclick="switchNav('tab-report', this)">
      <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
      <span>Raporlar</span>
    </button>
  </nav>

  <!-- Modal Task Details -->
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
    <div class="modal-bottom-sheet" style="max-height: 95vh; padding: 0.75rem;" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; padding: 0 0.4rem;">
        <h4 id="game-modal-title" style="font-size: 0.98rem; font-weight: 800;">🎮 Canlı Web Uygulaması / Oyun</h4>
        <div style="display: flex; gap: 0.4rem;">
          <a id="game-modal-link" href="/play" target="_blank" class="btn btn-outline" style="padding: 0.25rem 0.6rem; font-size: 0.75rem; text-decoration: none;">Tam Ekran ↗</a>
          <button class="btn btn-outline" style="padding: 0.2rem 0.5rem;" onclick="closeGameModal()">✕</button>
        </div>
      </div>
      <iframe id="game-iframe" src="" style="width: 100%; height: 80vh; border: none; border-radius: 12px; background: #000;"></iframe>
    </div>
  </div>

  <!-- Modal Code Viewer -->
  <div class="modal-backdrop" id="code-modal" onclick="closeCodeModal(event)">
    <div class="modal-bottom-sheet" style="max-height: 88vh;" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h4 id="code-modal-title" style="font-size: 0.95rem; font-weight: 800;">Dosya İçeriği</h4>
        <button class="btn btn-outline" style="padding: 0.2rem 0.5rem;" onclick="closeCodeModal()">✕</button>
      </div>
      <pre id="code-modal-content" style="background: #050811; padding: 0.8rem; border-radius: 8px; font-size: 0.78rem; overflow: auto; max-height: 68vh; color: #cbd5e1; white-space: pre-wrap; font-family: monospace;"></pre>
    </div>
  </div>

  <div class="toast" id="toast">Bildirim</div>

  <script>
    let currentLogIndex = 0;
    let activeProjectData = {};

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 2600);
    }

    function switchNav(tabId, el) {
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      el.classList.add('active');

      if (tabId === 'tab-tasks' || tabId === 'tab-report' || tabId === 'tab-api') {
        refreshStatus();
      } else if (tabId === 'tab-logs') {
        fetchLogs();
      }
    }

    function handleKey(e) {
      if (e.key === 'Enter') sendChat();
    }

    async function loadProjects() {
      try {
        const res = await fetch('/api/projects');
        const data = await res.json();
        activeProjectData = data;
        const sel = document.getElementById('project-selector');
        sel.innerHTML = '';
        data.projects.forEach(p => {
          const opt = document.createElement('option');
          opt.value = p.path;
          opt.innerText = p.name + (p.taskCount ? ` (${p.taskCount}g)` : '');
          if (p.path === data.currentPath) {
            opt.selected = true;
          }
          sel.appendChild(opt);
        });

        // Header play button
        const btnPlay = document.getElementById('btn-header-play');
        const btnCardPlay = document.getElementById('btn-card-play');
        if (data.hasGame) {
          btnPlay.style.display = 'inline-flex';
          btnCardPlay.style.display = 'inline-block';
        } else {
          btnPlay.style.display = 'none';
          btnCardPlay.style.display = 'none';
        }
      } catch (e) {
        console.error("Failed to load projects", e);
      }
    }

    async function switchProject(path) {
      if (!path) return;
      showToast("Proje değiştiriliyor...");
      try {
        const res = await fetch('/api/projects/switch', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ path })
        });
        const data = await res.json();
        showToast(data.message || "Proje değiştirildi!");
        await loadProjects();
        await refreshStatus();
        await loadChat();
      } catch (e) {
        showToast("Proje değiştirilemedi.");
      }
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

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function formatMessageText(txt) {
      if (!txt) return '';
      // 1. Triple-backtick markdown code blocks
      txt = txt.replace(/```([a-zA-Z0-9_-]+)?\n([\\s\\S]*?)```/g, function(match, lang, code) {
        return `<div class="code-window">
          <div class="code-window-header">
            <span class="code-lang-tag">${lang || 'kod'}</span>
            <button class="mini-copy-btn" onclick="copyCode(this)">📋 Kopyala</button>
          </div>
          <pre class="code-snippet-box"><code>${escapeHtml(code.trim())}</code></pre>
        </div>`;
      });
      // 2. Formatting rules
      return txt
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.12);padding:0.15rem 0.35rem;border-radius:4px;font-size:0.86em;font-family:monospace;color:#38bdf8;">$1</code>')
        .split('\n').join('<br>');
    }

    function renderChatMessages(messages) {
      const box = document.getElementById('chat-messages');
      box.innerHTML = '';
      messages.forEach(m => {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${m.sender}`;
        
        let html = `<div>${formatMessageText(m.text)}</div>`;

        // Render code files & snippets if task milestone
        if (m.task && m.task.files && m.task.files.length > 0) {
          html += `<div style="margin-top: 0.6rem;">`;
          html += `<div style="font-size:0.75rem; font-weight:800; color:var(--muted); text-transform:uppercase; margin-bottom: 0.35rem;">📁 Kodlanan Dosyalar & Konumları:</div>`;
          m.task.files.forEach(f => {
            html += `
              <details class="code-accordion">
                <summary class="code-summary">
                  <div style="display:flex; align-items:center; gap:0.35rem; min-width:0; overflow:hidden;">
                    <span>📄</span>
                    <span style="font-weight:700; color:#38bdf8;">${f.path}</span>
                    <span style="font-size:0.7rem; color:var(--muted);">(${f.lines} satır)</span>
                  </div>
                  <button class="mini-copy-btn" onclick="event.stopPropagation(); copyCode(this)">📋 Kopyala</button>
                </summary>
                <pre class="code-snippet-box"><code>${escapeHtml(f.snippet)}</code></pre>
              </details>
            `;
          });
          html += `</div>`;
        }

        if (m.actions && m.actions.length > 0) {
          html += `<div class="bubble-actions">`;
          m.actions.forEach(a => {
            if (a.playProject) {
              html += `<button class="chip-btn" style="background: linear-gradient(135deg, #10b981, #059669); font-weight: 800;" onclick="openGameModal('/play/${a.playProject}', '${a.projectTitle || '🎮 Canlı Oyun'}')">${a.label}</button>`;
            } else if (a.prompt) {
              html += `<button class="chip-btn" onclick="sendCustomPrompt('${a.prompt}')">${a.label}</button>`;
            } else if (a.file) {
              html += `<button class="chip-btn" style="background: rgba(59, 130, 246, 0.25); border-color: var(--primary);" onclick="openFileModal('${a.file}')">${a.label}</button>`;
            } else if (a.action === 'step') {
              html += `<button class="chip-btn" style="background: var(--emerald);" onclick="executeStep()">${a.label}</button>`;
            } else if (a.action === 'run') {
              html += `<button class="chip-btn" style="background: var(--primary);" onclick="executeRun()">${a.label}</button>`;
            } else if (a.tab) {
              html += `<button class="chip-btn" onclick="switchNav('tab-${a.tab}', document.querySelectorAll('.nav-item')[${a.tab === 'tasks' ? 1 : (a.tab === 'logs' ? 2 : (a.tab === 'api' ? 3 : 4))}])">${a.label}</button>`;
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

      const box = document.getElementById('chat-messages');
      const uBubble = document.createElement('div');
      uBubble.className = 'chat-bubble user';
      uBubble.innerText = text;
      box.appendChild(uBubble);
      box.scrollTop = box.scrollHeight;

      showToast("Planlanıyor...");

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ message: text })
        });
        const data = await res.json();
        renderChatMessages(data.messages || []);
        refreshStatus();
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

        // Header status
        const st = data.state || {};
        const headerBadge = document.getElementById('header-status');
        const exec = data.execution || {};

        if (exec.isRunning) {
          headerBadge.innerText = `ÇALIŞIYOR (${exec.action})`;
          headerBadge.className = 'status-badge working';
        } else {
          headerBadge.innerText = st.status || 'HAZIR';
          headerBadge.className = 'status-badge';
        }

        // Pipeline Tab
        const prog = st.progress || 0;
        document.getElementById('pipeline-progress-text').innerText = `${prog}%`;
        document.getElementById('pipeline-progress-bar').style.width = `${prog}%`;

        renderTaskList(data.tasks || [], st.completedTasks || []);

        // Models
        if (data.config && data.config.models) {
          const m = data.config.models;
          document.getElementById('model-mappings').innerHTML = `
            <div><strong>Orchestrator:</strong> <code>${m.orchestrator.model}</code> (${m.orchestrator.provider})</div>
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
        box.innerHTML = '<div style="text-align: center; color: var(--muted); padding: 1.5rem;">Bu projede henüz görev yok. Sohbet sekmesinden yazılım isteğinde bulunabilirsin!</div>';
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

    function copyAllLogs() {
      const term = document.getElementById('terminal-box');
      if (!term) return;
      const text = term.innerText || '';
      navigator.clipboard.writeText(text).then(() => {
        showToast("Tüm loglar panoya kopyalandı! 📋");
      }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        showToast("Tüm loglar panoya kopyalandı! 📋");
      });
    }

    async function copyLastError() {
      try {
        const res = await fetch('/api/logs/diagnose');
        const diag = await res.json();
        let copyText = "";
        if (diag && diag.hasError) {
          copyText = `[RAMAZAN AI HATA TEŞHİSİ]\nTür: ${diag.errorType}\nNeden: ${diag.rootCause}\nÖneri: ${diag.recommendation}\nSnippet: ${diag.matchSnippet || ''}`;
        } else {
          const lines = (document.getElementById('terminal-box').innerText || '').split('\n');
          const errs = lines.filter(l => l.includes('[ERROR]') || l.includes('[WARNING]') || l.includes('FAIL') || l.includes('Traceback'));
          copyText = errs.slice(-30).join('\n') || lines.slice(-20).join('\n');
        }
        navigator.clipboard.writeText(copyText).then(() => {
          showToast("Hata teşhisi panoya kopyalandı! ⚠️");
        });
      } catch (e) {
        showToast("Hata kopyalanırken durum oluştu.");
      }
    }

    function copyCode(btn) {
      const container = btn.closest('.code-window, .code-accordion');
      const codeEl = container ? container.querySelector('code') : null;
      if (!codeEl) return;
      navigator.clipboard.writeText(codeEl.innerText).then(() => {
        const orig = btn.innerText;
        btn.innerText = "Kopyalandı! ✅";
        setTimeout(() => { btn.innerText = orig; }, 2000);
      });
    }

    async function updateDiagnosticCard() {
      try {
        const res = await fetch('/api/logs/diagnose');
        const diag = await res.json();
        const card = document.getElementById('error-diag-card');
        if (!card) return;
        if (diag && diag.hasError) {
          card.style.display = 'block';
          document.getElementById('diag-type').innerText = diag.errorType || 'Hata';
          document.getElementById('diag-cause').innerText = diag.rootCause || '';
          document.getElementById('diag-recommendation').innerText = `💡 Öneri: ${diag.recommendation || ''}`;
          const actBtn = document.getElementById('diag-action-btn');
          if (diag.suggestedCommand) {
            actBtn.style.display = 'inline-block';
            actBtn.innerText = `💡 ${diag.suggestedCommand}`;
            actBtn.onclick = () => {
              navigator.clipboard.writeText(diag.suggestedCommand);
              showToast(`Komut kopyalandı: ${diag.suggestedCommand}`);
            };
          } else {
            actBtn.style.display = 'none';
          }
        } else {
          card.style.display = 'none';
        }
      } catch (e) {}
    }

    async function fetchLogs() {
      try {
        const res = await fetch(`/api/logs?since=${currentLogIndex}`);
        const data = await res.json();
        const term = document.getElementById('terminal-box');

        if (currentLogIndex === 0 && data.logs.length === 0) {
          term.innerHTML = '<div style="color: var(--muted);">Henüz terminal logu kaydedilmedi.</div>';
          return;
        }

        if (currentLogIndex === 0) {
          term.innerHTML = '';
        }

        if (data.logs && data.logs.length > 0) {
          data.logs.forEach(l => {
            const div = document.createElement('div');
            div.className = `log-entry log-${l.level}`;
            div.innerHTML = `<span class="log-time">[${l.time}]</span> <span style="font-weight:700;">[${l.level}]</span> ${l.message}`;
            term.appendChild(div);
          });
          currentLogIndex = data.total;
          term.scrollTop = term.scrollHeight;
          updateDiagnosticCard();
        }
        document.getElementById('log-count-badge').innerText = data.total;
      } catch (e) {
        console.error(e);
      }
    }

    async function clearLogsUI() {
      try {
        await fetch('/api/logs/clear', { method: 'POST' });
        currentLogIndex = 0;
        document.getElementById('terminal-box').innerHTML = '<div style="color: var(--muted);">Loglar temizlendi.</div>';
        document.getElementById('log-count-badge').innerText = '0';
      } catch (e) {}
    }

    async function executeStep() {
      showToast("Adım yürütülüyor...");
      try {
        const res = await fetch('/api/step', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "İşlem başlatıldı!");
        refreshStatus();
        fetchLogs();
      } catch (e) {
        showToast("Hata oluştu.");
      }
    }

    async function executeRun() {
      showToast("Otonom pipeline başlatıldı...");
      try {
        const res = await fetch('/api/run', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || "Pipeline başlatıldı!");
        refreshStatus();
        fetchLogs();
      } catch (e) {
        showToast("Hata oluştu.");
      }
    }

    async function runTestButton() {
      showToast("Testler koşuluyor...");
      try {
        const res = await fetch('/api/test', { method: 'POST' });
        const data = await res.json();
        showToast(data.passed ? "✅ Testler Başarılı!" : "❌ Testler Başarısız");
        refreshStatus();
        fetchLogs();
      } catch (e) {
        showToast("Test motoru hatası!");
      }
    }

    async function runAuditButton() {
      showToast("Final Audit denetleniyor...");
      try {
        await fetch('/api/audit', { method: 'POST' });
        showToast("Audit tamamlandı!");
        refreshStatus();
        fetchLogs();
      } catch (e) {
        showToast("Audit hatası!");
      }
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
            <pre style="background: #050811; padding: 0.5rem; border-radius: 6px; font-size: 0.75rem; max-height: 140px; overflow: auto; margin-top: 0.4rem;">${data.escalation}</pre>
            <button class="btn btn-emerald btn-block" style="margin-top: 0.6rem;" onclick="resetTask('${t.id}')">🔄 Görevi Sıfırla (Reset to READY)</button>
          </div>`;
        }
        if (data.memory) {
          html += `<div style="margin-top: 0.8rem;"><strong>Hafıza Kaydı:</strong><pre style="background: #050811; padding: 0.5rem; border-radius: 6px; font-size: 0.75rem; max-height: 140px; overflow: auto;">${data.memory}</pre></div>`;
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

    function openGameModal(url, title) {
      const modal = document.getElementById('game-modal');
      const iframe = document.getElementById('game-iframe');
      const titleEl = document.getElementById('game-modal-title');
      const linkEl = document.getElementById('game-modal-link');

      const targetUrl = url || (activeProjectData.gameUrl || '/play');
      const targetTitle = title || '🎮 Canlı Oyun / Web Önizleme';

      if (titleEl) titleEl.innerText = targetTitle;
      if (linkEl) linkEl.href = targetUrl;
      iframe.src = targetUrl;
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
        const res = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        document.getElementById('code-modal-title').innerText = filePath;
        document.getElementById('code-modal-content').innerText = data.content || "";
        document.getElementById('code-modal').style.display = 'flex';
      } catch (e) {
        window.open(`/preview/${filePath}`, '_blank');
      }
    }

    function closeCodeModal() {
      document.getElementById('code-modal').style.display = 'none';
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

    // Initialize Dashboard
    loadProjects();
    loadChat();
    refreshStatus();
    fetchLogs();

    // Polling for live status, background logs, and chat milestones
    setInterval(() => {
      refreshStatus();
      fetchLogs();
      loadChat();
    }, 2800);
  </script>
</body>
</html>
"""
