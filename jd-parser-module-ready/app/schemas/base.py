"""Base configuration for Pydantic models with camelCase aliases."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base Pydantic model with automatic camelCase alias generation and attribute population."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
