"""质押 '双列并排' Excel 上传解析测试。"""
import os
import tempfile
import pytest
from openpyxl import Workbook

from services.trend_service import _parse_pledge_side_by_side, parse_excel_for_trend


def _make_side_by_side_xlsx(rows: list[list]) -> str:
    """构造双行表头的质押样本 xlsx；rows = [[日期, 中大盘数量, 中大盘占比, 小盘数量, 小盘占比], ...]。"""
    path = tempfile.mktemp(suffix=".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.append(['日期', '中大盘', '中大盘', '小盘', '小盘'])
    ws.append([None, '占20均线数量', '占比', '占20均线数量', '占比'])
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_parse_basic_three_rows():
    path = _make_side_by_side_xlsx([
        ['3月11日', 69, '22.92%', 102, '25.76%'],
        ['3月12日', 74, '24.42%', 96, '24.30%'],
    ])
    try:
        records = _parse_pledge_side_by_side(path)
    finally:
        os.unlink(path)
    assert len(records) == 4  # 2 行 × 2 类型
    wtypes = {r["workflow_type"] for r in records}
    assert wtypes == {"质押(中大盘)", "质押(小盘)"}
    # 第一条：中大盘 3月11日
    r0 = next(r for r in records if r["date_str"].endswith("-03-11") and r["workflow_type"] == "质押(中大盘)")
    assert r0["count"] == 69
    assert r0["ratio"] == 0.2292
    # total = round(69 / 0.2292) = 301
    assert r0["total"] == 301


def test_parse_numeric_ratio():
    """占比是数字（0.25 或 25）也能解析。"""
    path = _make_side_by_side_xlsx([
        ['3月15日', 50, 0.25, 80, 25.0],
    ])
    try:
        records = _parse_pledge_side_by_side(path)
    finally:
        os.unlink(path)
    assert len(records) == 2
    zd = next(r for r in records if r["workflow_type"] == "质押(中大盘)")
    xp = next(r for r in records if r["workflow_type"] == "质押(小盘)")
    assert zd["ratio"] == 0.25 and zd["count"] == 50 and zd["total"] == 200
    assert xp["ratio"] == 0.25 and xp["count"] == 80 and xp["total"] == 320


def test_parse_empty_row_skipped():
    """数量列为空的行整体跳过。"""
    path = _make_side_by_side_xlsx([
        ['3月11日', 10, '10%', 20, '20%'],
        ['4月18日', None, None, None, None],  # 日期有但数据为空
    ])
    try:
        records = _parse_pledge_side_by_side(path)
    finally:
        os.unlink(path)
    # 只有 3月11日 的 2 条
    assert len(records) == 2


def test_parse_excel_for_trend_dispatches_pledge_special():
    """parse_excel_for_trend 对 workflow_type='质押(双列并排)' 走专用解析。"""
    path = _make_side_by_side_xlsx([['3月11日', 10, '10%', 20, '20%']])
    try:
        records = parse_excel_for_trend(path, "质押(双列并排)")
    finally:
        os.unlink(path)
    assert len(records) == 2
    assert {r["workflow_type"] for r in records} == {"质押(中大盘)", "质押(小盘)"}


def test_missing_date_column_raises():
    """表头无日期列 → 报错。"""
    path = tempfile.mktemp(suffix=".xlsx")
    wb = Workbook()
    ws = wb.active
    ws.append(['A', '中大盘', '中大盘', '小盘', '小盘'])
    ws.append(['X', '占20均线数量', '占比', '占20均线数量', '占比'])
    ws.append(['3月11日', 1, '1%', 2, '2%'])
    wb.save(path)
    try:
        with pytest.raises(ValueError, match="未找到日期列"):
            _parse_pledge_side_by_side(path)
    finally:
        os.unlink(path)
