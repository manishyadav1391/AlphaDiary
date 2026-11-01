"""Request and response models for FR-AUTH."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalise(cls, value: str) -> str:
        return value.strip().lower()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
