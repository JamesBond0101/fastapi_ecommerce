from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_seller
from app.db_depends import get_async_db
from app.schemas import ProductCreate, Product as ProductSchema, User as UserSchema, ProductList
from app.models import Product as ProductModel, Category as CategoryModel


router = APIRouter(
    prefix="/products",
    tags=["products"],
)


@router.get("/", status_code=status.HTTP_200_OK, response_model=ProductList)
async def get_all_products(
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: int | None = Query(None, description="Category ID"),
    min_price: float | None = Query(None, ge=0.0, description="Minimum price"),
    max_price: float | None = Query(None, ge=0.0, description="Maximum number"),
    in_stock: bool | None = Query(None, description="In Stock"),
    seller_id: int | None = Query(None, description="Seller ID"),
    from_date: datetime | None = Query(None, description="From date"),
    to_date: datetime | None = Query(None, description="To date"),
) -> ProductList:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Min price must be greater than max price",
        )

    filters = [ProductModel.is_active == True]
    if category_id is not None:
        filters.append(ProductModel.category_id == category_id)
    if min_price is not None:
        filters.append(ProductModel.price >= min_price)
    if max_price is not None:
        filters.append(ProductModel.price <= max_price)
    if in_stock is not None:
        filters.append(ProductModel.stock > 0 if in_stock else ProductModel.stock == 0)
    if seller_id is not None:
        filters.append(ProductModel.seller_id == seller_id)
    if from_date is not None:
        filters.append(ProductModel.created_at >= from_date)
    if to_date is not None:
        filters.append(ProductModel.created_at <= to_date)

    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)
    total = (await db.scalar(total_stmt)) or 0

    products_stmt = select(ProductModel).where(*filters).order_by(ProductModel.id).offset((page - 1) * page_size).limit(page_size)
    items = (await db.scalars(products_stmt)).all()

    result = {
        "total": total,
        "items": items,
        "page": page,
        "page_size": page_size,
    }
    return result


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProductSchema)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_seller)
) -> ProductSchema:
    stmt = select(CategoryModel).where(
        CategoryModel.id == product.category_id,
        CategoryModel.is_active == True
    )
    category = (await db.scalars(stmt)).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")
    db_product = ProductModel(**product.model_dump(), seller_id=current_user.id)
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.get("/category/{category_id}", status_code=status.HTTP_200_OK, response_model=Optional[list[ProductSchema]])
async def get_products_by_category(category_id: int, db: AsyncSession = Depends(get_async_db)) -> Optional[list[ProductSchema]]:
    stmt = select(CategoryModel).where(CategoryModel.id == category_id, CategoryModel.is_active == True)
    category = (await db.scalars(stmt)).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found or inactive")
    stmt_products = select(ProductModel).where(
        ProductModel.category_id == category_id,
        ProductModel.is_active == True,
    )
    products = (await db.scalars(stmt_products)).all()
    return products


@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_async_db)) -> ProductSchema:
    stmt = select(ProductModel).where(
        ProductModel.is_active == True,
        ProductModel.id == product_id,
    )
    product = (await db.scalars(stmt)).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    category = (await db.scalars(select(CategoryModel).where(
        CategoryModel.is_active == True,
        CategoryModel.id == product.category_id,
    ))).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    return product


@router.put("/{product_id}", status_code=status.HTTP_200_OK, response_model=ProductSchema)
async def update_product(
    product_id: int,
    product: ProductCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_seller)
) -> ProductSchema:
    stmt = select(ProductModel).where(
        ProductModel.is_active == True,
        ProductModel.id == product_id,
    )
    db_product = (await db.scalars(stmt)).first()
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    if db_product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own products")
    category = (await db.scalars(select(CategoryModel).where(
        CategoryModel.is_active == True,
        CategoryModel.id == product.category_id,
    ))).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    await db.execute(update(ProductModel).where(ProductModel.id == product_id).values(**product.model_dump()))
    await db.commit()
    await db.refresh(db_product)
    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_seller)
) -> dict:
    stmt = select(ProductModel).where(
        ProductModel.is_active == True,
        ProductModel.id == product_id,
    )
    db_product = (await db.scalars(stmt)).first()
    if db_product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")
    if db_product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own products")
    await db.execute(update(ProductModel).where(ProductModel.id == product_id).values(is_active=False))
    await db.commit()
    return {"status": "success", "message": "Product marked as inactive"}