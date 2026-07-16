from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_buyer, get_current_user
from app.db_depends import get_async_db
from app.models import Review as ReviewModel, Product as ProductModel
from app.schemas import Review as ReviewSchema, ReviewCreate, User as UserSchema, Product as ProductSchema


router = APIRouter(
    prefix="/reviews",
    tags=["reviews"]
)


async def update_product_rating(product_id: int, db: AsyncSession):
    result = await db.execute(
        select(func.avg(ReviewModel.grade)).where(
            ReviewModel.product_id == product_id,
            ReviewModel.is_active == True
        )
    )
    avg_rating = result.scalar() or 0.0
    await db.execute(update(ProductModel).where(ProductModel.id == product_id).values(rating=avg_rating))
    await db.commit()


async def get_product(product_id: int, db: AsyncSession) -> ProductSchema:
    product_stmt =  select(ProductModel).where(
        ProductModel.is_active == True,
        ProductModel.id == product_id
    )
    product = (await db.scalars(product_stmt)).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("/", response_model=list[ReviewSchema], status_code=status.HTTP_200_OK)
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)) -> list[ReviewSchema]:
    reviews_stmt = select(ReviewModel).where(ReviewModel.is_active == True)
    reviews = (await db.scalars(reviews_stmt)).all()
    return reviews


@router.get("/products/{product_id}/reviews", response_model=list[ReviewSchema], status_code=status.HTTP_200_OK)
async def get_reviews_by_product_id(product_id: int, db: AsyncSession = Depends(get_async_db)) -> list[ReviewSchema]:
    product = await get_product(product_id, db)
    reviews_stmt = select(ReviewModel).where(
        ReviewModel.is_active == True,
        ReviewModel.product_id == product.id
    )
    reviews = (await db.scalars(reviews_stmt)).all()
    return reviews


@router.post("/", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
    review: ReviewCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_buyer)
) -> ReviewSchema:
    product = await get_product(review.product_id, db)
    db_review = ReviewModel(**review.model_dump(), user_id=current_user.id)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)
    await update_product_rating(product_id=product.id, db=db)
    return db_review


@router.delete("/{review_id}", status_code=status.HTTP_200_OK)
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserSchema = Depends(get_current_user)
) -> dict:
    review_stmt = select(ReviewModel).where(
        ReviewModel.is_active == True,
        ReviewModel.id == review_id
    )
    review = (await db.scalars(review_stmt)).first()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    if current_user.id != review.user_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")
    await db.execute(update(ReviewModel).where(ReviewModel.id == review_id).values(is_active=False))
    await db.commit()
    await db.refresh(review)
    await update_product_rating(product_id=review.product_id, db=db)
    return {"message": "Review deleted"}




