import os
import tempfile
import shutil
import pytest
from openpyxl import Workbook

from services.trend_service import parse_excel_for_trend


@pytest.fixture
def tmp_xlsx():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make(path: str, rows: list):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_两列标准格式(tmp_xlsx):
    fp = os.path.join(tmp_xlsx, "a.xlsx")
    _make(fp, [
        ["日期", "数量"],
        [46112, 99],
        [46113, 89],
        [46114, 90],
    ])
    recs = parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")
    assert len(recs) == 3
    assert all(r["workflow_type"] == "百日新高总趋势" for r in recs)
    assert recs[0]["count"] == 99
    assert recs[0]["total"] == 0
    assert recs[0]["ratio"] == 0
    # Excel 序列号 46112 → 2026-03-31（Excel epoch 约定）
    assert recs[0]["date_str"] == "2026-03-31"


def test_空数量行跳过(tmp_xlsx):
    fp = os.path.join(tmp_xlsx, "a.xlsx")
    _make(fp, [
        ["日期", "数量"],
        [46112, 99],
        [46113, None],
        [46114, 90],
        [46115, ""],
    ])
    recs = parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")
    assert len(recs) == 2
    assert [r["count"] for r in recs] == [99, 90]


def test_日期字符串_M月D日(tmp_xlsx):
    fp = os.path.join(tmp_xlsx, "a.xlsx")
    _make(fp, [
        ["日期", "数量"],
        ["4月1日", 50],
        ["4月2日", 60],
    ])
    recs = parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")
    assert len(recs) == 2
    # 日期应落在已发生的某个年份
    assert recs[0]["date_str"].endswith("-04-01") or recs[0]["date_str"].endswith("-4-1")
    assert recs[0]["count"] == 50


def test_列名别名_count行数(tmp_xlsx):
    fp = os.path.join(tmp_xlsx, "a.xlsx")
    _make(fp, [
        ["date", "count"],
        [46112, 100],
    ])
    recs = parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")
    assert len(recs) == 1
    assert recs[0]["count"] == 100


def test_缺数量列_报错(tmp_xlsx):
    fp = os.path.join(tmp_xlsx, "a.xlsx")
    _make(fp, [
        ["日期", "其他"],
        [46112, 99],
    ])
    with pytest.raises(ValueError):
        parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")


def test_11_0422样例():
    """真实样例：/Users/xiayanji/Desktop/11_0422.xlsx（25行 - 1 表头 - 5 空 = 19）
    该样例路径可能不在容器内，跳过"""
    fp = "/Users/xiayanji/Desktop/11_0422.xlsx"
    if not os.path.exists(fp):
        pytest.skip("样例文件不存在")
    recs = parse_excel_for_trend(fp, "百日新高总趋势", metric_type="high_price")
    # 24 行数据里 5 行空数量 → 19 条
    assert len(recs) == 19
