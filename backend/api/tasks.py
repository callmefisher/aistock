from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_async_db
from ..models.models import Task, ExecutionLog
from ..api.auth import get_current_user
from ..models.models import User

router = APIRouter()


class TaskCreate(BaseModel):
    name: str
    data_source_ids: List[int]
    rule_ids: List[int]
    schedule_type: str = "manual"
    schedule_config: dict = None


class TaskUpdate(BaseModel):
    name: str = None
    data_source_ids: List[int] = None
    rule_ids: List[int] = None
    schedule_type: str = None
    schedule_config: dict = None
    is_active: bool = None


class TaskResponse(BaseModel):
    id: int
    name: str
    data_source_ids: List[int]
    rule_ids: List[int]
    schedule_type: str
    schedule_config: dict
    status: str
    last_run_time: datetime = None
    next_run_time: datetime = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExecutionLogResponse(BaseModel):
    id: int
    task_id: int
    status: str
    start_time: datetime
    end_time: datetime = None
    duration: float = None
    records_processed: int = None
    error_message: str = None
    output_file: str = None
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    db_task = Task(**task.dict())
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Task).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    db_task = result.scalar_one_or_none()
    
    if not db_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    await db.commit()
    await db.refresh(db_task)
    return db_task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    db_task = result.scalar_one_or_none()
    
    if not db_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(db_task)
    await db.commit()
    return {"message": "任务已删除"}


@router.post("/{task_id}/run")
async def run_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {"message": f"任务 {task_id} 已加入执行队列"}


@router.get("/{task_id}/logs", response_model=List[ExecutionLogResponse])
async def get_task_logs(
    task_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.task_id == task_id)
        .order_by(ExecutionLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
