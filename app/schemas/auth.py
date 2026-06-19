from pydantic import BaseModel, EmailStr, Field, field_validator


class CreateUserSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_to_lower(cls, v: str):
        return v.lower().strip()


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenSchema(BaseModel):
    refresh_token: str