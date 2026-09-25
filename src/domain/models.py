"""Core Domain Models"""
from typing import Optional
from pydantic import BaseModel, Field

class EntityModel(BaseModel):
    id: str = Field(description="Unique entity identifier")
    name: str = Field(description="Entity name")
    status: str = Field(default="ACTIVE")
    metadata: dict = Field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == "ACTIVE"
