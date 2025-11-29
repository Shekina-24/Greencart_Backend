from fastapi import APIRouter

from .endpoints import admin_refs, admin_reports, admin_reviews, admin_users, analytics, auth, cart, gdpr, health, orders, payments, producers, products, public_data, reviews, users, uploads

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(producers.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(analytics.router)
api_router.include_router(reviews.router)
api_router.include_router(admin_reviews.router)
api_router.include_router(admin_reports.router)
api_router.include_router(admin_refs.router)
api_router.include_router(admin_users.router)
api_router.include_router(public_data.router)
api_router.include_router(gdpr.router)
api_router.include_router(users.router)
api_router.include_router(cart.router)
api_router.include_router(uploads.router)
