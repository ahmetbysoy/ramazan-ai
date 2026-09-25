"""Business Service Layer and Repository Interface (TASK-002)"""
from typing import Dict, List, Optional
from src.domain.models import EntityModel


class RepositoryInterface:
    def get(self, entity_id: str) -> Optional[EntityModel]:
        raise NotImplementedError

    def save(self, entity: EntityModel) -> EntityModel:
        raise NotImplementedError

    def list_all(self) -> List[EntityModel]:
        raise NotImplementedError


class InMemoryEntityRepository(RepositoryInterface):
    def __init__(self):
        self._store: Dict[str, EntityModel] = {}

    def get(self, entity_id: str) -> Optional[EntityModel]:
        return self._store.get(entity_id)

    def save(self, entity: EntityModel) -> EntityModel:
        self._store[entity.id] = entity
        return entity

    def list_all(self) -> List[EntityModel]:
        return list(self._store.values())


class EntityService:
    def __init__(self, repository: RepositoryInterface):
        self.repository = repository

    def create_entity(self, entity_id: str, name: str, metadata: Optional[dict] = None) -> EntityModel:
        entity = EntityModel(id=entity_id, name=name, metadata=metadata or {})
        return self.repository.save(entity)

    def get_entity(self, entity_id: str) -> Optional[EntityModel]:
        return self.repository.get(entity_id)

    def list_active_entities(self) -> List[EntityModel]:
        return [e for e in self.repository.list_all() if e.is_active()]
