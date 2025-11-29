from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .database import Base


class TimestampMixin:
    """Reusable timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserRole(str, enum.Enum):
    CONSUMER = "consumer"
    PRODUCER = "producer"
    ADMIN = "admin"


class ProducerStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.CONSUMER, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_newsletter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_analytics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    producer_profile: Mapped["ProducerProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    products: Mapped[list["Product"]] = relationship(back_populates="producer")
    orders: Mapped[list["Order"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analytics_events: Mapped[list["AnalyticsEvent"]] = relationship(back_populates="user")


class ProducerProfile(Base, TimestampMixin):
    __tablename__ = "producer_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    siret: Mapped[str | None] = mapped_column(String(14))
    label: Mapped[str | None] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ProducerStatus] = mapped_column(
        SQLEnum(ProducerStatus),
        default=ProducerStatus.PENDING,
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="producer_profile")
    products: Mapped[list["Product"]] = relationship(back_populates="producer_profile")


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_region_category", "region", "category"),
        Index("ix_products_dlc", "dlc_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    producer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    producer_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("producer_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str | None] = mapped_column(String(255))
    dlc_date: Mapped[date | None] = mapped_column(Date)
    impact_co2_g: Mapped[int | None] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    promo_price_cents: Mapped[int | None] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ProductStatus] = mapped_column(
        SQLEnum(ProductStatus),
        default=ProductStatus.DRAFT,
        nullable=False,
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    producer: Mapped[User] = relationship(back_populates="products")
    producer_profile: Mapped[ProducerProfile | None] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    order_lines: Mapped[list["OrderLine"]] = relationship(back_populates="product")
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="product")
    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


class ProductImage(Base, TimestampMixin):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    product: Mapped[Product] = relationship(back_populates="images")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ux_orders_idempotency_key", "idempotency_key", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_impact_co2_g: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_reference: Mapped[str | None] = mapped_column(String(255))
    payment_provider: Mapped[str | None] = mapped_column(String(50))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="orders")
    lines: Mapped[list["OrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderLine(Base, TimestampMixin):
    __tablename__ = "order_lines"
    __table_args__ = (Index("ix_order_lines_product_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    product_title: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    impact_co2_g: Mapped[int | None] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product | None] = relationship(back_populates="order_lines")


class CartItem(Base, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        Index("ux_cart_user_product", "user_id", "product_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    user: Mapped[User] = relationship(back_populates="cart_items")
    product: Mapped[Product] = relationship(back_populates="cart_items")


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_product_status", "product_id", "status"),
        Index("ix_reviews_user_product", "user_id", "product_id"),
        UniqueConstraint("user_id", "product_id", "order_id", name="ux_review_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReviewStatus] = mapped_column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="reviews")
    product: Mapped[Product] = relationship(back_populates="reviews")
    order: Mapped[Order | None] = relationship()

class ReferenceKind(str, enum.Enum):
    CATEGORY = "category"
    REGION = "region"


class ReferenceValue(Base, TimestampMixin):
    __tablename__ = "reference_values"
    __table_args__ = (UniqueConstraint("kind", "slug", name="ux_reference_kind_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[ReferenceKind] = mapped_column(SQLEnum(ReferenceKind), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AnalyticsEvent(Base, TimestampMixin):
    __tablename__ = "analytics_events"
    __table_args__ = (Index("ix_analytics_events_name_created", "event_name", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship(back_populates="analytics_events")


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_action", "action"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(50))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship(back_populates="audit_logs")


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_jti", "jti", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), nullable=False)
    hashed_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
