"""当月每日新增（monthly_daily_new 步骤）测试 — 无缓存，只用数据日期当日的条件交集数据

覆盖：
- filter_monthly_daily_new_codes 纯函数：
  * 非首交易日：J 含数据日期且当月无更早日期才输出；跨月旧日期不影响输出
  * 首交易日判定（全表 J 列当月只出现数据日期）→ 排除上月任何日期
    （J="2026-10-01,2026-09-10" 排除；J="2026-10-01,2026-08-20" 有效输出）
  * 数据日期为本月非 1 日但当月无其他日期（如长假后首日）→ 同首交易日逻辑
  * 跨年首交易日（1 月 → 排除上一年 12 月）
  * 标绿：J 严格只含唯一日期且等于数据日期；含任何其他日期（含跨月）输出但不标绿
  * 行序去重（首行优先）、J 不含数据日期的行排除
- 数据加载：DB 优先（空表为权威空）、DB 记录缺 J 列（旧格式）走 Excel 兜底、
  无 DB 记录走 Excel 兜底、主文件查找排除"证券代码"后缀文件
- 步骤端到端：输出单列 Excel + 严格新增绿底、幂等重复执行输出一致、
  当日文件被删但 DB 有记录时结果不变（回归一键并行/当日二次执行标记丢失 bug）、
  当日条件交集有数据但无新增 → 成功输出空表、无数据/空表失败、单数字月份目录

DB 通过 patch core.database.AsyncSessionLocal 注入 FakeSession 隔离，不依赖真实数据库。
"""

import asyncio
import json
import os
import zlib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.workflow_executor import WorkflowExecutor, filter_monthly_daily_new_codes


# ---------------------------------------------------------------- DB 假件

def _compress(records) -> bytes:
    return zlib.compress(json.dumps(records, ensure_ascii=False).encode("utf-8"), 6)


class _FakeSession:
    """Async with 协议 + execute 按 params['d'] 过滤，fetchone 返回 (compressed,) 单行。"""

    def __init__(self, rows):
        self._rows = rows  # [(date_str, compressed)]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        d = (params or {}).get("d", "")
        matched = [r for r in self._rows if r[0] == d]
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=(matched[0][1],) if matched else None)
        return mock_result


def _fake_session_factory(rows):
    def factory(*a, **kw):
        return _FakeSession(rows)
    return factory


def _db_row(date_str, rows_j):
    """构造 workflow_results 记录（内容 = 条件交集主文件首 sheet 行）。
    rows_j: [(证券代码, J列日期串), ...]"""
    j_col = f"2026-03-18至{date_str}期间百日新高的日期"
    records = [
        {"证券代码": c, "证券简称": c + "简称", j_col: j}
        for c, j in rows_j
    ]
    return (date_str, _compress(records))


@pytest.fixture(autouse=True)
def _fake_db(monkeypatch):
    """默认 DB 无记录 → 文件类测试即 Excel 兜底路径，同时避免真实 DB 连接。"""
    monkeypatch.setattr("core.database.AsyncSessionLocal", _fake_session_factory([]))


# ---------------------------------------------------------------- 公共

def _make_intersection_file(base_dir, date_str, rows):
    """生成条件交集主文件（sheet"条件交集百日新高"），rows: [(证券代码, J列日期串), ...]
    同时放置"证券代码"后缀干扰文件，验证主文件查找的排除逻辑"""
    day_dir = os.path.join(base_dir, "条件交集", date_str)
    os.makedirs(day_dir, exist_ok=True)
    compact = date_str.replace("-", "")
    j_col = f"2026-03-18至{date_str}期间百日新高的日期"
    df = pd.DataFrame({
        "证券代码": [r[0] for r in rows],
        "证券简称": [r[0] + "简称" for r in rows],
        j_col: [r[1] for r in rows],
    })
    main_file = os.path.join(day_dir, f"7条件交集{compact}.xlsx")
    df.to_excel(main_file, index=False, sheet_name="条件交集百日新高", engine="openpyxl")
    pd.DataFrame({"证券代码": []}).to_excel(
        os.path.join(day_dir, f"7条件交集{compact}百日新高证券代码.xlsx"),
        index=False, engine="openpyxl",
    )
    return main_file


def _run_step(tmp_path, config):
    executor = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    return asyncio.run(executor.execute_step("monthly_daily_new", config))


def _read_output(path):
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    values = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
    fills = []
    for r in range(2, ws.max_row + 1):
        f = ws.cell(r, 1).fill
        fills.append(f.start_color.rgb if f.fill_type == "solid" else None)
    return ws.cell(1, 1).value, values, fills


# ---------------------------------------------------------------- 纯函数过滤

def test_filter_normal_day():
    """非首交易日：J 含数据日期且当月无更早日期才输出；跨月旧日期不影响输出，但影响标绿"""
    rows = [
        ("000001.SZ", "2026-10-01,2026-10-09"),   # 当月更早日期 → 排除
        ("000002.SZ", "2026-10-09"),               # 纯新 → 输出+标绿
        ("000003.SZ", "2026-10-09,2026-09-28"),    # 当月新增+跨月旧日期 → 输出不标绿
        ("000004.SZ", "2026-10-03"),               # J 不含数据日期 → 排除
        ("000002.SZ", "2026-10-09"),               # 重复代码 → 去重
    ]
    out, marked, first = filter_monthly_daily_new_codes(rows, "2026-10-09")
    assert out == ["000002.SZ", "000003.SZ"]
    assert marked == ["000002.SZ"]
    assert first is False


def test_filter_first_trading_day_on_month_1st():
    """首交易日（数据日期为本月1日）：排除上月日期；上上月日期有效"""
    rows = [
        ("000001.SZ", "2026-10-01"),               # 纯新 → 输出+标绿
        ("000002.SZ", "2026-10-01,2026-09-10"),     # 上月(9月)日期 → 排除
        ("000003.SZ", "2026-10-01,2026-08-20"),     # 上上月(8月)日期 → 有效输出，不标绿
    ]
    out, marked, first = filter_monthly_daily_new_codes(rows, "2026-10-01")
    assert first is True
    assert out == ["000001.SZ", "000003.SZ"]
    assert marked == ["000001.SZ"]


def test_filter_first_trading_day_later_in_month():
    """数据日期非1日但全表当月只出现数据日期（如长假后首日）→ 按首交易日逻辑"""
    rows = [
        ("000001.SZ", "2026-10-09"),
        ("000002.SZ", "2026-10-09,2026-09-30"),   # 上月(9月)日期 → 排除
        ("000003.SZ", "2026-10-09,2026-08-15"),   # 8月日期 → 有效输出
    ]
    out, marked, first = filter_monthly_daily_new_codes(rows, "2026-10-09")
    assert first is True
    assert out == ["000001.SZ", "000003.SZ"]
    assert marked == ["000001.SZ"]


def test_filter_first_trading_day_year_boundary():
    """跨年首交易日：1月 → 排除上一年 12 月，11 月及更早有效"""
    rows = [
        ("000001.SZ", "2027-01-04"),
        ("000002.SZ", "2027-01-04,2026-12-31"),   # 上月(2026-12) → 排除
        ("000003.SZ", "2027-01-04,2026-11-20"),   # 2026-11 → 有效输出
    ]
    out, marked, first = filter_monthly_daily_new_codes(rows, "2027-01-04")
    assert first is True
    assert out == ["000001.SZ", "000003.SZ"]
    assert marked == ["000001.SZ"]


def test_filter_empty_month_dates():
    """全表 J 列均无当月日期 → 首交易日判定为真，但无任何输出（均不含数据日期）"""
    rows = [("000001.SZ", "2026-09-20")]
    out, marked, first = filter_monthly_daily_new_codes(rows, "2026-10-09")
    assert out == [] and marked == [] and first is True


# ---------------------------------------------------------------- 数据加载

def test_load_rows_db_priority(tmp_path):
    """DB 有记录（无 Excel 文件）→ 直接用 DB，不需 Excel"""
    rows = [_db_row("2026-10-09", [
        ("000001.SZ", "2026-10-09"),
        ("000002.SZ", "2026-10-01,2026-10-09"),
    ])]
    ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows)):
        loaded = asyncio.run(ex._load_intersection_rows(
            os.path.join(str(tmp_path), "条件交集"), "2026-10-09"))
    assert loaded == [("000001.SZ", "2026-10-09"), ("000002.SZ", "2026-10-01,2026-10-09")]


def test_load_rows_db_empty_authoritative(tmp_path):
    """DB 记录为空列表 → 权威空表，不走 Excel 兜底"""
    rows = [("2026-10-09", _compress([]))]
    _make_intersection_file(str(tmp_path), "2026-10-09", [("000005.SZ", "2026-10-09")])
    ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows)):
        loaded = asyncio.run(ex._load_intersection_rows(
            os.path.join(str(tmp_path), "条件交集"), "2026-10-09"))
    assert loaded == []


def test_load_rows_db_old_format_fallback_excel(tmp_path):
    """DB 记录缺 J 列字段（旧格式首 sheet）→ 走 Excel 兜底"""
    rows = [("2026-10-09", _compress([{"证券代码": "000001.SZ", "其他": "x"}]))]
    _make_intersection_file(str(tmp_path), "2026-10-09", [("000005.SZ", "2026-10-09")])
    ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows)):
        loaded = asyncio.run(ex._load_intersection_rows(
            os.path.join(str(tmp_path), "条件交集"), "2026-10-09"))
    assert loaded == [("000005.SZ", "2026-10-09")]


def test_load_rows_nothing(tmp_path):
    """DB 与 Excel 均无数据 → None"""
    ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    loaded = asyncio.run(ex._load_intersection_rows(
        os.path.join(str(tmp_path), "条件交集"), "2026-10-09"))
    assert loaded is None


# ---------------------------------------------------------------- monthly_daily_new 步骤

def test_monthly_daily_new_step(tmp_path):
    """Excel 兜底：输出仅当日新增代码，J 严格单一日期标绿；幂等重复执行输出一致"""
    base = str(tmp_path)
    _make_intersection_file(base, "2026-10-09", [
        ("000001.SZ", "2026-10-01,2026-10-09"),   # 当月更早 → 排除
        ("000002.SZ", "2026-10-09"),               # 纯新 → 输出+标绿
        ("000003.SZ", "2026-10-09,2026-09-28"),    # 当月新增+跨月旧 → 输出不标绿
        ("000004.SZ", "2026-10-03,2026-10-09"),   # 当月更早 → 排除
    ])

    result = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result["success"] is True
    assert os.path.basename(result["file_path"]) == "17 10月新增1009.xlsx"
    # 数据目录按月组织
    assert os.path.basename(os.path.dirname(result["file_path"])) == "2026年10月新增"
    assert result["new_codes"] == ["000002.SZ", "000003.SZ"]
    assert result["marked_codes"] == ["000002.SZ"]

    header, values, fills = _read_output(result["file_path"])
    assert header == "证券代码"
    assert values == ["000002.SZ", "000003.SZ"]
    assert fills == ["FFD8EAD8", None]   # 严格单一日期标绿，跨月旧日期不标绿

    # 幂等：重复执行输出一致
    result2 = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result2["new_codes"] == result["new_codes"]
    assert result2["marked_codes"] == result["marked_codes"]
    _, values2, fills2 = _read_output(result2["file_path"])
    assert values2 == values and fills2 == fills


def test_monthly_daily_new_first_trading_day_step(tmp_path):
    """首交易日（本月1日）：排除上月日期，上上月日期有效；消息提示首交易日"""
    base = str(tmp_path)
    _make_intersection_file(base, "2026-10-01", [
        ("000001.SZ", "2026-10-01"),
        ("000002.SZ", "2026-10-01,2026-09-10"),   # 上月日期 → 排除
        ("000003.SZ", "2026-10-01,2026-08-20"),   # 上上月 → 输出不标绿
    ])

    result = _run_step(tmp_path, {"date_str": "2026-10-01"})
    assert result["success"] is True
    assert os.path.basename(result["file_path"]) == "17 10月新增1001.xlsx"
    assert result["new_codes"] == ["000001.SZ", "000003.SZ"]
    assert result["marked_codes"] == ["000001.SZ"]
    assert "当月第一个交易日" in result["message"]

    _, values, fills = _read_output(result["file_path"])
    assert values == ["000001.SZ", "000003.SZ"]
    assert fills == ["FFD8EAD8", None]


def test_monthly_daily_new_today_from_db(tmp_path):
    """回归 bug：条件交集再次执行时先删除了当日文件且失败，文件丢失；
    但首次成功的结果已入库 → 当月每日新增从 DB 读到当日数据，输出/标记正常"""
    rows = [_db_row("2026-10-09", [
        ("000001.SZ", "2026-10-01,2026-10-09"),
        ("000002.SZ", "2026-10-09"),
        ("000003.SZ", "2026-10-09"),
    ])]
    # 当日 Excel 文件不存在（已被删除）
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows)):
        result = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result["success"] is True
    assert result["new_codes"] == ["000002.SZ", "000003.SZ"]
    assert result["marked_codes"] == ["000002.SZ", "000003.SZ"]

    _, values, fills = _read_output(result["file_path"])
    assert values == ["000002.SZ", "000003.SZ"]
    assert fills == ["FFD8EAD8", "FFD8EAD8"]


def test_monthly_daily_new_no_new_codes(tmp_path):
    """当日条件交集有数据但无新增 → 成功输出空表（仅表头）"""
    base = str(tmp_path)
    _make_intersection_file(base, "2026-10-09", [
        ("000001.SZ", "2026-10-03,2026-10-09"),   # 当月更早 → 无新增
    ])
    result = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result["success"] is True
    assert result["new_codes"] == []
    assert "无新增" in result["message"]
    header, values, fills = _read_output(result["file_path"])
    assert header == "证券代码" and values == [] and fills == []


def test_monthly_daily_new_empty_table(tmp_path):
    """当日条件交集为空表（DB 空记录）→ 失败并提示"""
    rows = [("2026-10-09", _compress([]))]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows)):
        result = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result["success"] is False
    assert "空表" in result["message"]


def test_monthly_daily_new_no_data(tmp_path):
    """当月无任何数据（DB/Excel 均无）→ 失败并提示"""
    result = _run_step(tmp_path, {"date_str": "2026-10-09"})
    assert result["success"] is False
    assert "无条件交集数据" in result["message"]


def test_monthly_daily_new_single_digit_month(tmp_path):
    """单数字月份：目录 2026年3月新增 / 文件 17 3月新增0305.xlsx"""
    _make_intersection_file(str(tmp_path), "2026-03-05", [("600000.SH", "2026-03-05")])
    result = _run_step(tmp_path, {"date_str": "2026-03-05"})
    assert result["success"] is True
    rel = os.path.relpath(result["file_path"], str(tmp_path)).replace(os.sep, "/")
    assert rel == "当月每日新增/2026年3月新增/17 3月新增0305.xlsx"


def test_resolver_month_dir(tmp_path):
    """下载端点依赖 _get_daily_dir：新类型解析为月度目录，其他类型不受影响"""
    executor = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="当月每日新增")
    assert executor._get_daily_dir("2026-10-09") == os.path.join(str(tmp_path), "当月每日新增", "2026年10月新增")
    assert executor._get_daily_dir("2026-03-05") == os.path.join(str(tmp_path), "当月每日新增", "2026年3月新增")
    ex2 = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="条件交集")
    assert ex2._get_daily_dir("2026-10-09") == os.path.join(str(tmp_path), "条件交集", "2026-10-09")
