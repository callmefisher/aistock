import os
import tempfile
import shutil
import pytest
from openpyxl import Workbook

from services.trend_service import count_high_price_rows


@pytest.fixture
def tmp_base():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _make_xlsx(path: str, sheets: dict):
    """sheets: {sheet_name: [header_row_list, data_row_list, ...]}"""
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)


def _make_dir(base: str, date_str: str) -> str:
    d = os.path.join(base, date_str, "百日新高")
    os.makedirs(d, exist_ok=True)
    return d


def test_标准列_证券代码(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [
            ["证券代码", "名称"],
            ["600001.SH", "aa"],
            ["600002.SH", "bb"],
            ["600003.SH", "cc"],
            ["600004.SH", "dd"],
            ["600005.SH", "ee"],
        ]
    })
    assert count_high_price_rows(tmp_base, date_str) == 5


def test_列名_股票代码(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [["股票代码"], ["000001.SZ"], ["000002.SZ"]]
    })
    assert count_high_price_rows(tmp_base, date_str) == 2


def test_列名_代码_带空白换行(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [["  代\n码  "], ["600001.SH"], ["600002.SH"], ["600003.SH"]]
    })
    assert count_high_price_rows(tmp_base, date_str) == 3


def test_多文件去重(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [["证券代码"], ["600001.SH"], ["600002.SH"]]
    })
    _make_xlsx(os.path.join(d, "b.xlsx"), {
        "Sheet1": [["证券代码"], ["600002.SH"], ["600003.SH"]]
    })
    assert count_high_price_rows(tmp_base, date_str) == 3


def test_多sheet(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [["证券代码"], ["600001.SH"], ["600002.SH"]],
        "Sheet2": [["股票代码"], ["000001.SZ"], ["000002.SZ"]],
    })
    assert count_high_price_rows(tmp_base, date_str) == 4


def test_空目录(tmp_base):
    # 目录根本不存在
    assert count_high_price_rows(tmp_base, "2099-01-01") == 0


def test_无代码列(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [["名称", "价格"], ["aa", 1.0], ["bb", 2.0]]
    })
    assert count_high_price_rows(tmp_base, date_str) == 0


def test_跳过空单元格(tmp_base):
    date_str = "2026-01-02"
    d = _make_dir(tmp_base, date_str)
    _make_xlsx(os.path.join(d, "a.xlsx"), {
        "Sheet1": [
            ["证券代码"],
            ["600001.SH"],
            [None],
            [""],
            ["  "],
            ["600002.SH"],
        ]
    })
    assert count_high_price_rows(tmp_base, date_str) == 2


def test_实测文件2026_04_22():
    """对照真实数据：/data/excel/2026-04-22/百日新高/百日新高0422.xlsx"""
    base_dir = "/Users/xiayanji/qbox/aistock/data/excel"
    if not os.path.isdir(os.path.join(base_dir, "2026-04-22", "百日新高")):
        pytest.skip("实测数据不存在")
    count = count_high_price_rows(base_dir, "2026-04-22")
    # 用户期望 287
    assert count == 287, f"预期 287 实际 {count}"
