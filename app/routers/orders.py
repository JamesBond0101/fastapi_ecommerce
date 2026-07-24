from decimal import Decimal

from fastapi import APIRouter, status, Depends, HTTPException, Query
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.db_depends import get_async_db
from app.models.orders import Order as OrderModel, OrderItem as OrderItemModel
from app.models.users import User as UserModel
from app.models.cart_items import CartItem as CartItemModel
from app.schemas import Order as OrderSchema, OrderList

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
)


async def _load_order_with_items(db: AsyncSession, order_id: int) -> OrderModel | None:
    order_stmt = select(OrderModel).options(
        selectinload(OrderModel.items).selectinload(OrderItemModel.product),
    ).where(
        OrderModel.id == order_id
    )
    order = (await db.scalars(order_stmt)).first()

    return order


@router.post("/checkout", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
async def checkout_order(
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user)
) -> OrderSchema:
    cart_stmt = (select(CartItemModel)
        .options(selectinload(CartItemModel.product))
        .where(CartItemModel.user_id == current_user.id)
        .order_by(CartItemModel.id)
    )
    cart_items = (await db.scalars(cart_stmt)).all()
    if cart_items is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    order = OrderModel(user_id=current_user.id)
    total_amount = Decimal("0")

    for cart_item in cart_items:
        product = cart_item.product
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product {cart_item.product_id} is unavailable")
        if product.stock < cart_item.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Not enough stock for product {product.name}")
        unit_price = product.price
        total_price = unit_price * cart_item.quantity
        total_amount += total_price

        order_item = OrderItemModel(
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )
        order.items.append(order_item)
        product.stock -= cart_item.quantity

    order.total_amount = total_amount
    db.add(order)
    await db.execute(delete(CartItemModel).where(CartItemModel.user_id == current_user.id))
    await db.commit()

    created_order = await _load_order_with_items(db, order.id)
    if created_order is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order")
    return created_order


@router.get("/", response_model=OrderList)
async def get_orders(
    page: int = Query(1, ge=1, le=100),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user)
) -> OrderList:
    total_stmt = select(func.count(OrderModel.id)).where(OrderModel.user_id == current_user.id)
    total = (await db.scalars(total_stmt)).first() or 0

    orders_stmt = (select(OrderModel)
        .options(selectinload(OrderModel.items).selectinload(OrderItemModel.product))
        .where(OrderModel.user_id == current_user.id)
        .order_by(OrderModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = (await db.scalars(orders_stmt)).all()

    return OrderList(items=orders, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderSchema)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_user)
) -> OrderSchema:
    order = await _load_order_with_items(db, order_id)
    if not order or (order.user_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
