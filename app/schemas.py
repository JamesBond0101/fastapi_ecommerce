from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, EmailStr


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Название категории (3-50 символов)")
    parent_id: int | None = Field(None, description="ID родительской категории, если есть")


class Category(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор категории")
    name: str = Field(..., description="Название категории")
    parent_id: int | None = Field(None, description="ID родительской категории, если есть")
    is_active: bool = Field(..., description="Активность категории")

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100,
                      description="Название товара (3-100 символов)")
    description: str | None = Field(None, max_length=500,
                                       description="Описание товара (до 500 символов)")
    price: Decimal = Field(..., gt=0, description="Цена товара (больше 0)", decimal_places=2)
    image_url: str | None = Field(None, max_length=200, description="URL изображения товара")
    stock: int = Field(..., ge=0, description="Количество товара на складе (0 или больше)")
    category_id: int = Field(..., description="ID категории, к которой относится товар")


class Product(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор товара")
    name: str = Field(..., description="Название товара")
    description: str | None = Field(None, description="Описание товара")
    price: Decimal = Field(..., description="Цена товара в рублях", gt=0, decimal_places=2)
    image_url: str | None = Field(None, description="URL изображения товара")
    stock: int = Field(..., description="Количество товара на складе")
    is_active: bool = Field(..., description="Активность товара")
    rating: Decimal = Field(default=0.0, description="Рейтинг товара")
    category_id: int = Field(..., description="ID категории")
    seller_id: int = Field(..., description="ID продавца")
    created_at: datetime = Field(..., description="Дата создания товара")

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8,  description="Password is required 8 characters long")
    role: str = Field(default="buyer", pattern="^(buyer|seller)$", description="Role: 'buyer' or 'seller'")


class User(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str

    model_config = ConfigDict(from_attributes=True)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class Review(BaseModel):
    id: int = Field(..., description="Unique ID")
    user_id: int = Field(..., description="User ID")
    product_id: int = Field(..., description="Product ID")
    comment: str | None = Field(None, description="Product comment")
    comment_date: datetime = Field(..., description="Comment date")
    grade: int = Field(..., ge=1, le=5, description="Grade")
    is_active: bool = Field(default=True)

    model_config = ConfigDict(from_attributes=True)


class ReviewCreate(BaseModel):
    product_id: int = Field(..., description="Product ID")
    comment: str | None = Field(None, description="Product comment")
    grade: int = Field(..., ge=1, le=5, description="Grade")


class ProductList(BaseModel):
    items: list[Product] = Field(description="Product list")
    total: int = Field(ge=0, description="Total product count")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Page size")

    model_config = ConfigDict(from_attributes=True)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, description="Quantity of product")


class CartItemBase(BaseModel):
    product_id: int = Field(description="Product ID")
    quantity: int = Field(ge=1, description="Quantity of product")


class CartItemCreate(CartItemBase):
    pass


class CartItem(BaseModel):
    id: int = Field(description="Unique ID")
    quantity: int = Field(ge=1, description="Quantity of product")
    product: Product = Field(description="Product information")

    model_config = ConfigDict(from_attributes=True)


class Cart(BaseModel):
    user_id: int = Field(description="User ID")
    items: list[CartItem]  = Field(default_factory=list, description="Cart items")
    total_quantity: int = Field(ge=0, description="Total quantity")
    total_price: Decimal = Field(ge=0, description="Total price")

    model_config = ConfigDict(from_attributes=True)