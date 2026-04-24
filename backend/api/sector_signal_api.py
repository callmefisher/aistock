"""板块信号榜 API（独立路由模块）。

路由前缀：/api/sector-signal
端点：
  GET  /                    查询榜单（缓存命中 / 未命中实时计算）
  POST /recompute           强制重算
  GET  /history             历史查询（单板块时序 / 榜单成分）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config.sector_signal_config import TOP_N_CHOICES, TOP_N_DEFAULT
from models.models import User
from models.sector_signal_model import SectorSignal  # noqa: F401  强制注册到 Base
from services import sector_signal_service as sig_svc
from services.sector_signal_service import (
    InsufficientHistory, SectorNotFound, SourceFileMissing,
)
from utils.beijing_time import beijing_today_str

router = APIRouter()


class RecomputeBody(BaseModel):
    date: str


@router.get("/")
async def get_sector_signal(
    date: Optional[str] = None,
    top_n: int = TOP_N_DEFAULT,
    current_user: User = Depends(get_current_user),
):
    if top_n not in TOP_N_CHOICES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_TOP_N", "message": f"top_n 必须是 {sorted(TOP_N_CHOICES)} 之一"})

    if date is None:
        date = sig_svc.find_latest_date_with_source()
        if date is None:
            raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": "无可用的 public 文件"})
    else:
        try:
            parsed = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "日期格式错误（YYYY-MM-DD）"})
        if parsed.isoformat() > beijing_today_str():
            raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "不能查询未来日期"})

    try:
        result = await sig_svc.get_or_compute(date)
    except SourceFileMissing as e:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": str(e)})
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail={"code": "INSUFFICIENT_HISTORY", "message": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("compute_failed")
        raise HTTPException(status_code=500, detail={"code": "COMPUTE_FAILED", "message": str(e)})

    return {
        **result,
        "top_strong": result["top_strong"][:top_n],
        "top_reversal": result["top_reversal"][:top_n],
    }


@router.post("/recompute")
async def recompute_sector_signal(
    body: RecomputeBody,
    current_user: User = Depends(get_current_user),
):
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "INVALID_DATE", "message": "日期格式错误"})
    try:
        return await sig_svc.recompute(body.date)
    except SourceFileMissing as e:
        raise HTTPException(status_code=404, detail={"code": "SOURCE_FILE_MISSING", "message": str(e)})
    except InsufficientHistory as e:
        raise HTTPException(status_code=422, detail={"code": "INSUFFICIENT_HISTORY", "message": str(e)})


@router.get("/history")
async def get_sector_signal_history(
    sector: Optional[str] = None,
    days: int = 30,
    board: str = "strong",
    current_user: User = Depends(get_current_user),
):
    if not (1 <= days <= 180):
        raise HTTPException(status_code=400, detail={"code": "INVALID_DAYS", "message": "days 必须在 1-180"})
    if board not in {"strong", "reversal"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_BOARD", "message": "board 必须是 strong 或 reversal"})
    if sector:
        try:
            return await sig_svc.load_sector_history(sector, days)
        except SectorNotFound as e:
            raise HTTPException(status_code=404, detail={"code": "SECTOR_NOT_FOUND", "message": str(e)})
    return await sig_svc.load_board_history(board, days, top_n=10)
