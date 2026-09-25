"""
Context Builder for RAMAZAN AI.
Conforms to Sections 14 & 34 of specification.
Assembles surgical context:
GLOBAL CONTEXT + ARCHITECTURE + RELEVANT TASK + RELEVANT FILES + DEPENDENCY MEMORIES + TEST RESULTS + REVIEW FEEDBACK
"""

from pathlib import Path
from typing import Dict, List, Optional
from ramazan.schemas.task import Task
from ramazan.tools.fs import FileSystemTools


class ContextBuilder:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.fs = FileSystemTools(self.root_dir)

    def load_architecture_rules(self) -> str:
        arch_file = self.root_dir / ".ramazan" / "architecture.md"
        if arch_file.exists():
            return self.fs.read_file(".ramazan/architecture.md")
        return "Standard clean code, modular architecture, full test coverage required."

    def load_task_memories(self, dependency_ids: List[str]) -> str:
        memories = []
        memory_dir = self.root_dir / ".ramazan" / "memory"
        for dep_id in dependency_ids:
            mem_file = memory_dir / f"{dep_id}.md"
            if mem_file.exists():
                try:
                    content = self.fs.read_file(str(mem_file.relative_to(self.root_dir)))
                    memories.append(f"--- Memory from Prerequisite {dep_id} ---\n{content}")
                except Exception:
                    pass
        if not memories:
            return "No previous dependency memories available."
        return "\n\n".join(memories)

    def load_relevant_files(self, file_paths: List[str]) -> Dict[str, str]:
        files_content = {}
        for f in file_paths:
            try:
                if self.fs.file_exists(f):
                    content = self.fs.read_file(f, limit=500)
                    files_content[f] = content
                else:
                    files_content[f] = "[FILE DOES NOT EXIST YET - TO BE CREATED]"
            except Exception as e:
                files_content[f] = f"[ERROR READING FILE: {e}]"
        return files_content

    def build_worker_prompt(self, task: Task, test_failure: Optional[str] = None, review_feedback: Optional[str] = None) -> str:
        """
        Builds Worker prompt matching Section 34 exact standard.
        """
        arch = self.load_architecture_rules()
        dep_memories = self.load_task_memories(task.dependencies)
        files = self.load_relevant_files(task.files)

        files_formatted = "\n\n".join([f"### File: {path}\n```\n{content}\n```" for path, content in files.items()])
        criteria_formatted = "\n".join([f"- {c}" for c in task.acceptanceCriteria])

        prompt = f"""ROLE: You are a senior software engineer.
PROJECT: Autonomous Software Engineering Task Execution
ARCHITECTURE:
{arch}

TASK:
ID: {task.id}
Title: {task.title}
Description: {task.description}
Complexity: {task.complexity}
Priority: {task.priority}

FILES:
{files_formatted}

CONSTRAINTS:
1. Only modify files listed in target files: {', '.join(task.files) if task.files else 'Specified in task'}.
2. Comply strictly with architecture rules.
3. Write clean, robust, and verifiable code.
4. Include unit tests or test updates for all new/modified logic.

ACCEPTANCE CRITERIA:
{criteria_formatted}

PREVIOUS DEPENDENCIES MEMORY:
{dep_memories}

TEST FAILURE:
{test_failure if test_failure else 'None. Clean baseline.'}

REVIEW FEEDBACK:
{review_feedback if review_feedback else 'None.'}

REQUIRED OUTPUT FORMAT:
You MUST respond with a valid JSON object containing:
{{
  "explanation": "Brief explanation of implementation",
  "fileModifications": [
    {{
      "path": "path/to/file.py",
      "content": "Full new file content or precise replacement"
    }}
  ],
  "tests": [
    {{
      "path": "tests/test_file.py",
      "content": "Full test code"
    }}
  ],
  "potentialRisks": "Analysis of edge cases or risks"
}}
"""
        return prompt

    def build_reviewer_prompt(self, task: Task, changes_summary: str, test_output: str) -> str:
        """
        Builds Reviewer prompt matching Section 18 review protocol.
        """
        arch = self.load_architecture_rules()
        files = self.load_relevant_files(task.files)
        files_formatted = "\n\n".join([f"### File: {path}\n```\n{content}\n```" for path, content in files.items()])

        prompt = f"""ROLE: You are an expert code reviewer. Your job is NOT to write code or compliment the worker.
Your job is to rigorously identify defects, architectural violations, security holes, performance issues, missing tests, and unhandled edge cases.

ARCHITECTURE RULES:
{arch}

TASK UNDER REVIEW:
ID: {task.id}
Title: {task.title}
Description: {task.description}
Acceptance Criteria:
{chr(10).join([f"- {c}" for c in task.acceptanceCriteria])}

CODE CHANGES & RELEVANT FILES:
{files_formatted}

CHANGES SUMMARY:
{changes_summary}

OBJECTIVE TEST OUTPUT (Test Engine Result):
{test_output}

INSPECTION CHECKLIST:
1. Correctness: Does the implementation satisfy all acceptance criteria?
2. Security: Secrets, injection, insecure storage, permissions?
3. Architecture: Are module boundaries and architecture rules respected?
4. Edge Cases: Empty inputs, boundary values, exception handling?
5. Testing: Are test cases comprehensive and genuine?

REQUIRED OUTPUT:
You MUST reply with a JSON object conforming strictly to:
{{
  "status": "APPROVED" | "CHANGES_REQUIRED",
  "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "summary": "High level assessment",
  "issues": [
    {{
      "file": "path/to/file.py",
      "line": 12,
      "category": "security | correctness | architecture | edge_cases | performance | testing",
      "description": "Clear problem description with evidence",
      "requiredFix": "Concrete instruction on what must be changed"
    }}
  ]
}}
If there are any breaking issues or failed acceptance criteria, status MUST be CHANGES_REQUIRED.
Only output APPROVED if code is completely verified and free of defects.
"""
        return prompt
