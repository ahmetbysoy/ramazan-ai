import pytest
from src.domain.service import EntityService, InMemoryEntityRepository


def test_entity_service_crud():
    repo = InMemoryEntityRepository()
    service = EntityService(repo)

    entity = service.create_entity("e-1", "Test Item", {"tag": "prod"})
    assert entity.id == "e-1"
    assert entity.name == "Test Item"
    assert entity.is_active() is True

    fetched = service.get_entity("e-1")
    assert fetched == entity

    active_list = service.list_active_entities()
    assert len(active_list) == 1
    assert active_list[0].id == "e-1"
