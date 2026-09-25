import pytest
from ramazan.core.router import ModelRouter
from ramazan.config import RamazanConfig
from ramazan.schemas.task import Task


def test_model_router_by_complexity():
    config = RamazanConfig()
    router = ModelRouter(config)

    # Low complexity -> cheap model
    task_low = Task(id="TASK-LOW", title="Docs", description="Docs", complexity="low")
    model_low = router.route_task(task_low)
    assert model_low.model == config.models.worker.low.model

    # High complexity -> high tier model
    task_high = Task(id="TASK-HIGH", title="Security", description="Security", complexity="high")
    model_high = router.route_task(task_high)
    assert model_high.model == config.models.worker.high.model

    # Retries >= 2 -> escalates to critical model
    task_retry = Task(id="TASK-RETRY", title="Bug", description="Bug", complexity="low", retryCount=2)
    model_escalated = router.route_task(task_retry)
    assert model_escalated.model == config.models.worker.critical.model
