import os
import logging
import tempfile
import shutil
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, field_validator
import re

from models.models import User
from api.auth import get_current_user
from services.trend_service import (
    save_trend_data, get_trend_data, delete_trend_data,
    parse_excel_for_trend, batch_save_trend_data
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TrendDataInput(BaseModel):
    metric_type: str = "ma20"
    workflow_type: str
    date_str: str
    count: int
    total: int

    @field_validator('date_str')
    @classmethod
    def validate_date(cls, v):
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('日期格式必须为 YYYY-MM-DD')
        return v


class TrendRecord(BaseModel):
    workflow_type: str
    date_str: str
    count: int
    total: int


class BatchInput(BaseModel):
    metric_type: str = "ma20"
    source: str = "excel"
    records: List[TrendRecord]


@router.get("/trend-data/")
async def query_trend_data(
    metric_type: str = Query("ma20"),
    workflow_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    data = await get_trend_data(metric_type, workflow_type, start_date, end_date)
    return {"success": True, "data": data}


@router.post("/trend-data/")
async def create_trend_data(
    input_data: TrendDataInput,
    current_user: User = Depends(get_current_user)
):
    ok = await save_trend_data(
        metric_type=input_data.metric_type,
        workflow_type=input_data.workflow_type,
        date_str=input_data.date_str,
        count=input_data.count,
        total=input_data.total,
        source="manual",
    )
    if not ok:
        raise HTTPException(status_code=500, detail="保存失败")
    return {"success": True, "message": "已保存"}


@router.post("/trend-data/batch")
async def batch_create_trend_data(
    input_data: BatchInput,
    current_user: User = Depends(get_current_user)
):
    saved = await batch_save_trend_data(input_data.metric_type, [r.model_dump() for r in input_data.records], input_data.source)
    return {"success": True, "message": f"成功保存{saved}条", "saved": saved}


@router.post("/trend-data/upload")
async def upload_trend_excel(
    workflow_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        records = parse_excel_for_trend(tmp_path, workflow_type)
        return {"success": True, "records": records, "count": len(records)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"解析Excel失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.delete("/trend-data/{record_id}")
async def remove_trend_data(
    record_id: int,
    current_user: User = Depends(get_current_user)
):
    ok = await delete_trend_data(record_id)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"success": True, "message": "已删除"}
