"""
Git management and rollback functionality for RAMAZAN AI.
Conforms to Sections 26 & 27 of specification.
"""

import logging
from pathlib import Path
from typing import List, Optional

try:
    import git
    HAS_GITPYTHON = True
except ImportError:
    git = None
    HAS_GITPYTHON = False

logger = logging.getLogger("ramazan.git")


class GitManager:
    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = (repo_dir or Path.cwd()).resolve()
        self._repo: Optional[object] = None

    def get_repo(self) -> Optional[object]:
        if not HAS_GITPYTHON or git is None:
            return None
        if self._repo is None:
            try:
                self._repo = git.Repo(self.repo_dir, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                self._repo = None
        return self._repo

    def init_if_needed(self) -> bool:
        if not HAS_GITPYTHON or git is None:
            return False
        if self.get_repo() is None:
            try:
                self._repo = git.Repo.init(self.repo_dir)
                logger.info(f"Initialized new Git repository at {self.repo_dir}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize git repository: {e}")
                return False
        return True

    def get_status(self) -> str:
        repo = self.get_repo()
        if not repo:
            return "Not a git repository."
        return repo.git.status()

    def get_diff(self) -> str:
        repo = self.get_repo()
        if not repo:
            return ""
        return repo.git.diff()

    def commit_task(self, task_id: str, title: str, task_type: str = "implementation", files: Optional[List[str]] = None) -> Optional[str]:
        repo = self.get_repo()
        if not repo:
            logger.warning("No Git repository found. Skipping commit.")
            return None

        prefix = "feat"
        t_type = task_type.lower()
        if "test" in t_type:
            prefix = "test"
        elif "fix" in t_type:
            prefix = "fix"
        elif "refactor" in t_type:
            prefix = "refactor"
        elif "doc" in t_type:
            prefix = "docs"
        elif "arch" in t_type:
            prefix = "chore"

        commit_message = f"{prefix}: [{task_id}] {title}"

        try:
            # Stage changed files and .ramazan tracking files
            if files:
                for f in files:
                    full_p = self.repo_dir / f
                    if full_p.exists():
                        repo.git.add(f)
            else:
                repo.git.add("-A")

            # Always stage .ramazan updates
            if (self.repo_dir / ".ramazan").exists():
                repo.git.add(".ramazan")

            diff = repo.git.diff("--cached")
            if not diff.strip():
                logger.info("No staged changes to commit.")
                return None

            commit = repo.index.commit(commit_message)
            logger.info(f"Committed {task_id}: {commit.hexsha[:8]} - {commit_message}")
            return commit.hexsha
        except Exception as e:
            logger.error(f"Git commit failed: {e}")
            return None

    def rollback(self, files: Optional[List[str]] = None) -> bool:
        """
        Rolls back uncommitted changes. Does not wipe untracked files without confirmation.
        """
        repo = self.get_repo()
        if not repo:
            return False
        try:
            if files:
                for f in files:
                    try:
                        repo.git.checkout("HEAD", "--", f)
                    except Exception:
                        pass
            else:
                repo.git.checkout("HEAD", "--", ".")
            logger.warning("Rolled back uncommitted changes.")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
