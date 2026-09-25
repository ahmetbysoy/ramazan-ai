"""Public API Controller and Health Verification (TASK-003)"""
from typing import Dict, Any, List
from src.domain.service import EntityService


class DomainController:
    def __init__(self, service: EntityService):
        self.service = service

    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "UP",
            "service": "DomainController",
            "version": "1.0.0"
        }

    def create_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        entity_id = payload.get("id")
        name = payload.get("name")
        if not entity_id or not name:
            raise ValueError("id and name are required")
        entity = self.service.create_entity(entity_id, name, payload.get("metadata"))
        return entity.model_dump()

    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        entity = self.service.get_entity(entity_id)
        if not entity:
            raise KeyError(f"Entity '{entity_id}' not found")
        return entity.model_dump()

    def list_entities(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.service.list_active_entities()]
