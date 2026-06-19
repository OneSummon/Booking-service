from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.schemas.enums import UserStatus


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class InfoUserSchema(Base):
    id: int
    first_name: str | None
    last_name: str | None
    email: str
    created_at: datetime
    updated_at: datetime
    role: UserStatus

class UpdateUserSchema(Base):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        if v is None:
            return v
        return str(v).lower().strip()

class ChangePasswordSchema(Base):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
    retry_new_password: str