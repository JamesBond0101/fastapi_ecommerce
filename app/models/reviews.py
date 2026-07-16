from datetime import datetime

from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] =mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    comment: Mapped[str] = mapped_column(String, nullable=True)
    comment_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")

    __table_args__ = (
        CheckConstraint("grade >= 1 AND grade <= 5", name="check_grade"),
    )