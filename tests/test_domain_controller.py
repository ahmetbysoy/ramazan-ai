import pytest
from src.domain.service import EntityService, InMemoryEntityRepository
from src.domain.controller import DomainController


def test_domain_controller_health_and_ops():
    repo = InMemoryEntityRepository()
    service = EntityService(repo)
    controller = DomainController(service)

    health = controller.health_check()
    assert health["status"] == "UP"

    created = controller.create_entity({"id": "ctrl-1", "name": "Controller Item"})
    assert created["id"] == "ctrl-1"
    assert created["status"] == "ACTIVE"

    fetched = controller.get_entity("ctrl-1")
    assert fetched["id"] == "ctrl-1"

    all_items = controller.list_entities()
    assert len(all_items) == 1
