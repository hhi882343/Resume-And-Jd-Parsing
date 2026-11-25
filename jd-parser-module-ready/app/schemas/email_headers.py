"""Pydantic schemas for the Universal Email Header Extraction API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from app.schemas.base import CamelModel


class EmailContactSchema(CamelModel):
    """Schema representing an individual email contact."""

    name: str = ""
    email: str


class EmailHeadersRequest(CamelModel):
    """Request schema for extracting headers from raw email text."""

    raw_text: str = Field(..., min_length=1, description="Raw pasted email content")


class EmailHeadersResponse(CamelModel):
    """Response schema matching the required Universal Email Header JSON contract."""

    from_: List[EmailContactSchema] = Field(default_factory=list, alias="from")
    to: List[EmailContactSchema] = Field(default_factory=list)
    cc: List[EmailContactSchema] = Field(default_factory=list)
    subject: Optional[str] = None
    date: Optional[str] = None

