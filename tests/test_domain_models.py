import pytest
from src.domain.models import EntityModel

def test_entity_model_creation():
    entity = EntityModel(id="E-001", name="Test Entity")
    assert entity.id == "E-001"
    assert entity.is_active() is True
    assert entity.status == "ACTIVE"

def test_entity_inactive():
    entity = EntityModel(id="E-002", name="Inactive", status="ARCHIVED")
    assert entity.is_active() is False
