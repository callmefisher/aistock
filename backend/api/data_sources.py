from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_async_db
from ..models.models import DataSource
from ..api.auth import get_current_user
from ..models.models import User

router = APIRouter()


class DataSourceCreate(BaseModel):
    name: str
    website_url: str
    login_type: str
    login_config: dict = {}
    data_format: str
    extraction_config: dict = {}


class DataSourceUpdate(BaseModel):
    name: str = None
    website_url: str = None
    login_type: str = None
    login_config: dict = None
    data_format: str = None
    extraction_config: dict = None
    is_active: bool = None


class DataSourceResponse(BaseModel):
    id: int
    name: str
    website_url: str
    login_type: str
    data_format: str
    is_active: bool
    last_login_time: datetime = None
    last_fetch_time: datetime = None
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=DataSourceResponse)
async def create_data_source(
    data_source: DataSourceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    db_data_source = DataSource(**data_source.dict())
    db.add(db_data_source)
    await db.commit()
    await db.refresh(db_data_source)
    return db_data_source


@router.get("/", response_model=List[DataSourceResponse])
async def list_data_sources(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(DataSource).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(DataSource).where(DataSource.id == data_source_id)
    )
    data_source = result.scalar_one_or_none()
    if not data_source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    return data_source


@router.put("/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: int,
    data_source_update: DataSourceUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(DataSource).where(DataSource.id == data_source_id)
    )
    db_data_source = result.scalar_one_or_none()
    
    if not db_data_source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    
    update_data = data_source_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_data_source, field, value)
    
    await db.commit()
    await db.refresh(db_data_source)
    return db_data_source


@router.delete("/{data_source_id}")
async def delete_data_source(
    data_source_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(DataSource).where(DataSource.id == data_source_id)
    )
    db_data_source = result.scalar_one_or_none()
    
    if not db_data_source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    
    await db.delete(db_data_source)
    await db.commit()
    return {"message": "数据源已删除"}
