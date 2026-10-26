from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    image_url: str = ""
    category: str = "General"
    is_active: bool = True


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=100)


class OrderIn(BaseModel):
    address: str = Field(min_length=5)
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int | None
    name: str
    price: float
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    total: float
    status: str
    address: str
    created_at: datetime
    user_email: str | None
    items: list[OrderItemOut]


class RoleIn(BaseModel):
    role: Literal["customer", "admin"]


class StatusIn(BaseModel):
    status: Literal["pending", "paid", "shipped", "delivered", "cancelled"]
