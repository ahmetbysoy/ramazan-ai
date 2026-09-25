"""
Safe File System operations, Sandboxing, File Locking, and Rollback Snapshots for RAMAZAN AI.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import os
import re


class SandboxError(Exception):
    pass


class FileLockException(Exception):
    pass


@dataclass
class CodeMatch:
    path: str
    line: int
    text: str


class FileLockManager:
    """
    Implements Section 25: Code Ownership & File Locking.
    Ensures no two workers touch the same file concurrently.
    """
    def __init__(self):
        self._locks: Dict[str, str] = {}  # filepath -> taskId

    def acquire_locks(self, task_id: str, files: List[str]) -> bool:
        for file in files:
            norm = os.path.normpath(file)
            if norm in self._locks and self._locks[norm] != task_id:
                raise FileLockException(
                    f"File '{norm}' is locked by task '{self._locks[norm]}'. Task '{task_id}' cannot proceed."
                )
        for file in files:
            norm = os.path.normpath(file)
            self._locks[norm] = task_id
        return True

    def release_locks(self, task_id: str):
        keys_to_remove = [k for k, v in self._locks.items() if v == task_id]
        for k in keys_to_remove:
            del self._locks[k]

    def is_locked(self, file: str) -> Optional[str]:
        return self._locks.get(os.path.normpath(file))


# Global file lock manager instance
global_file_locks = FileLockManager()


class SnapshotManager:
    """
    Implements Section 27: Rollback and Atomic File Snapshotting.
    Ensures that only files touched by an agent are restored on failure,
    preserving human edits and unaffected files.
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()

    def create_snapshot(self, files: List[str]) -> Dict[str, Optional[str]]:
        snapshot: Dict[str, Optional[str]] = {}
        for f in files:
            p = (self.root_dir / f).resolve()
            if p.exists() and p.is_file():
                try:
                    snapshot[f] = p.read_text(encoding="utf-8")
                except Exception:
                    snapshot[f] = None
            else:
                snapshot[f] = None
        return snapshot

    def restore_snapshot(self, snapshot: Dict[str, Optional[str]]) -> None:
        for f, content in snapshot.items():
            p = (self.root_dir / f).resolve()
            if content is None:
                if p.exists():
                    p.unlink()
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")


class FileSystemTools:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.snapshots = SnapshotManager(self.root_dir)

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            resolved = (self.root_dir / p).resolve()
        else:
            resolved = p.resolve()

        # Strict sandbox validation: prohibit escaping project root
        if resolved != self.root_dir and self.root_dir not in resolved.parents:
            raise SandboxError(f"Path escapes project root: {path}")
        return resolved

    def read_file(self, path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if offset is not None:
            start = max(0, offset - 1)
            end = start + limit if limit is not None else len(lines)
            return "".join(lines[start:end])
        elif limit is not None:
            return "".join(lines[:limit])
        return "".join(lines)

    def write_file(self, path: str, content: str) -> bool:
        resolved = self._resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def delete_file(self, path: str) -> bool:
        resolved = self._resolve(path)
        if resolved.exists():
            resolved.unlink()
            return True
        return False

    def edit_file(self, path: str, old_text: str, new_text: str) -> bool:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            raise ValueError(f"Target text not found in {path}")
        content = content.replace(old_text, new_text, 1)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def search_code(self, pattern: str, glob_pattern: str = "**/*") -> List[CodeMatch]:
        rx = re.compile(pattern)
        matches: List[CodeMatch] = []
        ignored_dirs = {".ramazan", ".git", "__pycache__", "node_modules", ".venv"}
        for p in self.root_dir.glob(glob_pattern):
            if not p.is_file() or ignored_dirs & set(p.parts):
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                for i, line in enumerate(lines, 1):
                    if rx.search(line):
                        rel_path = str(p.relative_to(self.root_dir))
                        matches.append(CodeMatch(path=rel_path, line=i, text=line.strip()))
            except Exception:
                continue
        return matches

    def list_dir(self, path: str = ".") -> List[str]:
        resolved = self._resolve(path)
        if not resolved.exists():
            return []
        return [str(p.relative_to(self.root_dir)) for p in resolved.iterdir()]

    def file_exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except SandboxError:
            return False
