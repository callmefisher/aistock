"""本周类工作流（13/14/18号表）+ weekly_common 公共逻辑 测试

覆盖：
- weekly_common：
  * scan_back_dates / mmdd_of 基础工具
  * resolve_daily_output_file：数据日期已有同名→reuse；已有其他文件→reuse最新；
    数据日期为空→35日内回溯拷贝最新（copy）；35日外/均无→new；
    回溯窗口恰好35天（含当日），第36天不参与
  * load_all_a_column_map：[行业类别]全部 列定位 + mtime缓存失效
- weekly_ma20_close_high（13号表）：
  * 全新生成：Sheet1 表头「日期/股票数量」+当日行（数量=公共文件行数）、
    日期数字格式 m"月"d"日"、折线图存在（横轴DateAxis majorUnit=7）
  * 追加模式：已有文件新增一行、已有行不修改、同日重复执行仅刷新数量
  * 35天回溯拷贝模式：老文件不动、新副本追加
  * 公共数据源缺失 → 失败
- weekly_mv1000_high（14号表+20号表）：
  * 全新生成：首个sheet「筛选结果」=公共文件内容；MMDD sheet 为第2个sheet、
    按代码列降序、B列后插入空白列；20号表输出（A列+固定文件名）
  * 已有文件：筛选结果sheet不修改；MMDD sheet 重复执行先删后建（幂等）
  * 证券代码/股票代码 列名自适应
- all_a_800（18号表）：
  * 全新生成：新增股票前3列追加；板块列（[行业类别]全部 匹配）；
    「M/D\n39日新高」列（命中填代码）；已有行不修改
  * 已有文件追加：仅新增行填充板块/39日新高，已有行不动
  * 板块列已存在 → 不重复插入
- 当月每日新增：EXPORT_MDN_MA20_SHEET=False 时 Excel 无「20日线」sheet，
  但 save_workflow_result(ma20_records_override=...) 正常入库 final_ma20
"""

import json
import os
import zlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from openpyxl import load_workbook

from services.weekly_common import (
    _all_a_column_cache,
    invalidate_all_a_column_cache,
    load_all_a_column_map,
    mmdd_of,
    resolve_daily_output_file,
    scan_back_dates,
)
from services.weekly_ma20_close_high import (
    build_default_filename as ma20_build_default_filename,
    execute_weekly_ma20_close_high,
)
from services.weekly_mv1000_high import (
    execute_weekly_mv1000_high,
    sort_rows_by_code_desc,
)
from services.all_a_800 import execute_all_a_800
from services.workflow_executor import WorkflowExecutor
from services.workflow_result_service import save_workflow_result


# ---------------------------------------------------------------- 工具

def _compress(records) -> bytes:
    return zlib.compress(json.dumps(records, ensure_ascii=False).encode("utf-8"), 6)


class _UpsertCaptureSession:
    """捕获 save_workflow_result 的 UPSERT 参数（step_type/records）"""

    def __init__(self, calls):
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        self._calls.append(dict(params or {}))
        return MagicMock()

    async def commit(self):
        pass


def _capture_factory(calls):
    def factory(*a, **kw):
        return _UpsertCaptureSession(calls)
    return factory


def _executor(base_dir, workflow_type):
    return WorkflowExecutor(base_dir=base_dir, workflow_type=workflow_type)


def _write_public_file(base_dir, date_str, sub_dir, rows, filename=None):
    """写公共数据源文件（首sheet默认名）"""
    d = os.path.join(base_dir, date_str, sub_dir)
    os.makedirs(d, exist_ok=True)
    name = filename or f"{sub_dir}{date_str.replace('-', '')}.xlsx"
    path = os.path.join(d, name)
    pd.DataFrame(rows[1:], columns=rows[0]).to_excel(path, index=False, sheet_name="筛选结果")
    return path


def _write_all_a_industry_file(base_dir, codes_industries):
    """写全部A股文件：含 [行业类别]全部 多行表头列"""
    os.makedirs(os.path.join(base_dir, "全部A股"), exist_ok=True)
    header = "所属行业名称\n[行业标准]申万行业(2021)\n[行业类别]全部\n[截止日期]最新"
    df = pd.DataFrame({
        "证券代码": [c for c, _ in codes_industries],
        header: [v for _, v in codes_industries],
    })
    df.to_excel(os.path.join(base_dir, "全部A股", "6、全部A股 板块信息.xlsx"), index=False)


def _write_39day_file(base_dir, date_str, codes):
    d = os.path.join(base_dir, date_str, "39日新高")
    os.makedirs(d, exist_ok=True)
    pd.DataFrame({"股票代码": codes}).to_excel(
        os.path.join(d, f"39日新高{date_str.replace('-', '')}.xlsx"), index=False)


@pytest.fixture(autouse=True)
def _clear_caches():
    _all_a_column_cache.clear()
    from services.monthly_ai_summary import _all_a_sector_cache, _high39_cache
    _all_a_sector_cache.clear()
    _high39_cache.clear()
    yield
    _all_a_column_cache.clear()
    _all_a_sector_cache.clear()
    _high39_cache.clear()


# ---------------------------------------------------------------- weekly_common 基础

def test_scan_back_dates_and_mmdd():
    dates = scan_back_dates("2026-10-15", 35)
    assert len(dates) == 35
    assert dates[0] == "2026-10-15"
    assert dates[1] == "2026-10-14"
    assert dates[34] == "2026-09-11"
    assert mmdd_of("2026-10-15") == "1015"
    assert mmdd_of("2026-01-05") == "0105"


def test_resolve_output_file_new_mode(tmp_path):
    """数据日期及35日内均无文件 → 全新模式"""
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "new"
    assert path == os.path.join(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")


def test_resolve_output_file_reuse_same_name(tmp_path):
    """数据日期目录已有同名文件 → 直接复用"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    open(os.path.join(d, "a1015.xlsx"), "w").close()
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "reuse"
    assert path == os.path.join(d, "a1015.xlsx")


def test_resolve_output_file_reuse_other_name(tmp_path):
    """数据日期目录只有其他文件名 → 复用其中最新一个"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    open(os.path.join(d, "old1014.xlsx"), "w").close()
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "reuse"
    assert os.path.basename(path) == "old1014.xlsx"


def test_resolve_output_file_copy_within_35_days(tmp_path):
    """数据日期为空 → 回溯取最近日期文件拷贝重命名；老文件不动"""
    back = os.path.join(str(tmp_path), "2026-10-10", "输出")
    os.makedirs(back)
    src = os.path.join(back, "old1010.xlsx")
    pd.DataFrame({"x": [1]}).to_excel(src, index=False)
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "copy"
    assert os.path.basename(path) == "a1015.xlsx"
    assert os.path.dirname(path) == os.path.join(str(tmp_path), "2026-10-15", "输出")
    assert os.path.exists(src), "老文件不应被删除"
    assert os.path.exists(path)


def test_resolve_output_file_copy_nearest_date_wins(tmp_path):
    """回溯时取最近的日期（近到远第一个命中）"""
    for back_date in ("2026-09-20", "2026-10-12", "2026-10-13"):
        d = os.path.join(str(tmp_path), back_date, "输出")
        os.makedirs(d)
        pd.DataFrame({"x": [back_date]}).to_excel(
            os.path.join(d, f"old{back_date.replace('-', '')}.xlsx"), index=False)
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "copy"
    # 拷贝自 2026-10-13（最近），内容一致
    wb = load_workbook(path)
    assert wb.worksheets[0].cell(2, 1).value == "2026-10-13"


def test_resolve_output_file_beyond_35_days_is_new(tmp_path):
    """只有第36天前的文件 → 全新（回溯窗口恰35天含当日）"""
    back = os.path.join(str(tmp_path), "2026-09-10", "输出")  # 2026-10-15 往前第36天
    os.makedirs(back)
    open(os.path.join(back, "old.xlsx"), "w").close()
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "new"
    assert not os.path.exists(path)  # new 模式只返回路径不创建文件（由调用方生成）


def test_load_all_a_column_map_and_cache(tmp_path):
    _write_all_a_industry_file(str(tmp_path), [("000009.SZ", "电池"), ("600000.SH", "银行")])
    m = load_all_a_column_map(str(tmp_path), "[行业类别]全部")
    assert m["000009.SZ"] == "电池"
    assert m["600000.SH"] == "银行"

    # mtime 缓存命中
    m2 = load_all_a_column_map(str(tmp_path), "[行业类别]全部")
    assert m2 is m

    # 文件变化 → 缓存失效重新加载
    _write_all_a_industry_file(str(tmp_path), [("000009.SZ", "光伏")])
    m3 = load_all_a_column_map(str(tmp_path), "[行业类别]全部")
    assert m3["000009.SZ"] == "光伏"

    # 手动失效接口
    invalidate_all_a_column_cache()
    assert not _all_a_column_cache


# ---------------------------------------------------------------- 13号表 weekly_ma20_close_high

def _out13(base, date_str, name=None):
    return os.path.join(
        base, date_str, "本周20日收盘价新高输出",
        name or ma20_build_default_filename(date_str))


async def _run13(base, date_str, output_filename=""):
    return await execute_weekly_ma20_close_high(
        _executor(base, "本周20日线新高"),
        {"date_str": date_str, "output_filename": output_filename}, date_str)


@pytest.mark.asyncio
async def test_ma20_close_high_new_file(tmp_path):
    """全新生成：表头+当日行+数字格式+折线图（DateAxis 周）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码", "名称")] + [(f"00000{i}.SZ", f"股{i}") for i in range(7)])

    result = await _run13(base, "2026-10-15")
    assert result["success"], result.get("error")

    out = _out13(base, "2026-10-15")
    assert os.path.exists(out)
    wb = load_workbook(out)
    ws = wb["Sheet1"]
    assert ws.cell(1, 1).value == "日期"
    assert ws.cell(1, 2).value == "股票数量"
    assert ws.cell(2, 1).value == datetime(2026, 10, 15)
    assert ws.cell(2, 2).value == 7
    assert ws.cell(2, 1).number_format == 'm"月"d"日"'
    assert len(ws._charts) == 1
    chart = ws._charts[0]
    assert chart.x_axis.majorUnit == 7
    # 字体宋体12
    assert ws.cell(1, 1).font.name == "宋体"
    assert ws.cell(1, 1).font.size == 12


@pytest.mark.asyncio
async def test_ma20_close_high_append_row(tmp_path):
    """已有文件追加：已有行不修改，仅新增一行；图表重建不叠加"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-14", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 3)
    assert (await _run13(base, "2026-10-14"))["success"]

    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 5)
    result = await _run13(base, "2026-10-15")
    assert result["success"], result.get("error")

    # 复用同一文件（数据日期目录已有文件）
    wb = load_workbook(_out13(base, "2026-10-15"))
    ws = wb["Sheet1"]
    assert ws.cell(2, 1).value == datetime(2026, 10, 14)
    assert ws.cell(2, 2).value == 3  # 老行不动
    assert ws.cell(3, 1).value == datetime(2026, 10, 15)
    assert ws.cell(3, 2).value == 5  # 新行
    assert len(ws._charts) == 1


@pytest.mark.asyncio
async def test_ma20_close_high_same_day_refresh(tmp_path):
    """同日重复执行：仅刷新当日数量（幂等，不重复加行）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 4)
    assert (await _run13(base, "2026-10-15"))["success"]
    # 公共文件更新为6行（目录mtime变化，重新读取）
    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 6,
                       filename="本周20日收盘价新高v2.xlsx")
    os.remove(os.path.join(base, "2026-10-15", "本周20日收盘价新高",
                           "本周20日收盘价新高20261015.xlsx"))
    assert (await _run13(base, "2026-10-15"))["success"]

    wb = load_workbook(_out13(base, "2026-10-15"))
    ws = wb["Sheet1"]
    assert ws.max_row == 2  # 仍是1行数据
    assert ws.cell(2, 2).value == 6


@pytest.mark.asyncio
async def test_ma20_close_high_copy_from_35days(tmp_path):
    """数据日期目录为空 → 回溯拷贝最近文件，老文件不动，新副本追加"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-10", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 2)
    assert (await _run13(base, "2026-10-10"))["success"]
    old_out = _out13(base, "2026-10-10")
    old_mtime = os.path.getmtime(old_out)

    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 9)
    result = await _run13(base, "2026-10-15")
    assert result["success"], result.get("error")

    # 老文件未被修改
    assert os.path.getmtime(old_out) == old_mtime
    # 新文件：拷贝来的老行 + 新行
    wb = load_workbook(_out13(base, "2026-10-15"))
    ws = wb["Sheet1"]
    assert ws.cell(2, 2).value == 2
    assert ws.cell(3, 2).value == 9


@pytest.mark.asyncio
async def test_ma20_close_high_missing_public(tmp_path):
    """公共数据源缺失 → 失败"""
    result = await _run13(str(tmp_path), "2026-10-15")
    assert not result["success"]
    assert "公共数据源缺失" in result["error"]


@pytest.mark.asyncio
async def test_ma20_close_high_custom_filename(tmp_path):
    """配置自定义输出文件名 → 使用配置名"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 2)
    result = await _run13(base, "2026-10-15", output_filename="自定义13.xlsx")
    assert result["success"], result.get("error")
    assert os.path.exists(_out13(base, "2026-10-15", "自定义13.xlsx"))


# ---------------------------------------------------------------- 14号表 weekly_mv1000_high

_MV_ROWS = [
    ("股票代码", "证券简称", "总市值"),
    ("000001.SZ", "平安", "1200"),
    ("600519.SH", "茅台", "2000"),
    ("300750.SZ", "宁德", "1100"),
]


def _out14(base, date_str, name=None):
    return os.path.join(
        base, date_str, "本周总市值千亿新高输出",
        name or f"14 总市值大于1000亿 本周最高价格大于上周最高价格{mmdd_of(date_str)}.xlsx")


async def _run14(base, date_str, output_filename=""):
    return await execute_weekly_mv1000_high(
        _executor(base, "本周总市值千亿新高"),
        {"date_str": date_str, "output_filename": output_filename}, date_str)


@pytest.mark.asyncio
async def test_mv1000_new_file(tmp_path):
    """全新生成：筛选结果=公共文件；MMDD sheet 第2个、代码降序、B列后空列；20号表输出"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "本周总市值千亿新高", _MV_ROWS)

    result = await _run14(base, "2026-10-15")
    assert result["success"], result.get("error")

    out = _out14(base, "2026-10-15")
    wb = load_workbook(out)
    assert wb.sheetnames == ["筛选结果", "1015"], wb.sheetnames

    # 筛选结果 sheet = 公共文件原样
    ws1 = wb["筛选结果"]
    assert [c.value for c in ws1[1]] == ["股票代码", "证券简称", "总市值"]
    assert ws1.cell(2, 1).value == "000001.SZ"

    # MMDD sheet：代码降序 + B列后空白列
    ws2 = wb["1015"]
    assert [c.value for c in ws2[1]] == ["股票代码", "证券简称", None, "总市值"]
    codes = [ws2.cell(r, 1).value for r in range(2, ws2.max_row + 1)]
    assert codes == ["600519.SH", "300750.SZ", "000001.SZ"]  # 降序
    assert ws2.cell(2, 2).value == "茅台"
    assert ws2.cell(3, 3).value in (None, "")  # 插入的空白列

    # 20号表：A列（排序后）单独输出，固定文件名
    t20 = os.path.join(base, "2026-10-15", "20号表本周总市值千亿新高A列",
                       "20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx")
    assert os.path.exists(t20)
    wt = load_workbook(t20)
    wst = wt.worksheets[0]
    assert wst.cell(1, 1).value == "股票代码"
    assert [wst.cell(r, 1).value for r in range(2, wst.max_row + 1)] == \
        ["600519.SH", "300750.SZ", "000001.SZ"]


@pytest.mark.asyncio
async def test_mv1000_reuse_keeps_first_sheet(tmp_path):
    """已有文件：筛选结果 sheet 不修改；MMDD sheet 重复执行先删后建（幂等）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "本周总市值千亿新高", _MV_ROWS)
    assert (await _run14(base, "2026-10-15"))["success"]

    # 第2天：目录里已有文件（非默认名场景走最新文件复用）
    _write_public_file(base, "2026-10-16", "本周总市值千亿新高",
                       [("股票代码", "证券简称"), ("600000.SH", "浦发")])
    assert (await _run14(base, "2026-10-16"))["success"]

    wb = load_workbook(_out14(base, "2026-10-16"))
    # 拷贝自 10-15 的文件拓展：新 MMDD sheet 位于「筛选结果」之后，历史 MMDD sheet 保留
    assert wb.sheetnames == ["筛选结果", "1016", "1015"]
    # 筛选结果仍为 10-15 的内容（不修改）
    ws1 = wb["筛选结果"]
    assert ws1.cell(2, 1).value == "000001.SZ"
    assert ws1.max_row == 4
    # 1016 sheet 为新数据
    ws2 = wb["1016"]
    assert ws2.cell(2, 1).value == "600000.SH"


@pytest.mark.asyncio
async def test_mv1000_sort_by_zhengquan_code_fallback(tmp_path):
    """列名「证券代码」时同样按代码降序"""
    base = str(tmp_path)
    rows = [("证券代码", "名称"), ("000001.SZ", "a"), ("600519.SH", "b")]
    _write_public_file(base, "2026-10-15", "本周总市值千亿新高", rows)
    assert (await _run14(base, "2026-10-15"))["success"]
    ws2 = load_workbook(_out14(base, "2026-10-15"))["1015"]
    codes = [ws2.cell(r, 1).value for r in range(2, ws2.max_row + 1)]
    assert codes == ["600519.SH", "000001.SZ"]


def test_sort_rows_by_code_desc_mixed():
    """纯数字代码（补零归一）与带后缀代码混合降序；无代码行排末尾"""
    rows = [
        ("证券代码", "名称"),
        ("1", "a"),          # 归一为 000001 参与排序，但行内容保持原值
        ("600519.SH", "b"),
        ("300750.SZ", "c"),
    ]
    out = sort_rows_by_code_desc(rows)
    codes = [r[0] for r in out[1:]]
    # 排序按归一化代码降序：600519 > 300750 > 000001(=1)
    assert codes == ["600519.SH", "300750.SZ", "1"]


# ---------------------------------------------------------------- 18号表 all_a_800

_A800_ROWS = [
    ("证券代码", "证券简称", "总市值"),
    ("000001.SZ", "平安", "900"),
    ("600519.SH", "茅台", "2100"),
    ("300750.SZ", "宁德", "950"),
]


def _out18(base, date_str, name=None):
    return os.path.join(
        base, date_str, "全部A股800亿输出",
        name or f"18 全部A股总市值大于800亿{mmdd_of(date_str)}.xlsx")


async def _run18(base, date_str, output_filename=""):
    return await execute_all_a_800(
        _executor(base, "全部A股总市值大于800亿"),
        {"date_str": date_str, "output_filename": output_filename}, date_str)


@pytest.mark.asyncio
async def test_all_a_800_new_file(tmp_path):
    """全新生成：前3列追加 + 板块列 + 39日新高列（仅命中行填代码）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "全部A股800亿", _A800_ROWS)
    _write_all_a_industry_file(base, [("000001.SZ", "银行"), ("600519.SH", "白酒")])
    _write_39day_file(base, "2026-10-15", ["000001.SZ"])

    result = await _run18(base, "2026-10-15")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-15"))
    ws = wb.worksheets[0]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    assert header[:4] == ["证券代码", "证券简称", "总市值", "板块"]
    assert "10/15\n39日新高" in header

    rows = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
    assert len(rows) == 3
    assert ws.cell(rows["000001.SZ"], 4).value == "银行"
    assert ws.cell(rows["600519.SH"], 4).value == "白酒"
    assert ws.cell(rows["300750.SZ"], 4).value in (None, "")  # 未匹配到板块
    assert ws.cell(rows["000001.SZ"], 5).value == "000001.SZ"  # 39日新高命中
    assert ws.cell(rows["600519.SH"], 5).value != "600519.SH"  # 未命中不填


@pytest.mark.asyncio
async def test_all_a_800_incremental_append(tmp_path):
    """已有文件：仅新增行追加并填充新列；已有行（含旧板块）不修改"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "全部A股800亿", _A800_ROWS[:2])
    _write_all_a_industry_file(base, [("000001.SZ", "银行")])
    _write_39day_file(base, "2026-10-15", ["000001.SZ"])
    assert (await _run18(base, "2026-10-15"))["success"]

    # 次日公共文件多了新股票
    _write_public_file(base, "2026-10-16", "全部A股800亿", _A800_ROWS)
    _write_all_a_industry_file(base, [("000001.SZ", "银行"), ("600519.SH", "白酒"), ("300750.SZ", "电池")])
    _write_39day_file(base, "2026-10-16", ["300750.SZ"])
    result = await _run18(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-16"))
    ws = wb.worksheets[0]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    # 板块列已存在不重复插入；新增 10/16 列
    assert header.count("板块") == 1
    assert "10/15\n39日新高" in header
    assert "10/16\n39日新高" in header
    assert header.index("10/16\n39日新高") == header.index("板块") + 1

    rows = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
    assert len(rows) == 3
    # 10-15 已有行：板块保持，10/16 列不填
    r15 = rows["000001.SZ"]
    assert ws.cell(r15, header.index("板块") + 1).value == "银行"
    assert ws.cell(r15, header.index("10/16\n39日新高") + 1).value in (None, "")
    # 新增行：板块 + 39日新高命中
    r_new = rows["300750.SZ"]
    assert ws.cell(r_new, header.index("板块") + 1).value == "电池"
    assert ws.cell(r_new, header.index("10/16\n39日新高") + 1).value == "300750.SZ"


@pytest.mark.asyncio
async def test_all_a_800_missing_public(tmp_path):
    result = await _run18(str(tmp_path), "2026-10-15")
    assert not result["success"]
    assert "公共数据源缺失" in result["error"]


# ---------------------------------------------------------------- 当月每日新增：20日线sheet屏蔽 + DB透传

@pytest.mark.asyncio
async def test_mdn_ma20_sheet_blocked_but_db_saved_via_override(tmp_path):
    """17号表无「20日线」sheet（导出屏蔽），ma20_records_override 正常入库 final_ma20"""
    d = os.path.join(str(tmp_path), "out")
    os.makedirs(d)
    path = os.path.join(d, "17 10月新增1015.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"证券代码": ["000009.SZ"]}).to_excel(w, index=False, sheet_name="当月每日新增")

    calls = []
    with patch("services.workflow_result_service.AsyncSessionLocal", _capture_factory(calls)):
        ok = await save_workflow_result(
            1, "当月每日新增", "wf", "2026-10-15", path,
            ma20_records_override=[{"证券代码": "600000.SH"}, {"证券代码": "000001.SZ"}])
    assert ok
    assert [c["step_type"] for c in calls] == ["final", "final_ma20"]

    def _records(c):
        return json.loads(zlib.decompress(c["data_compressed"]).decode("utf-8"))

    assert [r["证券代码"] for r in _records(calls[1])] == ["600000.SH", "000001.SZ"]


@pytest.mark.asyncio
async def test_mdn_ma20_override_none_falls_back_to_file(tmp_path):
    """override=None（未提供）→ 回退从文件读「20日线」sheet（兼容开关恢复后的路径）"""
    d = os.path.join(str(tmp_path), "out")
    os.makedirs(d)
    path = os.path.join(d, "17 10月新增1015.xlsx")
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        pd.DataFrame({"证券代码": ["000009.SZ"]}).to_excel(w, index=False, sheet_name="当月每日新增")
        pd.DataFrame({"证券代码": ["600000.SH"]}).to_excel(w, index=False, sheet_name="20日线")

    calls = []
    with patch("services.workflow_result_service.AsyncSessionLocal", _capture_factory(calls)):
        ok = await save_workflow_result(1, "当月每日新增", "wf", "2026-10-15", path)
    assert ok
    assert [c["step_type"] for c in calls] == ["final", "final_ma20"]

    def _records(c):
        return json.loads(zlib.decompress(c["data_compressed"]).decode("utf-8"))

    assert [r["证券代码"] for r in _records(calls[1])] == ["600000.SH"]


@pytest.mark.asyncio
async def test_mdn_ma20_override_empty_list_still_saved(tmp_path):
    """override=[]（当日无新增）→ 照常入库 final_ma20（区别于 None=跳过）"""
    d = os.path.join(str(tmp_path), "out")
    os.makedirs(d)
    path = os.path.join(d, "17 10月新增1015.xlsx")
    pd.DataFrame({"证券代码": ["000009.SZ"]}).to_excel(path, index=False, sheet_name="当月每日新增")

    calls = []
    with patch("services.workflow_result_service.AsyncSessionLocal", _capture_factory(calls)):
        ok = await save_workflow_result(
            1, "当月每日新增", "wf", "2026-10-15", path, ma20_records_override=[])
    assert ok
    assert [c["step_type"] for c in calls] == ["final", "final_ma20"]

    def _records(c):
        return json.loads(zlib.decompress(c["data_compressed"]).decode("utf-8"))

    assert _records(calls[1]) == []


def test_export_mdn_ma20_sheet_flag():
    """全局开关：当前为屏蔽状态（后续恢复导出改回 True 即可）"""
    from services.workflow_executor import EXPORT_MDN_MA20_SHEET
    assert EXPORT_MDN_MA20_SHEET is False
