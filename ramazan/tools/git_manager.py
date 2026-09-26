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
                git_dir = self.repo_dir / ".git"
                if git_dir.exists():
                    self._repo = git.Repo(self.repo_dir)
                else:
                    self._repo = git.Repo(self.repo_dir, search_parent_directories=True)
            except git.InvalidGitRepositoryError:
                self._repo = None
        return self._repo

    def init_if_needed(self) -> bool:
        git_dir = self.repo_dir / ".git"
        if git_dir.exists():
            return True
        if HAS_GITPYTHON and git is not None:
            try:
                self._repo = git.Repo.init(self.repo_dir)
                logger.info(f"Initialized new Git repository at {self.repo_dir}")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize git repository: {e}")
        try:
            import subprocess
            subprocess.run(["git", "init"], cwd=str(self.repo_dir), check=True, capture_output=True)
            return True
        except Exception:
            return False

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

    def diff_for_task(self, files: Optional[List[str]] = None, base_ref: str = "HEAD") -> str:
        """
        Returns unified diff for working tree changes or specific task files against base_ref.
        Includes newly added untracked files with intent-to-add.
        """
        repo = self.get_repo()
        if repo:
            try:
                untracked = getattr(repo, "untracked_files", [])
                for f in (files or untracked):
                    if f in untracked and not f.startswith(".ramazan"):
                        try:
                            repo.git.add("-N", f)
                        except Exception:
                            pass
                if files:
                    valid_files = [f for f in files if (self.repo_dir / f).exists()]
                    if valid_files:
                        diff = repo.git.diff(base_ref, "--", *valid_files)
                        if diff.strip():
                            return diff
                        return repo.git.diff("--cached", "--", *valid_files)
                diff = repo.git.diff(base_ref)
                if not diff.strip():
                    diff = repo.git.diff("--cached")
                return diff
            except Exception:
                try:
                    return repo.git.diff()
                except Exception:
                    pass

        # Subprocess git fallback
        try:
            import subprocess
            if files:
                for f in files:
                    subprocess.run(["git", "add", "-N", f], cwd=str(self.repo_dir), capture_output=True)
                valid = [f for f in files if (self.repo_dir / f).exists()]
                if valid:
                    res = subprocess.run(["git", "diff", base_ref, "--"] + valid, cwd=str(self.repo_dir), capture_output=True, text=True)
                    if res.stdout.strip():
                        return res.stdout
            res = subprocess.run(["git", "diff", base_ref], cwd=str(self.repo_dir), capture_output=True, text=True)
            if not res.stdout.strip():
                res = subprocess.run(["git", "diff"], cwd=str(self.repo_dir), capture_output=True, text=True)
            return res.stdout
        except Exception:
            return ""

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

    def push(self, remote_name: str = "origin", branch: Optional[str] = None) -> bool:
        """
        Pushes current commits to remote repository (e.g. GitHub).
        """
        repo = self.get_repo()
        if not repo:
            return False
        try:
            cur_branch = branch or (repo.active_branch.name if not repo.head.is_detached else "main")
            # Check if remote exists
            if remote_name not in [r.name for r in repo.remotes]:
                logger.info(f"Remote '{remote_name}' not configured. Skipping git push.")
                return False
            repo.git.push(remote_name, cur_branch)
            logger.info(f"Auto-pushed {cur_branch} to {remote_name} successfully.")
            return True
        except Exception as e:
            logger.warning(f"Git push to {remote_name} skipped/failed: {e}")
            return False

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
