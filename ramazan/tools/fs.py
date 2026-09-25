"""
Safe File System operations and File Locking for RAMAZAN AI.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import os


class FileLockException(Exception):
    pass


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


class FileSystemTools:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = (self.root_dir / p).resolve()
        # Security sanity check: prevent escaping outside reasonable directory bounds if desired
        return p

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

    def list_dir(self, path: str = ".") -> List[str]:
        resolved = self._resolve(path)
        if not resolved.exists():
            return []
        return [str(p.relative_to(self.root_dir)) for p in resolved.iterdir()]

    def file_exists(self, path: str) -> bool:
        return self._resolve(path).exists()
