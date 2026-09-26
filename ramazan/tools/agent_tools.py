"""
Agent Tools and Tool Dispatcher for RAMAZAN AI.
Provides multi-turn tool calling definitions and execution for Worker agent.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ramazan.tools.patch_engine import apply_patch_to_text
from ramazan.tools.fs import FileSystemTools

logger = logging.getLogger("ramazan.agent_tools")


def is_test_path(path: str) -> bool:
    p = path.lower()
    return "test" in p or p.startswith("tests/") or p.endswith("_test.py") or "test_" in p


AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content of a file with optional line range. Use this to inspect existing source code or tests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path from project root."},
                    "start_line": {"type": "integer", "description": "1-based starting line number (optional)."},
                    "end_line": {"type": "integer", "description": "1-based ending line number (optional)."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List directory contents including files and subdirectories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path (default: '.')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or completely overwrite a file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to write."},
                    "content": {"type": "string", "description": "Full file content to write."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Apply a unified diff or search/replace hunk to modify an existing file minimally without rewriting everything.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to patch."},
                    "diff": {"type": "string", "description": "Unified diff or search/replace block."}
                },
                "required": ["path", "diff"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a safe shell command in the project directory (e.g. syntax checks, builds).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the project test suite or a specific test file using pytest/configured test command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional specific test file or directory to run."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "View git diff of current uncommitted changes to inspect modifications.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


class AgentToolDispatcher:
    def __init__(
        self,
        root_dir: Path,
        allowed_files: Optional[List[str]] = None,
        strict_scope: bool = True
    ):
        self.root_dir = root_dir.resolve()
        self.allowed_files = [str(f).replace("\\", "/") for f in (allowed_files or [])]
        self.strict_scope = strict_scope
        self.fs = FileSystemTools(self.root_dir)
        self.modified_files: List[str] = []
        self.test_files: List[str] = []

    def _resolve_safe_path(self, rel_path: str) -> Path:
        target = (self.root_dir / rel_path).resolve()
        if not str(target).startswith(str(self.root_dir)):
            raise ValueError(f"Path traversal detected: {rel_path} outside root {self.root_dir}")
        return target

    def _check_scope(self, rel_path: str) -> Tuple[bool, str]:
        if not self.strict_scope or not self.allowed_files:
            return True, ""
        norm_path = rel_path.replace("\\", "/").lstrip("./")
        if norm_path in self.allowed_files or is_test_path(norm_path):
            return True, ""
        # Check subpath
        for af in self.allowed_files:
            if norm_path.startswith(af.rstrip("/") + "/"):
                return True, ""
        return False, f"Scope Violation: '{norm_path}' is not within task scope {self.allowed_files} (tests are also allowed)."

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Executes named tool with dictionary arguments and returns string response.
        """
        try:
            if tool_name == "read_file":
                return self._tool_read_file(args.get("path", ""), args.get("start_line"), args.get("end_line"))
            elif tool_name == "list_dir":
                return self._tool_list_dir(args.get("path", "."))
            elif tool_name == "write_file":
                return self._tool_write_file(args.get("path", ""), args.get("content", ""))
            elif tool_name == "apply_patch":
                return self._tool_apply_patch(args.get("path", ""), args.get("diff", ""))
            elif tool_name == "run_command":
                return self._tool_run_command(args.get("command", ""))
            elif tool_name == "run_tests":
                return self._tool_run_tests(args.get("path"))
            elif tool_name == "git_diff":
                return self._tool_git_diff()
            else:
                return f"Error: Unknown tool '{tool_name}'."
        except Exception as e:
            logger.error(f"Error executing {tool_name} with args {args}: {e}")
            return f"Error executing {tool_name}: {e}"

    def _tool_read_file(self, rel_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        if not rel_path:
            return "Error: 'path' argument is required."
        target = self._resolve_safe_path(rel_path)
        if not target.exists() or not target.is_file():
            return f"Error: File '{rel_path}' does not exist."

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)
            if start_line is not None or end_line is not None:
                s = max(1, start_line or 1)
                e = min(total_lines, end_line or total_lines)
                selected = lines[s - 1 : e]
                numbered = [f"{i}: {line}" for i, line in enumerate(selected, start=s)]
                return f"[Showing lines {s}-{e} of {total_lines} in {rel_path}]\n" + "\n".join(numbered)
            else:
                return content
        except Exception as e:
            return f"Error reading file '{rel_path}': {e}"

    def _tool_list_dir(self, rel_path: str = ".") -> str:
        target = self._resolve_safe_path(rel_path)
        if not target.exists() or not target.is_dir():
            return f"Error: Directory '{rel_path}' does not exist."

        entries = []
        for item in sorted(target.iterdir()):
            if item.name.startswith(".ramazan") or item.name in [".git", "__pycache__", ".pytest_cache", ".venv"]:
                continue
            item_type = "DIR" if item.is_dir() else "FILE"
            entries.append(f"{item_type:4} {item.name}")
        return f"Directory listing of '{rel_path}':\n" + ("\n".join(entries) if entries else "(empty)")

    def _tool_write_file(self, rel_path: str, content: str) -> str:
        if not rel_path:
            return "Error: 'path' argument is required."
        ok, scope_err = self._check_scope(rel_path)
        if not ok:
            return f"Error: {scope_err}"

        target = self._resolve_safe_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        norm = str(target.relative_to(self.root_dir)).replace("\\", "/")
        if is_test_path(norm):
            if norm not in self.test_files:
                self.test_files.append(norm)
        else:
            if norm not in self.modified_files:
                self.modified_files.append(norm)

        lines_count = len(content.splitlines())
        return f"Successfully wrote {lines_count} lines to {norm}."

    def _tool_apply_patch(self, rel_path: str, diff: str) -> str:
        if not rel_path or not diff:
            return "Error: 'path' and 'diff' arguments are required."
        ok, scope_err = self._check_scope(rel_path)
        if not ok:
            return f"Error: {scope_err}"

        target = self._resolve_safe_path(rel_path)
        if not target.exists():
            return f"Error: File '{rel_path}' does not exist to patch. Use write_file to create new files."

        orig_text = target.read_text(encoding="utf-8", errors="replace")
        success, new_text, msg = apply_patch_to_text(orig_text, diff)
        if not success:
            return f"Error: {msg}"

        target.write_text(new_text, encoding="utf-8")
        norm = str(target.relative_to(self.root_dir)).replace("\\", "/")
        if is_test_path(norm):
            if norm not in self.test_files:
                self.test_files.append(norm)
        else:
            if norm not in self.modified_files:
                self.modified_files.append(norm)

        return f"Patch successful: {msg} for {norm}."

    def _tool_run_command(self, command: str) -> str:
        if not command or not command.strip():
            return "Error: 'command' argument is required."
        # Disallow dangerous operations
        forbidden = ["rm -rf /", ":(){ :|:& };:", "mkfs", "dd if="]
        for f in forbidden:
            if f in command:
                return f"Error: Command rejected for safety reasons ({f})."

        try:
            res = subprocess.run(
                command,
                cwd=str(self.root_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=45
            )
            out = []
            if res.stdout:
                out.append(f"STDOUT:\n{res.stdout}")
            if res.stderr:
                out.append(f"STDERR:\n{res.stderr}")
            ret = f"Exit code: {res.returncode}\n" + ("\n".join(out) if out else "(no output)")
            return ret[:4000]
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 45 seconds."
        except Exception as e:
            return f"Error running command: {e}"

    def _tool_run_tests(self, path: Optional[str] = None) -> str:
        from ramazan.tools.test_runner import TestEngine
        engine = TestEngine(self.root_dir)
        res = engine.run_tests(path=path)
        status = "PASSED" if res.passed else "FAILED"
        return f"Test Run {status} (Exit: {res.exitCode}, Duration: {res.duration:.2f}s)\n{res.summary}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"[:4000]

    def _tool_git_diff(self) -> str:
        from ramazan.tools.git_manager import GitManager
        gm = GitManager(self.root_dir)
        diff = gm.diff_for_task(files=self.allowed_files)
        return diff if diff.strip() else "(No git changes detected)"
