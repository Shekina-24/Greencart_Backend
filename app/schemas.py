from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, EmailStr, Field, model_validator

from .models import OrderStatus, ProducerStatus, ProductStatus, ReviewStatus, UserRole


class ORMModel(BaseModel):
    model_config = {"from_attributes": True}


# --- Users & Auth ---
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    consent_newsletter: bool = False
    consent_analytics: bool = False


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CONSUMER


class UserUpdate(BaseModel):

    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    consent_newsletter: Optional[bool] = None
    consent_analytics: Optional[bool] = None

    @model_validator(mode="after")
    def ensure_payload_not_empty(self) -> "UserUpdate":
        if not any(
            getattr(self, field) is not None
            for field in ("first_name", "last_name", "region", "consent_newsletter", "consent_analytics")
        ):
            raise ValueError("At least one field must be provided")
        return self


class UserRead(ORMModel):
    id: int
    email: EmailStr
    role: UserRole
    first_name: Optional[str]
    last_name: Optional[str]
    region: Optional[str]
    is_active: bool
    email_verified_at: Optional[datetime]
    last_login_at: Optional[datetime]
    consent_newsletter: bool
    consent_analytics: bool
    created_at: datetime
    updated_at: datetime


class Token(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
    jti: str
    scope: str = "access"


class RefreshTokenPayload(TokenPayload):
    scope: str = "refresh"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserRoleUpdate(BaseModel):
    role: UserRole


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CONSUMER
    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    consent_newsletter: bool = False
    consent_analytics: bool = False


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


# --- Producers ---
class ProducerProfileBase(BaseModel):
    legal_name: Optional[str] = Field(default=None, max_length=255)
    siret: Optional[str] = Field(default=None, max_length=14)
    label: Optional[str] = Field(default=None, max_length=120)
    bio: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)


class ProducerProfileCreate(ProducerProfileBase):
    status: ProducerStatus = ProducerStatus.PENDING


class ProducerProfileRead(ORMModel):
    id: int
    status: ProducerStatus
    legal_name: Optional[str]
    siret: Optional[str]
    label: Optional[str]
    bio: Optional[str]
    location: Optional[str]
    created_at: datetime
    updated_at: datetime


# --- Catalog / Products ---
class ProductImageCreate(BaseModel):
    url: AnyHttpUrl
    is_primary: bool = False


class ProductImageRead(ORMModel):
    id: int
    url: AnyHttpUrl
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class ProductBase(BaseModel):
    title: str = Field(max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    origin: Optional[str] = Field(default=None, max_length=255)
    dlc_date: Optional[date] = None
    impact_co2_g: Optional[int] = Field(default=None, ge=0)
    price_cents: int = Field(ge=0)
    promo_price_cents: Optional[int] = Field(default=None, ge=0)
    stock: int = Field(ge=0)
    status: ProductStatus = ProductStatus.DRAFT
    is_published: bool = False


class ProductCreate(ProductBase):
    images: list[ProductImageCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    origin: Optional[str] = Field(default=None, max_length=255)
    dlc_date: Optional[date] = None
    impact_co2_g: Optional[int] = Field(default=None, ge=0)
    price_cents: Optional[int] = Field(default=None, ge=0)
    promo_price_cents: Optional[int] = Field(default=None, ge=0)
    stock: Optional[int] = Field(default=None, ge=0)
    status: Optional[ProductStatus] = None
    is_published: Optional[bool] = None
    images: Optional[list[ProductImageCreate]] = None

    @model_validator(mode="after")
    def ensure_some_field(self) -> "ProductUpdate":
        if not any(
            getattr(self, field) is not None
            for field in (
                "title",
                "description",
                "category",
                "region",
                "origin",
                "dlc_date",
                "impact_co2_g",
                "price_cents",
                "promo_price_cents",
                "stock",
                "status",
                "is_published",
                "images",
            )
        ):
            raise ValueError("At least one field must be provided for update")
        return self


class ProductRead(ORMModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    region: Optional[str]
    origin: Optional[str]
    dlc_date: Optional[date]
    impact_co2_g: Optional[int]
    price_cents: int
    promo_price_cents: Optional[int]
    stock: int
    status: ProductStatus
    is_published: bool
    created_at: datetime
    updated_at: datetime
    images: list[ProductImageRead] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


# --- Cart ---
class CartItemUpdate(BaseModel):
    product_id: int
    quantity: int = Field(ge=0, le=100)


class CartItemRead(ORMModel):
    id: int
    product_id: int
    product_title: str
    quantity: int
    unit_price_cents: int
    subtotal_cents: int
    created_at: datetime
    updated_at: datetime


class CartRead(BaseModel):
    items: list[CartItemRead]
    total_items: int
    total_amount_cents: int


# --- Orders ---
class OrderItemInput(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=100)


class OrderCreate(BaseModel):
    items: list[OrderItemInput]
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def ensure_items(self) -> "OrderCreate":
        if not self.items:
            raise ValueError("Order requires at least one item")
        return self


class OrderLineRead(ORMModel):
    id: int
    product_id: Optional[int]
    product_title: str
    quantity: int
    unit_price_cents: int
    reference_price_cents: int | None = None
    subtotal_cents: int
    impact_co2_g: Optional[int]
    created_at: datetime
    updated_at: datetime


class OrderRead(ORMModel):
    id: int
    status: OrderStatus
    currency: str
    total_amount_cents: int
    total_items: int
    total_impact_co2_g: int
    payment_reference: Optional[str]
    payment_provider: Optional[str]
    idempotency_key: Optional[str]
    placed_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    lines: list[OrderLineRead] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    items: list[OrderRead]
    total: int
    limit: int
    offset: int


# --- Reviews ---
class ReviewBase(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


class ReviewCreate(ReviewBase):
    product_id: int
    order_id: Optional[int] = None


class ReviewRead(ORMModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    comment: Optional[str]
    status: ReviewStatus
    created_at: datetime
    published_at: Optional[datetime]
    moderation_notes: Optional[str]


class ReviewListResponse(BaseModel):
    items: list[ReviewRead]
    total: int
    limit: int
    offset: int


class ReviewModerationRequest(BaseModel):
    status: ReviewStatus
    moderation_notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_status(self) -> "ReviewModerationRequest":
        if self.status not in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
            raise ValueError("Status must be approved or rejected for moderation")
        return self


# --- Reference Values ---
class ReferenceValueBase(BaseModel):
    name: str = Field(max_length=150)
    slug: str = Field(max_length=160)
    is_active: bool = True


class ReferenceValueCreate(ReferenceValueBase):
    pass


class ReferenceValueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    slug: Optional[str] = Field(default=None, max_length=160)
    is_active: Optional[bool] = None


class ReferenceValueRead(ORMModel):
    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReferenceValueList(BaseModel):
    items: list[ReferenceValueRead]
    total: int
    limit: int
    offset: int


# --- Analytics ---
class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(max_length=120)
    source: Optional[str] = Field(default=None, max_length=120)
    properties: Optional[dict] = None


class AnalyticsEventRead(ORMModel):
    id: int
    event_name: str
    source: Optional[str]
    payload: Optional[str]
    created_at: datetime


class AnalyticsEventListResponse(BaseModel):
    items: list[AnalyticsEventRead]
    total: int
    limit: int
    offset: int


class AnalyticsEmbedTokenRequest(BaseModel):
    region: Optional[str] = Field(default=None, max_length=120)
    producer_id: Optional[int] = None
    date_start: Optional[str] = Field(default=None, max_length=40)
    date_end: Optional[str] = Field(default=None, max_length=40)


class AnalyticsEmbedTokenResponse(BaseModel):
    embed_url: str
    token: str
    expires_at: datetime


class AnalyticsReportSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    total_orders: int
    total_revenue_cents: int
    total_items_sold: int
    average_order_value_cents: int
    top_products: list[dict]


class ReportFileInfo(BaseModel):
    format: Literal["html", "pdf"]
    path: str
    size_bytes: int


class AnalyticsReport(BaseModel):
    summary: AnalyticsReportSummary
    files: list[ReportFileInfo]


class AnalyticsTimeseriesPoint(BaseModel):
    bucket: str
    orders: int
    revenue_cents: int
    items: int
    aov_cents: int


class AnalyticsTimeseries(BaseModel):
    points: list[AnalyticsTimeseriesPoint]


class RateLimitMetric(BaseModel):
    namespace: str
    allowed: int
    blocked: int


class RateLimitMetrics(BaseModel):
    items: list[RateLimitMetric]


class ProducerOrderLineRead(BaseModel):
    id: int
    order_id: int
    product_id: int | None
    product_title: str
    quantity: int
    unit_price_cents: int
    reference_price_cents: int | None = None
    subtotal_cents: int
    created_at: datetime


class ProducerOrderRead(BaseModel):
    order_id: int
    status: OrderStatus
    customer_id: int
    customer_email: EmailStr
    created_at: datetime
    total_amount_cents: int
    lines: list[ProducerOrderLineRead]


class ProducerOrderListResponse(BaseModel):
    items: list[ProducerOrderRead]
    total: int
    limit: int
    offset: int


class ProducerTopProduct(BaseModel):
    product_id: int
    title: str
    revenue_cents: int
    units_sold: int
    average_rating: Optional[float] = None


class ProducerInsights(BaseModel):
    total_orders: int
    total_revenue_cents: int
    total_items_sold: int
    average_order_value_cents: int
    total_impact_co2_g: int
    top_products: list[ProducerTopProduct] = Field(default_factory=list)


# --- Payments ---
class PaymentInitRequest(BaseModel):
    order_id: int
    provider: str = Field(pattern="^(stripe|paygreen|manual)$")
    success_url: AnyHttpUrl
    cancel_url: AnyHttpUrl


class PaymentSession(BaseModel):
    checkout_url: AnyHttpUrl
    payment_reference: str


class PaymentWebhookPayload(BaseModel):
    provider: str
    order_id: int
    event: str = Field(pattern="^(payment_succeeded|payment_failed|payment_refunded)$")
    signature: str = Field(min_length=8)
    payload: dict = Field(default_factory=dict)
