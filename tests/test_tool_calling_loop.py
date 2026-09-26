"""
Unit tests for Agent Tool Calling Loop and Dispatcher (FAZ 2.1).
"""

from pathlib import Path
from ramazan.tools.agent_tools import AgentToolDispatcher, AGENT_TOOLS_SCHEMA
from ramazan.tools.patch_engine import apply_patch_to_text
from ramazan.schemas.task import Task
from ramazan.agents.worker_agent import WorkerAgent
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient, LLMResponse


def test_patch_engine_unified_and_search_replace():
    orig = "line 1\nline 2\nline 3\n"
    # Unified diff
    patch = "@@ -1,3 +1,3 @@\n line 1\n-line 2\n+line two modified\n line 3\n"
    ok, new_t, msg = apply_patch_to_text(orig, patch)
    assert ok is True
    assert "line two modified" in new_t

    # Search / Replace
    sr_patch = "<<<<<<< SEARCH\nline 3\n=======\nline 3 updated\n>>>>>>> REPLACE"
    ok2, new_t2, msg2 = apply_patch_to_text(new_t, sr_patch)
    assert ok2 is True
    assert "line 3 updated" in new_t2


def test_agent_tool_dispatcher_crud_and_scope(tmp_path: Path):
    allowed = ["src/service.py"]
    dispatcher = AgentToolDispatcher(root_dir=tmp_path, allowed_files=allowed, strict_scope=True)

    # 1. write_file in scope
    res = dispatcher.execute_tool("write_file", {"path": "src/service.py", "content": "def run():\n    return 42\n"})
    assert "Successfully wrote" in res
    assert (tmp_path / "src" / "service.py").read_text() == "def run():\n    return 42\n"

    # 2. read_file
    read_res = dispatcher.execute_tool("read_file", {"path": "src/service.py"})
    assert "return 42" in read_res

    # 3. list_dir
    list_res = dispatcher.execute_tool("list_dir", {"path": "src"})
    assert "service.py" in list_res

    # 4. apply_patch
    patch = "<<<<<<< SEARCH\n    return 42\n=======\n    return 100\n>>>>>>> REPLACE"
    patch_res = dispatcher.execute_tool("apply_patch", {"path": "src/service.py", "diff": patch})
    assert "Patch successful" in patch_res
    assert (tmp_path / "src" / "service.py").read_text() == "def run():\n    return 100\n"

    # 5. write_file outside scope -> rejected
    viol_res = dispatcher.execute_tool("write_file", {"path": "secret/config.py", "content": "bad"})
    assert "Scope Violation" in viol_res
    assert not (tmp_path / "secret" / "config.py").exists()

    # 6. write_file to tests/ allowed by default
    test_res = dispatcher.execute_tool("write_file", {"path": "tests/test_service.py", "content": "def test_run(): pass\n"})
    assert "Successfully wrote" in test_res


def test_worker_agent_multi_turn_tool_execution(tmp_path: Path):
    task = Task(
        id="TASK-010",
        title="Implement Calculator",
        description="Write calculator operations",
        type="implementation",
        status="PENDING",
        dependencies=[],
        files=["src/calc.py"],
        acceptanceCriteria=["add function implemented"]
    )

    class MockToolLLMClient(LLMClient):
        def __init__(self):
            super().__init__(use_mock=False)
            self.turn_count = 0

        def generate_with_tools(self, model, messages, tools=None, temperature=0.2):
            self.turn_count += 1
            if self.turn_count == 1:
                # First turn: call write_file tool
                return LLMResponse(
                    content="Writing implementation and test",
                    model=model,
                    tool_calls=[
                        {
                            "id": "call_write_1",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path": "src/calc.py", "content": "def add(a, b): return a + b\\n"}'
                            }
                        },
                        {
                            "id": "call_write_2",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": '{"path": "tests/test_calc.py", "content": "from src.calc import add\\ndef test_add(): assert add(1, 2) == 3\\n"}'
                            }
                        }
                    ]
                )
            else:
                # Second turn: finished
                return LLMResponse(
                    content="Completed calculator implementation and verified tests.",
                    model=model,
                    tool_calls=None
                )

    mock_client = MockToolLLMClient()
    worker = WorkerAgent(
        model_config=ModelConfig(model="mock-worker", provider="openai"),
        root_dir=tmp_path,
        llm_client=mock_client
    )

    out = worker.execute_task(task=task, context_prompt="Please implement calc", strict_scope=True)
    assert len(out.fileModifications) == 1
    assert out.fileModifications[0].path == "src/calc.py"
    assert "def add" in out.fileModifications[0].content
    assert (tmp_path / "src" / "calc.py").exists()
    assert (tmp_path / "tests" / "test_calc.py").exists()
