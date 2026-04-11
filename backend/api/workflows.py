from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel
from datetime import datetime
import os
import pandas as pd
from core.database import get_async_db
from models.models import Workflow
from api.auth import get_current_user
from models.models import User
from services.workflow_executor import workflow_executor
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class WorkflowStepConfig(BaseModel):
    data_source_id: Optional[int] = None
    file_path: Optional[str] = None
    columns: Optional[Any] = None
    output_filename: Optional[str] = None
    apply_formatting: Optional[bool] = True
    date_str: Optional[str] = None
    stock_code_column: Optional[str] = None
    date_column: Optional[str] = None
    use_fixed_columns: Optional[bool] = True
    exclude_patterns: Optional[List[Any]] = []
    exclude_patterns_text: Optional[str] = ""


class WorkflowStep(BaseModel):
    type: str
    config: Optional[Dict[str, Any]] = {}
    status: Optional[str] = "pending"


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStep]


class WorkflowUpdate(BaseModel):
    name: str = None
    description: str = None
    steps: List[WorkflowStep] = None
    status: str = None
    is_active: bool = None


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    steps: Union[List[dict], None] = None
    status: str
    last_run_time: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=WorkflowResponse)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    db_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        steps=[step.dict() for step in workflow.steps]
    )
    db.add(db_workflow)
    await db.commit()
    await db.refresh(db_workflow)
    return db_workflow


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Workflow).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    workflow_update: WorkflowUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    db_workflow = result.scalar_one_or_none()

    if not db_workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    update_data = workflow_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "steps" and value is not None:
            setattr(db_workflow, field, [step.dict() if hasattr(step, 'dict') else step for step in value])
        else:
            setattr(db_workflow, field, value)

    await db.commit()
    await db.refresh(db_workflow)
    return db_workflow


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    db_workflow = result.scalar_one_or_none()

    if not db_workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    await db.delete(db_workflow)
    await db.commit()
    return {"message": "工作流已删除"}


@router.post("/{workflow_id}/execute-step/")
async def execute_workflow_step(
    workflow_id: int,
    step_request: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    steps = workflow.steps or []
    step_index = step_request.get("step_index", 0)

    if step_index >= len(steps):
        raise HTTPException(status_code=400, detail="步骤索引超出范围")

    step = steps[step_index]
    step_type = step.get("type")
    step_config = step.get("config", {})
    date_str = step.get("config", {}).get("date_str") or step_config.get("date_str")

    first_step_date = None
    if step_index == 0:
        first_step_date = date_str
    else:
        for i in range(len(steps)):
            prev_config = steps[i].get("config", {})
            first_step_date = prev_config.get("date_str")
            if first_step_date:
                break

    output_date_str = first_step_date or date_str

    if not date_str:
        for i in range(step_index, -1, -1):
            prev_config = steps[i].get("config", {})
            date_str = prev_config.get("date_str")
            if date_str:
                break

    input_data = None
    if step_index > 0:
        prev_step = steps[step_index - 1]
        prev_type = prev_step.get("type")
        prev_config = prev_step.get("config", {})
        prev_output_filename = prev_config.get("output_filename")

        logger.info(f"步骤{step_index}读取上一步: type={prev_type}, prev_date={output_date_str}, current_date={date_str}")

        if prev_type == "merge_excel":
            output_filename = prev_output_filename or "total_1.xlsx"
            prev_output = os.path.join(
                workflow_executor._get_daily_dir(output_date_str),
                output_filename
            )
            logger.info(f"步骤{step_index}尝试读取merge_excel输出: {prev_output}")
            if os.path.exists(prev_output):
                df = pd.read_excel(prev_output)
                input_data = df
                logger.info(f"步骤{step_index}成功读取上一步输出: {prev_output}, 行数: {len(df)}")
            else:
                logger.warning(f"步骤{step_index}上一步输出文件不存在: {prev_output}")

        elif prev_type in ["smart_dedup", "extract_columns"]:
            if prev_type == "smart_dedup":
                prev_output = os.path.join(
                    workflow_executor._get_daily_dir(output_date_str),
                    "deduped.xlsx"
                )
            else:
                prev_output = os.path.join(
                    workflow_executor._get_daily_dir(output_date_str),
                    prev_output_filename or "output.xlsx"
                )
            logger.info(f"步骤{step_index}尝试读取{prev_type}输出: {prev_output}")
            if os.path.exists(prev_output):
                df = pd.read_excel(prev_output)
                input_data = df
                logger.info(f"步骤{step_index}成功读取上一步输出: {prev_output}, 行数: {len(df)}")
            else:
                logger.warning(f"步骤{step_index}上一步输出文件不存在: {prev_output}")

    logger.info(f"执行工作流{workflow_id}步骤{step_index}: {step_type}, config: {step_config}, date_str: {date_str}, output_date: {output_date_str}")

    result_data = await workflow_executor.execute_step(
        step_type=step_type,
        step_config=step_config,
        input_data=input_data,
        date_str=output_date_str
    )

    if not result_data.get("success", False):
        raise HTTPException(status_code=400, detail=result_data.get("message", "步骤执行失败"))

    result_data_content = result_data.get("data")
    result_rows = []
    result_columns = result_data.get("columns", [])
    if isinstance(result_data_content, list):
        result_rows = result_data_content[:100]
    elif result_data_content is not None and hasattr(result_data_content, 'to_dict'):
        import numpy as np
        df_clean = result_data_content.fillna('')
        result_rows = df_clean.head(100).to_dict('records')
        for record in result_rows:
            for k, v in record.items():
                if isinstance(v, (float, np.floating)) and (np.isnan(v) or np.isinf(v)):
                    record[k] = ''

    return {
        "message": result_data.get("message", f"步骤 {step_index + 1} 执行完成"),
        "step_index": step_index,
        "data": {
            "rows": result_data.get("rows"),
            "columns": result_columns,
            "file_path": result_data.get("file_path"),
            "records": result_rows
        }
    }


@router.post("/{workflow_id}/run/")
async def run_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    workflow.status = "running"
    await db.commit()
    await db.refresh(workflow)

    return {"message": f"工作流 {workflow_id} 已开始执行", "workflow_id": workflow_id}
