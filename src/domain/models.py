"""Core Domain Models"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class EntityModel(BaseModel):
    id: str = Field(description="Unique entity identifier")
    name: str = Field(description="Entity name")
    status: str = Field(default="ACTIVE", description="Entity status (ACTIVE, INACTIVE, ARCHIVED)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional entity metadata")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Entity ID cannot be empty or whitespace")
        return v.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Entity name cannot be empty or whitespace")
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = {"ACTIVE", "INACTIVE", "ARCHIVED", "PENDING"}
        v_upper = v.upper()
        if v_upper not in valid_statuses:
            raise ValueError(f"Invalid status '{v}'. Must be one of {valid_statuses}")
        return v_upper

    def is_active(self) -> bool:
        return self.status == "ACTIVE"
