from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel
from datetime import datetime
import os
import glob
import shutil
import pandas as pd
import asyncio
import uuid
import json
from fastapi.responses import FileResponse
from core.database import get_async_db
from models.models import Workflow, BatchExecution
from api.auth import get_current_user
from models.models import User
from services.workflow_executor import workflow_executor
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = "/Users/xiayanji/qbox/aistock/data/excel" if os.path.exists("/Users/xiayanji") else "/app/data/excel"


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

        elif prev_type in ["smart_dedup", "extract_columns", "match_high_price", "match_ma20", "match_soe", "match_sector"]:
            fixed_output_map = {
                "smart_dedup": "deduped.xlsx",
            }
            if prev_type in fixed_output_map:
                output_filename = fixed_output_map[prev_type]
            else:
                type_defaults = {
                    "match_high_price": "output_3.xlsx",
                    "match_ma20": "output_4.xlsx",
                    "match_soe": "output_5.xlsx",
                    "extract_columns": "output_2.xlsx",
                }
                output_filename = prev_output_filename or type_defaults.get(prev_type, "output.xlsx")
            if output_filename:
                prev_output = os.path.join(
                    workflow_executor._get_daily_dir(output_date_str),
                    output_filename
                )
                logger.info(f"步骤{step_index}尝试读取{prev_type}输出: {prev_output}")
                if os.path.exists(prev_output):
                    df = pd.read_excel(prev_output)
                    input_data = df
                    logger.info(f"步骤{step_index}成功读取上一步输出: {prev_output}, 行数: {len(df)}")
                else:
                    logger.warning(f"步骤{step_index}上一步输出文件不存在: {prev_output}")
            else:
                logger.warning(f"步骤{step_index}上一步({prev_type})无输出文件配置，跳过数据传递")

    logger.info(f"执行工作流{workflow_id}步骤{step_index}: {step_type}, config: {step_config}, date_str: {date_str}, output_date: {output_date_str}")
    logger.info(f"步骤{step_index}输入数据: {'None' if input_data is None else f'DataFrame({len(input_data)}行)'}")

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


from pydantic import BaseModel

class OpenDirectoryRequest(BaseModel):
    path: str


@router.post("/open-directory")
async def open_directory(
    request: OpenDirectoryRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        if os.path.exists(request.path):
            return {"success": True, "message": f"目录存在: {request.path}"}
        else:
            return {"success": False, "message": f"目录不存在: {request.path}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


class StepFileUploadRequest(BaseModel):
    workflow_id: int
    step_index: int
    step_type: str


def get_target_directory(step_type: str, date_str: Optional[str] = None) -> str:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    if step_type == "merge_excel":
        return os.path.join(BASE_DIR, date_str)
    elif step_type == "match_high_price":
        return os.path.join(BASE_DIR, "百日新高")
    elif step_type == "match_ma20":
        return os.path.join(BASE_DIR, "20日均线")
    elif step_type == "match_soe":
        return os.path.join(BASE_DIR, "国企")
    elif step_type == "match_sector":
        return os.path.join(BASE_DIR, "一级板块")
    else:
        return os.path.join(BASE_DIR, date_str)


@router.post("/upload-step-file/")
async def upload_step_file(
    workflow_id: int = Form(...),
    step_index: int = Form(...),
    step_type: str = Form(...),
    date_str: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"[Upload] step_type={step_type}, date_str={date_str}, filename={file.filename}")
    target_dir = get_target_directory(step_type, date_str)
    logger.info(f"[Upload] target_dir={target_dir}")
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, file.filename)
    logger.info(f"[Upload] saving to {file_path}")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)
        logger.info(f"[Upload] success, size={file_size}")
        return {
            "success": True,
            "message": f"文件上传成功",
            "file": {
                "filename": file.filename,
                "path": file_path,
                "size": file_size,
                "target_dir": target_dir
            }
        }
    except Exception as e:
        logger.error(f"[Upload] failed: {str(e)}")
        return {"success": False, "message": f"上传失败: {str(e)}"}


@router.get("/step-files/")
async def get_step_files(
    step_type: str = Query(...),
    date_str: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    target_dir = get_target_directory(step_type, date_str)

    if not os.path.exists(target_dir):
        return {"success": True, "files": [], "directory": target_dir}

    excel_files = []
    for ext in ["*.xlsx", "*.xls"]:
        pattern = os.path.join(target_dir, ext)
        for file_path in glob.glob(pattern):
            stat = os.stat(file_path)
            excel_files.append({
                "filename": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

    excel_files.sort(key=lambda x: x["modified_time"], reverse=True)
    return {"success": True, "files": excel_files, "directory": target_dir}


@router.delete("/step-files/")
async def delete_step_file(
    file_path: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    try:
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        os.remove(file_path)
        return {"success": True, "message": "文件已删除"}
    except Exception as e:
        return {"success": False, "message": f"删除失败: {str(e)}"}


@router.get("/step-files/preview")
async def preview_step_file(
    file_path: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    try:
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        df = pd.read_excel(file_path)
        records = df.head(20).fillna('').to_dict('records')
        columns = df.columns.tolist()

        return {
            "success": True,
            "filename": os.path.basename(file_path),
            "total_rows": len(df),
            "columns": columns,
            "preview": records
        }
    except Exception as e:
        return {"success": False, "message": f"预览失败: {str(e)}"}


class BatchRunRequest(BaseModel):
    workflow_ids: List[int]


@router.post("/batch-run/")
async def batch_run_workflows(
    request: BatchRunRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    task_id = f"batch_{uuid.uuid4().hex[:12]}"
    workflow_ids = request.workflow_ids

    batch = BatchExecution(
        id=task_id,
        workflow_ids=workflow_ids,
        status="pending",
        total=len(workflow_ids),
        completed=0,
        failed=0,
        results=[],
        created_by=current_user.username
    )
    db.add(batch)
    await db.commit()

    asyncio.create_task(_run_batch_workflows(task_id, workflow_ids, current_user.username))

    return {
        "success": True,
        "task_id": task_id,
        "message": f"已启动 {len(workflow_ids)} 个工作流的并行执行"
    }


async def _run_batch_workflows(task_id: str, workflow_ids: list, username: str):
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        batch = await db.get(BatchExecution, task_id)
        if not batch:
            return
        batch.status = "running"
        batch.started_at = datetime.now()
        await db.commit()

    results = []

    async def run_single(wf_id):
        from core.database import AsyncSessionLocal
        import pandas as pd
        loop = asyncio.get_running_loop()
        result_entry = {"workflow_id": wf_id, "status": "pending", "error": None, "output_file": None, "steps": []}

        try:
            async with AsyncSessionLocal() as db:
                wf_result = await db.execute(select(Workflow).where(Workflow.id == wf_id))
                workflow = wf_result.scalar_one_or_none()
                if not workflow:
                    result_entry["status"] = "failed"
                    result_entry["error"] = "工作流不存在"
                    return result_entry

                steps = workflow.steps or []
                if not steps:
                    result_entry["status"] = "failed"
                    result_entry["error"] = "工作流无步骤"
                    return result_entry

                start_time = datetime.now()
                input_data = None

                first_step_date = None
                for s in steps:
                    d = (s.get("config") or {}).get("date_str")
                    if d:
                        first_step_date = d
                        break
                output_date_str = first_step_date or datetime.now().strftime("%Y-%m-%d")

                for i, step in enumerate(steps):
                    step_type = step.get("type", "")
                    step_config = step.get("config", {})
                    step_date_str = step_config.get("date_str") or output_date_str

                    step_result = {"step_index": i, "type": step_type, "status": "running"}
                    try:
                        logger.info(f"[批量] 工作流{wf_id} 执行步骤{i}: {step_type}, date={step_date_str}")

                        exec_result = await workflow_executor.execute_step(
                            step_type=step_type,
                            step_config=step_config,
                            input_data=input_data,
                            date_str=output_date_str
                        )

                        if exec_result.get("success"):
                            step_result["status"] = "completed"
                            step_result["message"] = exec_result.get("message", "")

                            output_file = exec_result.get("file_path")
                            if output_file and os.path.exists(output_file):
                                try:
                                    input_data = await loop.run_in_executor(None, pd.read_excel, output_file)
                                    logger.info(f"[批量] 工作流{wf_id} 步骤{i} 从文件读取完整数据: {output_file}, {len(input_data)}行")
                                except Exception as read_err:
                                    logger.warning(f"[批量] 读取输出文件失败: {read_err}, 回退到data字段")
                                    result_data = exec_result.get("data")
                                    if isinstance(result_data, list) and len(result_data) > 0:
                                        input_data = await loop.run_in_executor(None, pd.DataFrame, result_data)
                            else:
                                result_data = exec_result.get("data")
                                if isinstance(result_data, list) and len(result_data) > 0:
                                    input_data = await loop.run_in_executor(None, pd.DataFrame, result_data)
                                elif hasattr(result_data, 'to_dict'):
                                    input_data = result_data

                            if output_file:
                                step_result["output_file"] = output_file
                                if i == len(steps) - 1:
                                    result_entry["output_file"] = output_file
                        else:
                            step_result["status"] = "failed"
                            step_result["error"] = exec_result.get("message", "执行失败")
                            logger.warning(f"[批量] 工作流{wf_id} 步骤{i}({step_type})失败: {step_result['error']}")

                    except Exception as e:
                        step_result["status"] = "failed"
                        step_result["error"] = str(e)
                        logger.error(f"[批量] 工作流{wf_id} 步骤{i}({step_type})异常: {e}")

                    result_entry["steps"].append(step_result)

                end_time = datetime.now()
                duration = round((end_time - start_time).total_seconds(), 2)

                failed_steps = [s for s in result_entry["steps"] if s.get("status") == "failed"]
                if failed_steps:
                    result_entry["status"] = "partial" if len(failed_steps) < len(result_entry["steps"]) else "failed"
                    result_entry["error"] = f"{len(failed_steps)}个步骤失败"
                else:
                    result_entry["status"] = "completed"

                result_entry["duration"] = duration
                result_entry["step_count"] = len(steps)

                workflow.status = "active"
                workflow.last_run_time = datetime.now()
                await db.commit()

        except Exception as e:
            result_entry["status"] = "failed"
            result_entry["error"] = str(e)
            logger.error(f"[批量] 工作流{wf_id}整体异常: {e}")

        return result_entry

    tasks = [run_single(wid) for wid in workflow_ids]
    completed_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in completed_results:
        if isinstance(r, Exception):
            results.append({"workflow_id": 0, "status": "failed", "error": str(r), "steps": []})
        else:
            results.append(r)

    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        batch = await db.get(BatchExecution, task_id)
        if batch:
            batch.results = results
            batch.completed = sum(1 for r in results if r.get("status") in ("completed", "partial"))
            batch.failed = sum(1 for r in results if r.get("status") == "failed")
            batch.finished_at = datetime.now()

            if batch.failed == 0:
                batch.status = "completed"
            elif batch.completed > 0:
                batch.status = "partial"
            else:
                batch.status = "failed"

            await db.commit()


@router.get("/batch-status/{task_id}/")
async def get_batch_status(
    task_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    batch = await db.get(BatchExecution, task_id)
    if not batch:
        raise HTTPException(status_code=404, detail="批次任务不存在")

    response = {
        "task_id": batch.id,
        "status": batch.status,
        "workflow_ids": batch.workflow_ids,
        "total": batch.total,
        "completed": batch.completed,
        "failed": batch.failed,
        "results": batch.results or [],
        "started_at": batch.started_at.isoformat() if batch.started_at else None,
        "finished_at": batch.finished_at.isoformat() if batch.finished_at else None
    }
    
    return response


@router.get("/download-result/{workflow_id}")
async def download_workflow_result(
    workflow_id: int,
    step_index: int = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    steps = workflow.steps or []

    output_date_str = None
    for i in range(len(steps)):
        sd = steps[i].get("config", {}).get("date_str")
        if sd:
            output_date_str = sd
            break
    if not output_date_str:
        output_date_str = datetime.now().strftime("%Y-%m-%d")

    if step_index is not None and step_index < len(steps):
        step = steps[step_index]
        step_config = step.get("config", {})
        output_filename = step_config.get("output_filename")

        if output_filename:
            file_path = os.path.join(BASE_DIR, output_date_str, output_filename)
        else:
            target_dir = get_target_directory(step.get("type"), output_date_str)
            files = glob.glob(os.path.join(target_dir, "*.xlsx"))
            if files:
                file_path = sorted(files)[-1]
            else:
                raise HTTPException(status_code=404, detail="未找到结果文件")
    else:
        for i in range(len(steps) - 1, -1, -1):
            step = steps[i]
            step_type = step.get("type")
            step_config = step.get("config", {})
            output_filename = step_config.get("output_filename")

            if output_filename:
                candidate_path = os.path.join(BASE_DIR, output_date_str, output_filename)
                if os.path.exists(candidate_path):
                    file_path = candidate_path
                    break
            else:
                target_dir = get_target_directory(step_type, output_date_str)
                files = glob.glob(os.path.join(target_dir, "*.xlsx"))
                if files:
                    file_path = sorted(files)[-1]
                    break
        else:
            raise HTTPException(status_code=404, detail="未找到结果文件")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


PUBLIC_DIR = os.path.join(BASE_DIR, "2025public")


@router.get("/public-files/")
async def get_public_files(
    current_user: User = Depends(get_current_user)
):
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    excel_files = []
    for ext in ["*.xlsx", "*.xls"]:
        pattern = os.path.join(PUBLIC_DIR, ext)
        for file_path in glob.glob(pattern):
            stat = os.stat(file_path)
            excel_files.append({
                "filename": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

    excel_files.sort(key=lambda x: x["modified_time"], reverse=True)
    return {"success": True, "files": excel_files, "directory": PUBLIC_DIR}


@router.post("/public-files/upload/")
async def upload_public_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    os.makedirs(PUBLIC_DIR, exist_ok=True)
    file_path = os.path.join(PUBLIC_DIR, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)
        return {
            "success": True,
            "message": f"文件上传成功",
            "file": {
                "filename": file.filename,
                "path": file_path,
                "size": file_size,
                "target_dir": PUBLIC_DIR
            }
        }
    except Exception as e:
        logger.error(f"[Public Upload] failed: {str(e)}")
        return {"success": False, "message": f"上传失败: {str(e)}"}


@router.delete("/public-files/")
async def delete_public_file(
    file_path: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    try:
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        os.remove(file_path)
        return {"success": True, "message": "文件已删除"}
    except Exception as e:
        return {"success": False, "message": f"删除失败: {str(e)}"}


@router.get("/public-files/preview")
async def preview_public_file(
    file_path: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    try:
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        df = pd.read_excel(file_path, skiprows=1)
        records = df.head(20).fillna('').to_dict('records')
        columns = df.columns.tolist()

        return {
            "success": True,
            "filename": os.path.basename(file_path),
            "total_rows": len(df),
            "columns": columns,
            "preview": records
        }
    except Exception as e:
        logger.error(f"[Preview] failed: {str(e)}")
        return {"success": False, "message": f"预览失败: {str(e)}"}
