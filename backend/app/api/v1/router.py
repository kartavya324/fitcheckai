from fastapi import APIRouter

from app.api.v1 import (
    health, jobs, uploads, products, avatar, footwear, stylist, sizing, wardrobe, color, feed,
    auth, billing,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(billing.router)
api_router.include_router(health.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(products.router)
api_router.include_router(avatar.router)
api_router.include_router(footwear.router)
api_router.include_router(stylist.router)
api_router.include_router(sizing.router)
api_router.include_router(wardrobe.router)
api_router.include_router(color.router)
api_router.include_router(feed.router)
