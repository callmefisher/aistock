from fastapi import APIRouter

router = APIRouter()


@router.get("/version")
async def get_version():
    from core.config import settings
    return {"version": settings.VERSION}
