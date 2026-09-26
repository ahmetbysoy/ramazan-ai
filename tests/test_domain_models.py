import pytest
from pydantic import ValidationError
from src.domain.models import EntityModel

def test_entity_model_creation():
    entity = EntityModel(id="E-001", name="Test Entity")
    assert entity.id == "E-001"
    assert entity.name == "Test Entity"
    assert entity.is_active() is True
    assert entity.status == "ACTIVE"
    assert entity.metadata == {}

def test_entity_inactive():
    entity = EntityModel(id="E-002", name="Inactive", status="INACTIVE")
    assert entity.is_active() is False
    assert entity.status == "INACTIVE"

def test_entity_validation_empty_id():
    with pytest.raises(ValidationError) as exc_info:
        EntityModel(id="", name="Valid Name")
    assert "Entity ID cannot be empty or whitespace" in str(exc_info.value)

def test_entity_validation_whitespace_id():
    with pytest.raises(ValidationError) as exc_info:
        EntityModel(id="   ", name="Valid Name")
    assert "Entity ID cannot be empty or whitespace" in str(exc_info.value)

def test_entity_validation_empty_name():
    with pytest.raises(ValidationError) as exc_info:
        EntityModel(id="E-003", name="")
    assert "Entity name cannot be empty or whitespace" in str(exc_info.value)

def test_entity_validation_invalid_status():
    with pytest.raises(ValidationError) as exc_info:
        EntityModel(id="E-004", name="Valid Name", status="UNKNOWN")
    assert "Invalid status" in str(exc_info.value)

def test_entity_validation_valid_statuses():
    for status in ["ACTIVE", "inactive", "ARCHIVED", "pending"]:
        entity = EntityModel(id="E-005", name="Valid", status=status)
        assert entity.status == status.upper()
