"""Health check роутер"""

from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "scim-proxy",
        "version": "1.0.0"
    }


@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {"message": "SCIM Proxy Service is running"}