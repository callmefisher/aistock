from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import os
import logging
import tempfile
import pandas as pd
from core.database import get_async_db
from models.models import StockPool
from api.auth import get_current_user
from models.models import User

router = APIRouter()


class StockPoolResponse(BaseModel):
    id: int
    name: str
    task_id: Optional[int] = None
    workflow_id: Optional[int] = None
    date_str: str = ""
    file_path: Optional[str] = None
    total_stocks: Optional[int] = None
    filter_conditions: Optional[list] = None
    source_types: Optional[list] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[StockPoolResponse])
async def list_stock_pools(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(StockPool).order_by(StockPool.id.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{stock_pool_id}", response_model=StockPoolResponse)
async def get_stock_pool(
    stock_pool_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(StockPool).where(StockPool.id == stock_pool_id)
    )
    stock_pool = result.scalar_one_or_none()
    if not stock_pool:
        raise HTTPException(status_code=404, detail="选股池不存在")
    return stock_pool


@router.get("/{stock_pool_id}/data")
async def get_stock_pool_data(
    stock_pool_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """返回选股池完整数据"""
    result = await db.execute(
        select(StockPool).where(StockPool.id == stock_pool_id)
    )
    stock_pool = result.scalar_one_or_none()
    if not stock_pool:
        raise HTTPException(status_code=404, detail="选股池不存在")

    data = stock_pool.data or []
    # data 可能是 JSON 字符串或已解析的 list
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = []

    return {
        "id": stock_pool.id,
        "name": stock_pool.name,
        "date_str": stock_pool.date_str or "",
        "total_stocks": stock_pool.total_stocks or 0,
        "source_types": stock_pool.source_types or [],
        "filter_conditions": stock_pool.filter_conditions or [],
        "data": data
    }


@router.get("/{stock_pool_id}/download")
async def download_stock_pool(
    stock_pool_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(StockPool).where(StockPool.id == stock_pool_id)
    )
    stock_pool = result.scalar_one_or_none()

    if not stock_pool:
        raise HTTPException(status_code=404, detail="选股池不存在")

    # 原始文件存在，直接返回
    if stock_pool.file_path and os.path.exists(stock_pool.file_path):
        return FileResponse(
            path=stock_pool.file_path,
            filename=os.path.basename(stock_pool.file_path),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # 文件不存在，从 DB 中的 data 字段重新生成 Excel
    data = stock_pool.data or []
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = []

    if not data:
        raise HTTPException(status_code=404, detail="文件不存在且无数据可导出")

    date_part = (stock_pool.date_str or "").replace("-", "")
    filename = f"7条件交集{date_part}.xlsx"

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        df = pd.DataFrame(data)
        df.to_excel(tmp_path, index=False, engine="openpyxl")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"生成Excel失败: stock_pool_id={stock_pool_id}, error={e}")
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail="生成Excel失败")

    return FileResponse(
        path=tmp_path,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        background=BackgroundTask(os.unlink, tmp_path),
    )


@router.delete("/{stock_pool_id}")
async def delete_stock_pool(
    stock_pool_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(StockPool).where(StockPool.id == stock_pool_id)
    )
    stock_pool = result.scalar_one_or_none()

    if not stock_pool:
        raise HTTPException(status_code=404, detail="选股池不存在")

    if stock_pool.file_path and os.path.exists(stock_pool.file_path):
        os.remove(stock_pool.file_path)

    await db.delete(stock_pool)
    await db.commit()
    return {"message": "选股池已删除"}
