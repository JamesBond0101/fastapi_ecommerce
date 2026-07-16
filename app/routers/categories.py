from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.auth import get_current_admin
from app.models.categories import Category as CategoryModel
from app.schemas import Category as CategorySchema, CategoryCreate, User as UserSchema
from app.db_depends import get_async_db

router = APIRouter(
    prefix="/categories",
    tags=["categories"]
)

@router.get("/", response_model=list[CategorySchema])
async def get_all_categories(db: AsyncSession = Depends(get_async_db)) -> list[CategorySchema]:
    stmt = select(CategoryModel).where(CategoryModel.is_active == True)
    result = await db.scalars(stmt)
    categories = result.all()
    return categories


@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_admin)
) -> CategorySchema:
    if category.parent_id is not None:
        stmt = select(CategoryModel).where(
            CategoryModel.id == category.parent_id,
            CategoryModel.is_active == True
        )
        result = await db.scalars(stmt)
        parent = result.first()
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")


    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    await db.commit()
    return db_category


@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(
    category_id: int,
    category: CategoryCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_admin)
) -> CategorySchema:
    stmt = select(CategoryModel).where(
        CategoryModel.id == category_id,
        CategoryModel.is_active == True
    )
    db_category = (await db.scalars(stmt)).first()
    if db_category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(
            CategoryModel.id == category.parent_id,
            CategoryModel.is_active == True
        )
        parent = (await db.scalars(parent_stmt)).first()
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(**category.model_dump()))
    await db.commit()
    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_admin)
) -> dict:
    stmt = select(CategoryModel).where(
        CategoryModel.id == category_id,
        CategoryModel.is_active == True
    )
    category = (await db.scalars(stmt)).first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    await db.commit()
    return {"status": "success", "message": "Category marked as inactive"}