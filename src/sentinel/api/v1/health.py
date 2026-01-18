from fastapi import APIRouter
from sentinel.api.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    return HealthResponse(status="healthy", version="0.1.0")