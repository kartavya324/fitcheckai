from fastapi import APIRouter

from app.api.v1 import health, jobs, uploads, products

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(products.router)
