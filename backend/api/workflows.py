from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel
from datetime import datetime
import os
import glob
import shutil
import copy
import re
import pandas as pd
import asyncio
import uuid
import json
from fastapi.responses import FileResponse
from services.workflow_executor import clean_df_for_json
from core.database import get_async_db
from models.models import Workflow, BatchExecution
from api.auth import get_current_user
from models.models import User
from services.workflow_executor import workflow_executor
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

BASE_DIR = "/Users/xiayanji/qbox/aistock/data/excel" if os.path.exists("/Users/xiayanji") else "/app/data/excel"


def _extract_date_str(steps):
    """从步骤配置中提取 date_str"""
    if not steps:
        return ""
    for s in steps:
        config = s.get("config", {}) if isinstance(s, dict) else (s.config or {})
        date_str = config.get("date_str", "") if isinstance(config, dict) else getattr(config, "date_str", "")
        if date_str:
            return date_str
    return ""


async def _check_type_date_unique(db, workflow_type: str, date_str: str, exclude_id: int = None):
    """校验 workflow_type + date_str 唯一性（仅 date_str 非空时）"""
    if not date_str:
        return
    query = select(Workflow).where(
        Workflow.workflow_type == workflow_type,
        Workflow.date_str == date_str
    )
    if exclude_id is not None:
        query = query.where(Workflow.id != exclude_id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"工作流类型「{workflow_type or '并购重组'}」在 {date_str} 已存在工作流「{existing.name}」，不允许重复"
        )


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
    workflow_type: Optional[str] = ""
    steps: List[WorkflowStep]


class WorkflowUpdate(BaseModel):
    name: str = None
    description: str = None
    workflow_type: str = None
    steps: List[WorkflowStep] = None
    status: str = None
    is_active: bool = None


class WorkflowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    workflow_type: str = ""
    date_str: str = ""
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
    steps_dicts = [step.dict() for step in workflow.steps]
    date_str = _extract_date_str(steps_dicts)
    workflow_type = workflow.workflow_type or ""

    await _check_type_date_unique(db, workflow_type, date_str)

    db_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        workflow_type=workflow_type,
        date_str=date_str,
        steps=steps_dicts
    )
    db.add(db_workflow)
    await db.commit()
    await db.refresh(db_workflow)
    return db_workflow


@router.get("/types/")
async def get_workflow_types(
    current_user: User = Depends(get_current_user)
):
    from config.workflow_type_config import get_available_types
    types = get_available_types()
    return {
        "success": True,
        "types": [{"value": "", "display_name": "默认（并购重组）"}] + types
    }


@router.get("/check-data-availability/")
async def check_data_availability(
    date_str: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    """检查指定日期各工作流类型是否有最终输出数据"""
    from config.workflow_type_config import WORKFLOW_TYPE_CONFIG
    from sqlalchemy import text

    # 获取所有非聚合类型
    all_types = []
    for key, config in WORKFLOW_TYPE_CONFIG.items():
        if key and not config.get("is_aggregation"):
            all_types.append(key)

    # 查询数据库中已有的 final 结果
    result = await db.execute(text("""
        SELECT DISTINCT
            CASE WHEN workflow_type = '' THEN '并购重组' ELSE workflow_type END as wtype
        FROM workflow_results
        WHERE date_str = :date_str AND step_type = 'final'
    """), {"date_str": date_str})
    available_types = {row[0] for row in result.fetchall()}

    available = [t for t in all_types if t in available_types]
    missing = [t for t in all_types if t not in available_types]

    return {
        "date_str": date_str,
        "available": available,
        "missing": missing
    }


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Workflow).order_by(Workflow.name.asc()).offset(skip).limit(limit)
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


class BulkSetDateRequest(BaseModel):
    date_str: str


@router.put("/bulk-set-date")
async def bulk_set_date(
    payload: BulkSetDateRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """批量同步所有工作流的数据日期 (Workflow.date_str + steps[].config.date_str)"""
    date_str = (payload.date_str or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="date_str 必须为 YYYY-MM-DD 格式")

    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    updated = 0

    for wf in workflows:
        changed = False
        if wf.date_str != date_str:
            wf.date_str = date_str
            changed = True

        steps = wf.steps or []
        new_steps = []
        steps_changed = False
        for s in steps:
            if isinstance(s, dict):
                s_copy = copy.deepcopy(s)
                cfg = s_copy.get("config") or {}
                date_str_changed_in_step = False
                if cfg.get("date_str") != date_str:
                    cfg["date_str"] = date_str
                    steps_changed = True
                    date_str_changed_in_step = True
                # 条件交集：high_price_periods[*].end 同步为新日期（start 不动，
                # 实现"截至今日的滚动窗口"效果；若 end < start 会在执行时被忽略）
                hp_periods = cfg.get("high_price_periods")
                if isinstance(hp_periods, list):
                    new_periods = []
                    for p in hp_periods:
                        if isinstance(p, dict) and p.get("end") != date_str:
                            p_copy = dict(p)
                            p_copy["end"] = date_str
                            new_periods.append(p_copy)
                            steps_changed = True
                        else:
                            new_periods.append(p)
                    cfg["high_price_periods"] = new_periods
                # 趋势类（导出20日均线趋势/百日新高总趋势）：
                # preset 非 custom 时，以 date_str 为锚点重算 date_range_start/end。
                # custom 模式尊重用户手动设置的固定范围，不动。
                preset = cfg.get("date_preset")
                if preset and preset != "custom" and "date_range_end" in cfg:
                    try:
                        from datetime import datetime as _dt
                        from dateutil.relativedelta import relativedelta as _rd
                        anchor = _dt.strptime(date_str, "%Y-%m-%d")
                        delta_map = {"1m": _rd(months=1), "6m": _rd(months=6), "1y": _rd(years=1)}
                        if preset in delta_map:
                            new_start = (anchor - delta_map[preset]).strftime("%Y-%m-%d")
                            new_end = anchor.strftime("%Y-%m-%d")
                            if cfg.get("date_range_start") != new_start:
                                cfg["date_range_start"] = new_start
                                steps_changed = True
                            if cfg.get("date_range_end") != new_end:
                                cfg["date_range_end"] = new_end
                                steps_changed = True
                    except Exception as e:
                        logger.warning(f"[bulk-set-date] 趋势范围重算失败: {e}")
                # 若本 step 的 date_str 发生变化，或 output_filename / _actual_output
                # 里仍残留非当前日期的 8 位日期串（YYYYMMDD / YYYY-MM-DD），
                # 都清空——下次执行会按新 date_str 重新生成文件名。
                target_no_dash = date_str.replace("-", "")
                def _has_stale_date(val: str) -> bool:
                    if not val or not isinstance(val, str):
                        return False
                    # 任意 8 位数字连串不等于当前日期 → 视为残留旧日期
                    for m in re.finditer(r"\d{8}", val):
                        if m.group(0) != target_no_dash:
                            return True
                    # 或带连字符形式
                    for m in re.finditer(r"\d{4}-\d{2}-\d{2}", val):
                        if m.group(0) != date_str:
                            return True
                    return False
                for fname_key in ("output_filename", "_actual_output"):
                    cur = cfg.get(fname_key)
                    if cur and (date_str_changed_in_step or _has_stale_date(cur)):
                        cfg[fname_key] = ""
                        steps_changed = True
                s_copy["config"] = cfg
                new_steps.append(s_copy)
            else:
                new_steps.append(s)
        if steps_changed:
            wf.steps = new_steps
            changed = True

        if changed:
            updated += 1

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"[bulk-set-date] commit 失败: {e}")
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")

    return {"success": True, "updated_count": updated}


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

    # 确定更新后的 workflow_type 和 date_str，用于唯一性校验
    new_type = update_data.get("workflow_type", db_workflow.workflow_type) or ""
    new_steps = update_data.get("steps")
    if new_steps is not None:
        steps_dicts = [step.dict() if hasattr(step, 'dict') else step for step in new_steps]
        new_date_str = _extract_date_str(steps_dicts)
    else:
        new_date_str = db_workflow.date_str or ""

    await _check_type_date_unique(db, new_type, new_date_str, exclude_id=workflow_id)

    for field, value in update_data.items():
        if field == "steps" and value is not None:
            setattr(db_workflow, field, [step.dict() if hasattr(step, 'dict') else step for step in value])
        elif field == "workflow_type":
            from config.workflow_type_config import WORKFLOW_TYPE_CONFIG
            if value and value not in WORKFLOW_TYPE_CONFIG:
                logger.warning(f"未知的工作流类型: {value}, 将使用默认配置")
            setattr(db_workflow, field, value or "")
        else:
            setattr(db_workflow, field, value)

    # 同步 date_str
    db_workflow.date_str = new_date_str

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

    workflow_type = workflow.workflow_type or ""
    from services.workflow_executor import WorkflowExecutor
    executor_with_type = WorkflowExecutor(base_dir=BASE_DIR, workflow_type=workflow_type)

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
            output_filename = prev_output_filename or executor_with_type.resolver.get_output_filename("merge_excel", output_date_str)
            prev_output = os.path.join(
                executor_with_type._get_daily_dir(output_date_str),
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
            output_filename = prev_output_filename or executor_with_type.resolver.get_output_filename(prev_type, output_date_str)
            if output_filename:
                prev_output = os.path.join(
                    executor_with_type._get_daily_dir(output_date_str),
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

    result_data = await executor_with_type.execute_step(
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

    steps = copy.deepcopy(workflow.steps or [])
    if not steps:        raise HTTPException(status_code=400, detail="工作流无步骤")

    workflow_type = workflow.workflow_type or ""
    from services.workflow_executor import WorkflowExecutor
    executor = WorkflowExecutor(base_dir=BASE_DIR, workflow_type=workflow_type)

    first_step_date = None
    for s in steps:
        d = (s.get("config") or {}).get("date_str")
        if d:
            first_step_date = d
            break
    output_date_str = first_step_date or datetime.now().strftime("%Y-%m-%d")

    start_time = datetime.now()
    input_data = None
    step_results = []
    last_output_file = None
    last_exec_result = None  # 用于提取 stats/warnings/fail_samples

    # 最后一步（match_sector）：若未指定 output_filename 则用模板；否则尊重用户输入
    if steps and steps[-1].get("type") == "match_sector":
        cfg = steps[-1].setdefault("config", {})
        user_specified = (cfg.get("output_filename") or "").strip()
        if not user_specified:
            final_name = executor.resolver.get_output_filename("match_sector", output_date_str)
            if final_name:
                cfg["output_filename"] = final_name

    # 条件交集步骤：注入 workflow_id 到 config
    for step in steps:
        if step.get("type") == "condition_intersection":
            step.setdefault("config", {})["_workflow_id"] = workflow_id

    for i, step in enumerate(steps):
        step_type = step.get("type", "")
        step_config = step.get("config", {})

        logger.info(f"[单工作流] {workflow_id} 步骤{i}: {step_type}")
        exec_result = await executor.execute_step(
            step_type=step_type,
            step_config=step_config,
            input_data=input_data,
            date_str=output_date_str
        )

        if exec_result.get("success"):
            # 内存传递 DataFrame，避免磁盘读写
            if "_df" in exec_result and exec_result["_df"] is not None:
                input_data = exec_result["_df"]
            output_file = exec_result.get("file_path")
            if output_file:
                last_output_file = output_file
                # 保存实际输出文件名到步骤配置，供下载端点查找
                step_config["_actual_output"] = os.path.basename(output_file)
            last_exec_result = exec_result
            step_results.append({"step": i, "type": step_type, "status": "completed",
                                 "message": exec_result.get("message", "")})
        else:
            step_results.append({"step": i, "type": step_type, "status": "failed",
                                 "error": exec_result.get("message", "")})
            logger.warning(f"[单工作流] {workflow_id} 步骤{i}({step_type})失败: {exec_result.get('message')}")

    # 质押工作流 finalize：列重排 + 分 sheet + 条件格式 + 同步 public
    try:
        if last_output_file:
            executor.finalize_pledge_if_needed(last_output_file, output_date_str)
    except Exception as _e:
        logger.warning(f"[质押 finalize] run_workflow 末尾调用失败: {_e}")

    duration = round((datetime.now() - start_time).total_seconds(), 2)

    workflow.status = "active"
    workflow.last_run_time = datetime.now()
    workflow.steps = steps  # 保存实际输出文件名等运行时信息
    await db.commit()

    failed = [s for s in step_results if s["status"] == "failed"]

    # 执行成功后立刻写入数据库（is_export_only 类型跳过）
    db_saved = False
    from config.workflow_type_config import get_type_config
    type_config = get_type_config(workflow_type)
    if last_output_file and not failed and not type_config.get("is_export_only"):
        from services.workflow_result_service import save_workflow_result
        try:
            db_saved = await save_workflow_result(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                workflow_name=workflow.name,
                date_str=output_date_str,
                file_path=last_output_file,
                step_type="final"
            )
            if not db_saved:
                logger.warning(f"[单工作流] {workflow_id} save_workflow_result 返回 False")
        except Exception as e:
            logger.error(f"执行后DB写入失败: {e}")
    else:
        logger.warning(f"[单工作流] {workflow_id} 跳过DB保存: output={last_output_file}, failed={len(failed)}, export_only={type_config.get('is_export_only')}")

    # 构建最后一步的预览数据
    preview_data = []
    if input_data is not None and hasattr(input_data, 'head'):
        preview_data = clean_df_for_json(input_data)

    data_payload = {
        "rows": len(input_data) if input_data is not None and hasattr(input_data, '__len__') else 0,
        "records": preview_data,
        "file_path": last_output_file,
    }
    # 透传最后一步的结构化反馈（pledge_trend_analysis 的 stats/fail_samples；
    # condition_intersection 的 warnings 等）
    if last_exec_result is not None:
        if last_exec_result.get("stats") is not None:
            data_payload["stats"] = last_exec_result["stats"]
        if last_exec_result.get("fail_samples") is not None:
            data_payload["fail_samples"] = last_exec_result["fail_samples"]
        if last_exec_result.get("warnings") is not None:
            data_payload["warnings"] = last_exec_result["warnings"]

    return {
        "message": f"工作流执行完成，耗时{duration}秒" + (f"，{len(failed)}个步骤失败" if failed else "") + (", 结果已保存到数据库" if db_saved else ""),
        "workflow_id": workflow_id,
        "duration": duration,
        "steps": step_results,
        "output_file": last_output_file,
        "data": data_payload,
    }


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


def get_target_directory(step_type: str, date_str: Optional[str] = None, workflow_type: str = ""):
    from services.path_resolver import get_resolver

    resolver = get_resolver(BASE_DIR, workflow_type)

    if step_type in ["match_high_price", "match_ma20", "match_soe", "match_sector"]:
        return resolver.get_match_source_directory(step_type, date_str)
    else:
        return resolver.get_upload_directory(date_str)


@router.post("/upload-step-file/")
async def upload_step_file(
    workflow_id: int = Form(...),
    step_index: int = Form(...),
    step_type: str = Form(...),
    workflow_type: str = Form(""),
    date_str: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    logger.info(f"[Upload] step_type={step_type}, date_str={date_str}, filename={file.filename}")

    if not workflow_type and workflow_id:
        try:
            result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
            wf = result.scalar_one_or_none()
            if wf:
                workflow_type = wf.workflow_type or ""
        except Exception as e:
            logger.warning(f"[Upload] 获取workflow_type失败: {e}")

    target_dir = get_target_directory(step_type, date_str, workflow_type)
    logger.info(f"[Upload] target_dir={target_dir}")
    os.makedirs(target_dir, exist_ok=True)

    # 安全防御：客户端传来的 filename 可能含路径分隔符（如 Safari 的
    # webkitdirectory 会让 file.name = "0422/foo.xlsx"），也可能被
    # 恶意构造 "../../etc/passwd"。统一取 basename 剥到叶子名。
    raw_filename = file.filename or ""
    safe_filename = os.path.basename(raw_filename.replace("\\", "/"))
    if not safe_filename or safe_filename in (".", ".."):
        logger.error(f"[Upload] 非法 filename: {raw_filename!r}")
        return {"success": False, "message": f"非法文件名: {raw_filename!r}"}
    if safe_filename != raw_filename:
        logger.warning(f"[Upload] filename 含路径分隔符，剥离后 {raw_filename!r} → {safe_filename!r}")

    file_path = os.path.join(target_dir, safe_filename)
    logger.info(f"[Upload] saving to {file_path}")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)
        logger.info(f"[Upload] success, size={file_size}")

        from services.workflow_executor import invalidate_match_source_cache
        invalidate_match_source_cache(target_dir)

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
    workflow_type: str = Query(""),
    current_user: User = Depends(get_current_user)
):
    target_dir = get_target_directory(step_type, date_str, workflow_type)

    # match 步骤：自动创建目录并从历史日期复制文件
    if step_type in ["match_high_price", "match_ma20", "match_soe", "match_sector"] and date_str:
        from services.path_resolver import get_resolver
        resolver = get_resolver(BASE_DIR, workflow_type)
        target_dir = resolver.ensure_match_source_files(step_type, date_str)

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

        dir_path = os.path.dirname(file_path)
        os.remove(file_path)

        from services.workflow_executor import invalidate_match_source_cache
        invalidate_match_source_cache(dir_path)

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

    # 聚合类型（is_aggregation）排到最后执行，确保其他工作流数据最完整
    normal_ids = []
    aggregation_ids = []
    for wid in workflow_ids:
        result = await db.execute(select(Workflow).where(Workflow.id == wid))
        wf = result.scalar_one_or_none()
        from config.workflow_type_config import get_type_config as _gtc
        if wf and _gtc(wf.workflow_type or "").get("is_aggregation"):
            aggregation_ids.append(wid)
        else:
            normal_ids.append(wid)
    sorted_ids = normal_ids + aggregation_ids

    batch = BatchExecution(
        id=task_id,
        workflow_ids=sorted_ids,
        status="pending",
        total=len(sorted_ids),
        completed=0,
        failed=0,
        results=[],
        created_by=current_user.username
    )
    db.add(batch)
    await db.commit()

    asyncio.create_task(_run_batch_workflows(task_id, sorted_ids, current_user.username))

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

                steps = copy.deepcopy(workflow.steps or [])
                if not steps:
                    result_entry["status"] = "failed"
                    result_entry["error"] = "工作流无步骤"
                    return result_entry

                start_time = datetime.now()
                input_data = None

                workflow_type = workflow.workflow_type or ""

                from services.workflow_executor import WorkflowExecutor
                executor_with_type = WorkflowExecutor(base_dir=BASE_DIR, workflow_type=workflow_type)

                first_step_date = None
                for s in steps:
                    d = (s.get("config") or {}).get("date_str")
                    if d:
                        first_step_date = d
                        break
                output_date_str = first_step_date or datetime.now().strftime("%Y-%m-%d")

                # 强制用最新配置的文件名覆盖最后一步
                if steps and steps[-1].get("type") == "match_sector":
                    final_name = executor_with_type.resolver.get_output_filename("match_sector", output_date_str)
                    if final_name:
                        steps[-1].setdefault("config", {})["output_filename"] = final_name

                # 条件交集步骤：注入 workflow_id 到 config
                for step in steps:
                    if step.get("type") == "condition_intersection":
                        step.setdefault("config", {})["_workflow_id"] = wf_id

                for i, step in enumerate(steps):
                    # 每步前让出事件循环，让轮询请求得以处理
                    await asyncio.sleep(0)

                    step_type = step.get("type", "")
                    step_config = step.get("config", {})
                    step_date_str = step_config.get("date_str") or output_date_str

                    step_result = {"step_index": i, "type": step_type, "status": "running"}
                    try:
                        logger.info(f"[批量] 工作流{wf_id} 执行步骤{i}: {step_type}, date={step_date_str}, type={workflow_type}")

                        exec_result = await executor_with_type.execute_step(
                            step_type=step_type,
                            step_config=step_config,
                            input_data=input_data,
                            date_str=output_date_str
                        )

                        if exec_result.get("success"):
                            step_result["status"] = "completed"
                            step_result["message"] = exec_result.get("message", "")

                            # 优先使用内存中的 DataFrame，避免磁盘读写
                            if "_df" in exec_result and exec_result["_df"] is not None:
                                input_data = exec_result["_df"]
                            else:
                                output_file = exec_result.get("file_path")
                                if output_file and os.path.exists(output_file):
                                    try:
                                        input_data = await loop.run_in_executor(None, pd.read_excel, output_file)
                                    except Exception as read_err:
                                        logger.warning(f"[批量] 读取输出文件失败: {read_err}")

                            output_file = exec_result.get("file_path")
                            if output_file:
                                step_result["output_file"] = output_file
                                step_config["_actual_output"] = os.path.basename(output_file)
                                if i == len(steps) - 1:
                                    result_entry["output_file"] = output_file
                        else:
                            step_result["status"] = "failed"
                            step_result["error"] = exec_result.get("message", "执行失败")

                    except Exception as e:
                        step_result["status"] = "failed"
                        step_result["error"] = str(e)

                    result_entry["steps"].append(step_result)

                end_time = datetime.now()
                duration = round((end_time - start_time).total_seconds(), 2)

                failed_steps = [s for s in result_entry["steps"] if s.get("status") == "failed"]
                if failed_steps:
                    result_entry["status"] = "partial" if len(failed_steps) < len(result_entry["steps"]) else "failed"
                    result_entry["error"] = f"{len(failed_steps)}个步骤失败"
                else:
                    result_entry["status"] = "completed"

                # 质押工作流 finalize：列重排 + 分 sheet + 条件格式 + 同步 public
                # 必须在 save_workflow_result 之前，否则 DB 存的还是 finalize 前的单 sheet 文件
                try:
                    if result_entry["output_file"]:
                        executor_with_type.finalize_pledge_if_needed(result_entry["output_file"], output_date_str)
                except Exception as _e:
                    logger.warning(f"[批量] 工作流{wf_id} 质押 finalize 失败: {_e}")

                # 执行成功后写入 workflow_results（is_export_only 类型跳过）
                from config.workflow_type_config import get_type_config as _get_tc
                _tc = _get_tc(workflow_type)
                if result_entry["output_file"] and result_entry["status"] == "completed" and not _tc.get("is_export_only"):
                    from services.workflow_result_service import save_workflow_result
                    try:
                        await save_workflow_result(
                            workflow_id=wf_id,
                            workflow_type=workflow_type,
                            workflow_name=workflow.name,
                            date_str=output_date_str,
                            file_path=result_entry["output_file"],
                            step_type="final"
                        )
                    except Exception as e:
                        logger.error(f"[批量] 工作流{wf_id} DB写入失败: {e}")

                result_entry["duration"] = duration
                result_entry["step_count"] = len(steps)

                workflow.status = "active"
                workflow.last_run_time = datetime.now()
                workflow.steps = steps  # 保存 _actual_output 等运行时信息
                await db.commit()

        except Exception as e:
            result_entry["status"] = "failed"
            result_entry["error"] = str(e)
            logger.error(f"[批量] 工作流{wf_id}整体异常: {e}")

        # 完成后返回结果（进度更新由外层处理）
        return result_entry

    # 顺序执行，每完成一个立即更新进度（pandas是CPU阻塞的，gather无真正并行）
    from core.database import AsyncSessionLocal
    for wid in workflow_ids:
        result_entry = await run_single(wid)
        results.append(result_entry)

        # 立即更新 batch 进度
        async with AsyncSessionLocal() as batch_db:
            batch = await batch_db.get(BatchExecution, task_id)
            if batch:
                batch.results = list(results)
                batch.completed = sum(1 for r in results if r.get("status") in ("completed", "partial"))
                batch.failed = sum(1 for r in results if r.get("status") == "failed")
                await batch_db.commit()

        # 让出事件循环，让轮询请求得以处理
        await asyncio.sleep(0)

    # 全部完成，标记最终状态
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        batch = await db.get(BatchExecution, task_id)
        if batch:
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
    # 强制从DB刷新，不用session缓存（后台任务用独立session写入）
    await db.refresh(batch)

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


@router.get("/batch-download/{task_id}")
async def batch_download_results(
    task_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    import zipfile
    import io

    batch = await db.get(BatchExecution, task_id)
    if not batch:
        raise HTTPException(status_code=404, detail="批次任务不存在")

    if batch.status not in ['completed', 'partial']:
        raise HTTPException(status_code=400, detail="批次任务尚未完成")

    # 创建内存中的zip文件
    zip_buffer = io.BytesIO()
    files_to_clean = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for result in batch.results:
            workflow_id = result.get('workflow_id')
            output_file = result.get('output_file')

            if output_file and os.path.exists(output_file):
                arcname = f"workflow_{workflow_id}_{os.path.basename(output_file)}"
                zip_file.write(output_file, arcname)
                files_to_clean.append(output_file)

    zip_buffer.seek(0)

    # zip已读入内存，立即删除源文件（数据已存入DB）
    for f in files_to_clean:
        try:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"批量下载后清理: {f}")
        except Exception as e:
            logger.warning(f"清理文件失败: {f}, {e}")

    # 返回zip文件
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=batch_{task_id}.zip",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        }
    )


@router.get("/download-result/{workflow_id}")
async def download_workflow_result(
    workflow_id: int,
    background_tasks: BackgroundTasks,
    step_index: int = Query(None),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")

    steps = workflow.steps or []
    workflow_type = workflow.workflow_type or ""

    from services.workflow_executor import WorkflowExecutor
    executor_with_type = WorkflowExecutor(base_dir=BASE_DIR, workflow_type=workflow_type)

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
        step_type = step.get("type")
        daily_dir = executor_with_type._get_daily_dir(output_date_str)

        # 优先 _actual_output（运行时实际文件名），再 resolver，再 config
        auto_filename = executor_with_type.resolver.get_output_filename(step_type, output_date_str)
        output_filename = step_config.get("output_filename")
        actual_output = step_config.get("_actual_output")

        file_path = None
        for fname in [actual_output, auto_filename, output_filename]:
            if fname:
                candidate = os.path.join(daily_dir, fname)
                if os.path.exists(candidate):
                    file_path = candidate
                    break
        if not file_path:
            raise HTTPException(status_code=404, detail="未找到结果文件")
    else:
        file_path = None
        daily_dir = executor_with_type._get_daily_dir(output_date_str)
        for i in range(len(steps) - 1, -1, -1):
            step = steps[i]
            step_type = step.get("type")
            step_config = step.get("config", {})

            # 优先 _actual_output（运行时实际文件名）
            actual_output = step_config.get("_actual_output")
            if actual_output:
                candidate_path = os.path.join(daily_dir, actual_output)
                if os.path.exists(candidate_path):
                    file_path = candidate_path
                    break

            # 再用 resolver 最新配置的文件名（避免旧配置和实际文件不一致）
            auto_filename = executor_with_type.resolver.get_output_filename(step_type, output_date_str)
            if auto_filename:
                candidate_path = os.path.join(daily_dir, auto_filename)
                if os.path.exists(candidate_path):
                    file_path = candidate_path
                    break

            # 再试步骤配置里存的文件名
            output_filename = step_config.get("output_filename")
            if output_filename:
                candidate_path = os.path.join(daily_dir, output_filename)
                if os.path.exists(candidate_path):
                    file_path = candidate_path
                    break

        if not file_path:
            raise HTTPException(status_code=404, detail="未找到结果文件")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    # 收集所有步骤生成的文件路径，下载后全部清理
    generated_files = set()
    daily_dir = executor_with_type._get_daily_dir(output_date_str)
    try:
        public_dir = executor_with_type.resolver.get_public_directory(output_date_str)
    except (ValueError, KeyError):
        public_dir = None
    for step in steps:
        step_type = step.get("type")
        step_config = step.get("config", {})
        for key in ["output_filename", "_actual_output"]:
            fname = step_config.get(key)
            if fname:
                fpath = os.path.join(daily_dir, fname)
                if public_dir is None or not fpath.startswith(public_dir):
                    generated_files.add(fpath)
        auto_fname = executor_with_type.resolver.get_output_filename(step_type, output_date_str)
        if auto_fname:
            fpath = os.path.join(daily_dir, auto_fname)
            if public_dir is None or not fpath.startswith(public_dir):
                generated_files.add(fpath)
    # 最终文件也加入清理（数据已存入DB），但排除 public 目录
    if public_dir is None or not file_path.startswith(public_dir):
        generated_files.add(file_path)

    # 复制到临时文件用于下载，避免传输中被删
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, os.path.basename(file_path))
    shutil.copy2(file_path, tmp_path)

    def cleanup_all():
        for gf in generated_files:
            try:
                if os.path.exists(gf):
                    os.remove(gf)
                    logger.info(f"下载后清理: {gf}")
            except Exception as e:
                logger.warning(f"清理文件失败: {gf}, {e}")
        # 清理临时文件
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    background_tasks.add_task(cleanup_all)

    return FileResponse(
        path=tmp_path,
        filename=os.path.basename(file_path),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        }
    )


PUBLIC_DIR = os.path.join(BASE_DIR, "2025public")


@router.get("/public-files/")
async def get_public_files(
    workflow_type: str = Query(""),
    date_str: str = Query(""),
    current_user: User = Depends(get_current_user)
):
    if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise HTTPException(status_code=400, detail="date_str 格式无效，需要 YYYY-MM-DD")
    from services.path_resolver import get_resolver
    resolver = get_resolver(BASE_DIR, workflow_type)
    try:
        public_dir = resolver.get_public_directory(date_str or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    os.makedirs(public_dir, exist_ok=True)

    excel_files = []
    for ext in ["*.xlsx", "*.xls"]:
        pattern = os.path.join(public_dir, ext)
        for file_path in glob.glob(pattern):
            stat = os.stat(file_path)
            excel_files.append({
                "filename": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

    excel_files.sort(key=lambda x: x["modified_time"], reverse=True)
    return {"success": True, "files": excel_files, "directory": public_dir}


@router.post("/public-files/upload/")
async def upload_public_file(
    file: UploadFile = File(...),
    workflow_type: str = Form(""),
    date_str: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise HTTPException(status_code=400, detail="date_str 格式无效，需要 YYYY-MM-DD")
    from services.path_resolver import get_resolver
    resolver = get_resolver(BASE_DIR, workflow_type)
    try:
        public_dir = resolver.get_public_directory(date_str or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    os.makedirs(public_dir, exist_ok=True)
    file_path = os.path.join(public_dir, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)

        from services.workflow_executor import invalidate_public_cache
        invalidate_public_cache(public_dir)

        return {
            "success": True,
            "message": f"文件上传成功",
            "file": {
                "filename": file.filename,
                "path": file_path,
                "size": file_size,
                "target_dir": public_dir
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

        dir_path = os.path.dirname(file_path)
        os.remove(file_path)

        from services.workflow_executor import invalidate_public_cache, invalidate_match_source_cache
        invalidate_public_cache(dir_path)
        invalidate_match_source_cache(dir_path)

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
