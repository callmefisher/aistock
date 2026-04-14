from fastapi import APIRouter, Depends, HTTPException
from api.auth import get_current_user
from models.models import User
from services import workflow_result_service as svc

router = APIRouter()


@router.get("/results/grouped")
async def get_results_grouped(
    current_user: User = Depends(get_current_user)
):
    grouped = await svc.get_results_grouped()
    return {"success": True, "data": grouped}


@router.get("/results/{result_id}/preview")
async def get_result_preview(
    result_id: int,
    current_user: User = Depends(get_current_user)
):
    result = await svc.get_result_preview(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")
    return {"success": True, "data": result}


@router.get("/results/{result_id}/full")
async def get_result_full(
    result_id: int,
    current_user: User = Depends(get_current_user)
):
    result = await svc.get_result_full(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")
    return {"success": True, "data": result}


@router.delete("/results/{result_id}")
async def delete_result(
    result_id: int,
    current_user: User = Depends(get_current_user)
):
    ok = await svc.delete_result(result_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"success": True, "message": "已删除"}
