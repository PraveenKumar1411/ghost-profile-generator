"""Application API router."""

from fastapi import APIRouter

from app.routers.health import router as health_router
from app.routers.report import router as report_router
from app.routers.scan import router as scan_router
from app.routers.scans import router as scans_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(scan_router)
api_router.include_router(scans_router)
api_router.include_router(report_router)
