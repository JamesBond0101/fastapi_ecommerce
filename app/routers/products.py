import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query, UploadFile, File
from sqlalchemy import select, update, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_seller
from app.db_depends import get_async_db
from app.schemas import ProductCreate, Product as ProductSchema, User as UserSchema, ProductList
from app.models import Product as ProductModel, Category as CategoryModel


router = APIRouter(
    prefix="/products",
    tags=["products"],
)


BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_ROOT = BASE_DIR / "media" / "products"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024


async def save_product_image(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPG, PNG or WebP images are allowed")

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is too large")

    extension = Path(file.filename or "").suffix.lower() or ".jpg"
    file_name = f"{uuid.uuid4()}.{extension}"
    file_path = MEDIA_ROOT / file_name
    file_path.write_bytes(content)
    return f"/media/products/{file_name}"


def remove_product_image(url: str | None) -> None:
    if url is None:
        return
    relative_path = url.lstrip("/")
    file_path = BASE_DIR / relative_path
    if file_path.exists():
        file_path.unlink()


@router.get("/", status_code=status.HTTP_200_OK, response_model=ProductList)
async def get_all_products(
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=1, description="Search by name"),
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

    rank_col = None
    if search:
        search_value = search.strip()
        if search_value:
            ts_query = func.websearch_to_tsquery('english', search_value)
            filters.append(ProductModel.tsv.op("@@")(ts_query))
            rank_col = func.ts_rank_cd(ProductModel.tsv, ts_query).label("rank")

    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)
    total = (await db.scalar(total_stmt)) or 0

    if rank_col is not None:
        products_stmt = select(ProductModel).where(*filters).order_by(desc(rank_col),ProductModel.id).offset((page - 1) * page_size).limit(page_size)
    else:
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
    product: ProductCreate = Depends(ProductCreate.as_form),
    image: UploadFile | None = File(None),
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

    image_url = await save_product_image(image) if image else None
    db_product = ProductModel(**product.model_dump(), seller_id=current_user.id, image_url=image_url)
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
    product: ProductCreate = Depends(ProductCreate.as_form),
    image: UploadFile | None = File(None),
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
    if image:
        remove_product_image(db_product.image_url)
        db_product.image_url = await save_product_image(image) if image else None
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

    remove_product_image(db_product.image_url)
    await db.execute(update(ProductModel).where(ProductModel.id == product_id).values(is_active=False, image_url=None))
    await db.commit()
    return {"status": "success", "message": "Product marked as inactive"}