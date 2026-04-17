from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from api.auth import get_current_user
from models.models import User
from services import workflow_result_service as svc
import tempfile
import os

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

    df.to_excel(tmp_path, index=False, engine="openpyxl")

    # 涨幅排名: 应用专属格式
    if result.get('workflow_type') == '涨幅排名':
        wb = load_workbook(tmp_path)
        ws = wb.active

        DEEP_RED = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
        DEEP_RED_FONT = Font(color="FFFFFF", bold=True)
        LIGHT_RED = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
        LIGHT_RED_FONT = Font(color="FFFFFF")
        GOLD_FILL = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

        max_row = ws.max_row
        max_col = ws.max_column

        # 表头：加粗居中，仅第3列金色，日期列头写入实际日期值
        import re as re_mod
        from datetime import datetime as dt
        date_str = result.get('date_str', '')
        try:
            ref_date = dt.strptime(date_str, '%Y-%m-%d')
        except Exception:
            ref_date = dt.now()

        for col_idx in range(1, max_col + 1):
            cell = ws.cell(row=1, column=col_idx)
            header = str(cell.value or '')
            m = re_mod.match(r'^(\d+)月(\d+)日$', header)
            if m:
                month, day = int(m.group(1)), int(m.group(2))
                year = ref_date.year if month <= ref_date.month else ref_date.year - 1
                cell.value = dt(year, month, day)
                cell.number_format = 'm"月"d"日"'
            cell.font = Font(bold=True, size=11)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=1, column=3).fill = GOLD_FILL
        ws.cell(row=1, column=3).font = Font(bold=True, size=11)

        # 列宽
        for col_idx in range(1, max_col + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 35 if col_idx in (2, 3) else 25

        # 所有数据单元格居中
        center = Alignment(horizontal="center", vertical="center")
        for row_idx in range(2, max_row + 1):
            for col_idx in range(1, max_col + 1):
                ws.cell(row=row_idx, column=col_idx).alignment = center

        # 日期列(col4+) Top5 深红
        for col_idx in range(4, max_col + 1):
            for row_idx in range(2, max_row + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                try:
                    val = int(cell.value) if cell.value is not None else None
                except (ValueError, TypeError):
                    val = None
                if val is not None and val <= 5:
                    cell.fill = DEEP_RED
                    cell.font = DEEP_RED_FONT

        # 当日列(col4) 排名提升浅红（非Top5，且排名数字 < 上一工作日col5）
        if max_col >= 5:
            for row_idx in range(2, max_row + 1):
                cell_today = ws.cell(row=row_idx, column=4)
                cell_prev = ws.cell(row=row_idx, column=5)
                try:
                    rank_today = int(cell_today.value) if cell_today.value is not None else None
                    rank_prev = int(cell_prev.value) if cell_prev.value is not None else None
                except (ValueError, TypeError):
                    rank_today = rank_prev = None
                if rank_today is not None and rank_today > 5 and rank_prev is not None and rank_today < rank_prev:
                    cell_today.fill = LIGHT_RED
                    cell_today.font = LIGHT_RED_FONT

        # 自动过滤
        ws.auto_filter.ref = f"A1:{get_column_letter(max_col)}{max_row}"

        wb.save(tmp_path)

    return FileResponse(
        path=tmp_path,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        background=BackgroundTask(os.unlink, tmp_path),
    )
