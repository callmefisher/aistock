from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from typing import Optional
from api.auth import get_current_user
from models.models import User
from services import workflow_result_service as svc
import tempfile
import os
import json

router = APIRouter()


@router.get("/results/grouped")
async def get_results_grouped(
    current_user: User = Depends(get_current_user)
):
    grouped = await svc.get_results_grouped()
    return {"success": True, "data": grouped}


@router.get("/results/ranking-analysis")
async def get_ranking_analysis(
    result_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """返回涨幅排名完整数据供板块涨幅分析Tab使用"""
    grouped = await svc.get_results_grouped()
    ranking_list = grouped.get("涨幅排名", [])
    if not ranking_list:
        return {"success": True, "data": None, "available": []}

    available = [
        {"id": r["id"], "date_str": r["date_str"], "workflow_name": r["workflow_name"]}
        for r in ranking_list
    ]

    valid_ids = {r["id"] for r in ranking_list}
    target_id = result_id if result_id and result_id in valid_ids else ranking_list[0]["id"]
    full = await svc.get_result_full(target_id)
    if not full:
        return {"success": True, "data": None, "available": available}

    return {"success": True, "data": full, "available": available}


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


@router.get("/results/{result_id}/download")
async def download_result(
    result_id: int,
    current_user: User = Depends(get_current_user)
):
    """下载格式化 Excel，涨幅排名类型应用专属格式"""
    result = await svc.get_result_full(result_id)
    if not result:
        raise HTTPException(status_code=404, detail="结果不存在")

    import pandas as pd
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    df = pd.DataFrame(result['data'])
    filename = result.get('source_filename') or f"{result['workflow_name']}_{result['date_str']}.xlsx"
    if not filename.endswith('.xlsx'):
        filename += '.xlsx'

    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()

    # 质押类型：直接复制 public 目录下的 final 文件（含双 sheet / 条件格式 / 列宽 / 筛选），
    # 然后用 stock_pools 全局最大公告日重做"最新公告日"红标。
    if result.get('workflow_type') == '质押':
        import shutil
        from services.path_resolver import get_resolver
        from core.config import settings
        base_dir = os.path.join(settings.DATA_DIR, "excel") if hasattr(settings, "DATA_DIR") else None
        # 兜底：尝试两种常见 base_dir
        for candidate in (base_dir, "/app/data/excel", "/Users/xiayanji/qbox/aistock/data/excel"):
            if candidate and os.path.isdir(candidate):
                base_dir = candidate
                break
        resolver = get_resolver(base_dir, "质押")
        public_dir = resolver.get_public_directory(result.get('date_str'))
        # 优先按 source_filename 命中；否则取 public 目录下第一个 xlsx
        src_path = None
        sf = result.get('source_filename')
        if sf:
            cand = os.path.join(public_dir, sf)
            if os.path.isfile(cand):
                src_path = cand
        if not src_path and os.path.isdir(public_dir):
            for f in os.listdir(public_dir):
                if f.lower().endswith('.xlsx'):
                    src_path = os.path.join(public_dir, f)
                    break
        if not src_path:
            raise HTTPException(status_code=404, detail=f"质押 public 文件不存在: {public_dir}")

        shutil.copy2(src_path, tmp_path)

        # baseline：查 workflow_results 表中质押类型、date_str < 当前结果 date_str 的
        # 所有 final 记录，解压 data_compressed，取所有行"最新公告日"的最大值。
        # stock_pools 表不参与（它是条件交集的选股池，不含纯质押历史）。
        import zlib
        from sqlalchemy import text
        max_ts = None
        try:
            from core.database import SyncSessionLocal
            current_date_str = result.get('date_str')
            db = SyncSessionLocal()
            try:
                if current_date_str:
                    rows = db.execute(text("""
                        SELECT data_compressed FROM workflow_results
                        WHERE workflow_type = :wt
                          AND step_type = 'final'
                          AND date_str < :dt
                        ORDER BY date_str DESC
                    """), {"wt": "质押", "dt": current_date_str}).fetchall()
                    for row in rows:
                        raw = row[0]
                        if not raw:
                            continue
                        try:
                            records = json.loads(zlib.decompress(raw).decode("utf-8"))
                        except Exception:
                            continue
                        if not isinstance(records, list):
                            continue
                        for rec in records:
                            if not isinstance(rec, dict):
                                continue
                            dv = rec.get("最新公告日")
                            if not dv:
                                continue
                            try:
                                ts = pd.to_datetime(dv, errors="coerce")
                                if pd.isna(ts):
                                    continue
                            except Exception:
                                continue
                            if max_ts is None or ts > max_ts:
                                max_ts = ts
            finally:
                db.close()
        except Exception:
            max_ts = None

        # 施加红标（stock_pools 空 → 不标）
        if max_ts is not None:
            wb = load_workbook(tmp_path)
            red_fill = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                header = [c.value for c in ws[1]]
                if "最新公告日" not in header:
                    continue
                date_col = header.index("最新公告日") + 1
                for row in range(2, ws.max_row + 1):
                    date_val = ws.cell(row, date_col).value
                    if not date_val:
                        continue
                    try:
                        ts = pd.to_datetime(date_val, errors="coerce")
                        if pd.isna(ts):
                            continue
                    except Exception:
                        continue
                    if ts > max_ts:
                        ws.cell(row, date_col).fill = red_fill
            wb.save(tmp_path)

        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            background=BackgroundTask(os.unlink, tmp_path),
        )

    df.to_excel(tmp_path, index=False, engine="openpyxl")

    # 涨幅排名: 应用专属格式（与工作流导出共享 apply_ranking_format）
    if result.get('workflow_type') == '涨幅排名':
        from datetime import datetime as dt
        from services.ranking_format import apply_ranking_format

        wb = load_workbook(tmp_path)
        ws = wb.active

        date_str = result.get('date_str', '')
        try:
            ref_date = dt.strptime(date_str, '%Y-%m-%d')
        except Exception:
            ref_date = dt.now()

        # 统计分析路径下 prev_rank 取 sheet 第 (date_start+1) 列的值（共享函数内部处理），
        # 所以这里 prev_rank_by_sector 传 None 即可
        apply_ranking_format(ws, prev_rank_by_sector=None, ref_date=ref_date)

        wb.save(tmp_path)

    return FileResponse(
        path=tmp_path,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        background=BackgroundTask(os.unlink, tmp_path),
    )
