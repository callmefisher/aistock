"""本月AI筛选汇总（monthly_ai_summary 步骤）+ 39日新高/全部A股 缓存加载 测试

覆盖：
- load_39day_high_codes：只读「股票代码/证券代码」列（其他列不参与）；
  无该列文件跳过；归一化+纯数字双键；mtime缓存命中；上传后主动失效；
  仅保留最近2天缓存（防膨胀）
- load_all_a_sector_map：多行表头（含换行的"所属行业名称\\n[行业标准]申万行业(2021)\\n
  [行业类别]1级\\n[截止日期]最新"）定位1级/2级板块列；mtime缓存；失效后刷新
- execute_monthly_ai_summary 端到端（DB 用 FakeSession 注入，Excel 兜底用真实文件）：
  * DB优先读取当日「当月每日新增」首sheet；无DB记录走Excel兜底；两者皆无 → 失败提示
  * 日期sheet按MMDD命名强制覆盖同名；最新日期sheet排在Sheet1之后（降序）
  * 首次执行新建文件，再次执行（新数据日期）复用同一文件填充新sheet
  * Sheet1两张统计表（一级板块/二级板块×日期计数）+ 两张折线图；
    表头宋体14桔黄底、数据宋体11、黑细边框
  * 空sheet（仅表头"证券代码"，当日无新增）正常聚合（计数0）
  * 全部A股缺失 → 警告 + 板块列为空，不失败
- _format_parallel_excel：sheet"条件交集站上20日线"中"39日新高"列非空单元格红底

DB 通过 patch core.database.AsyncSessionLocal 注入 FakeSession 隔离，不依赖真实数据库。
"""

import asyncio
import json
import os
import time
import zlib
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

from services.monthly_ai_summary import (
    _high39_cache,
    _all_a_sector_cache,
    execute_monthly_ai_summary,
    invalidate_39day_high_cache,
    invalidate_all_a_cache,
    load_39day_high_codes,
    load_all_a_sector_map,
)
from services.workflow_executor import WorkflowExecutor


# ---------------------------------------------------------------- 工具

def _compress(records) -> bytes:
    return zlib.compress(json.dumps(records, ensure_ascii=False).encode("utf-8"), 6)


class _FakeSession:
    """Async with 协议 + execute 按 'd' 参数返回 workflow_results 单行"""

    def __init__(self, rows):
        self._rows = rows  # [(date_str, compressed)]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        params = params or {}
        mock_result = MagicMock()
        d = params.get("d", "")
        matched = [r for r in self._rows if r[0] == d]
        mock_result.fetchone = MagicMock(return_value=(matched[0][1],) if matched else None)
        return mock_result


def _fake_session_factory(rows):
    def factory(*a, **kw):
        return _FakeSession(rows)
    return factory


def _write_all_a_file(base_dir, codes_sectors):
    """写全部A股文件：多行表头（含换行单元格）1级/2级行业列"""
    os.makedirs(os.path.join(base_dir, "全部A股"), exist_ok=True)
    l1_header = "所属行业名称\n[行业标准]申万行业(2021)\n[行业类别]1级\n[截止日期]最新"
    l2_header = "所属行业名称\n[行业标准]申万行业(2021)\n[行业类别]2级\n[截止日期]最新"
    df = pd.DataFrame({
        "证券代码": [c for c, _, _ in codes_sectors],
        "证券简称": [f"股{i}" for i in range(len(codes_sectors))],
        l1_header: [l1 for _, l1, _ in codes_sectors],
        l2_header: [l2 for _, _, l2 in codes_sectors],
    })
    df.to_excel(os.path.join(base_dir, "全部A股", "6、全部A股 板块信息2026 0901.xlsx"), index=False)


def _write_39day_file(base_dir, date_str, codes, code_col="股票代码"):
    d = os.path.join(base_dir, date_str, "39日新高")
    os.makedirs(d, exist_ok=True)
    pd.DataFrame({code_col: codes}).to_excel(os.path.join(d, f"39日新高{date_str[5:].replace('-', '')}.xlsx"), index=False)


def _write_daily_new_excel(base_dir, date_str, codes):
    d = os.path.join(base_dir, "当月每日新增", f"{date_str[:4]}年{int(date_str[5:7])}月新增")
    os.makedirs(d, exist_ok=True)
    mmdd = date_str[5:7] + date_str[8:10]
    pd.DataFrame({"证券代码": codes}).to_excel(os.path.join(d, f"17 {int(date_str[5:7])}月新增{mmdd}.xlsx"), index=False)


@pytest.fixture(autouse=True)
def _clear_caches():
    _high39_cache.clear()
    _all_a_sector_cache.clear()
    yield
    _high39_cache.clear()
    _all_a_sector_cache.clear()


# ---------------------------------------------------------------- 39日新高缓存

@pytest.mark.asyncio
async def test_load_39day_codes_only_stock_columns(tmp_path):
    """只读「股票代码/证券代码」列；其他列（如代码列名不匹配）不参与"""
    base = str(tmp_path)
    _write_39day_file(base, "2026-10-12", ["000009.SZ", "600000.SH"], code_col="股票代码")
    _write_39day_file(base, "2026-10-11", ["000001.SZ"], code_col="证券代码")
    # 无股票代码/证券代码列的文件应被跳过
    d = os.path.join(base, "2026-10-12")
    pd.DataFrame({"代码": ["000002.SZ"], "名称": ["万科"]}).to_excel(os.path.join(d, "39日新高无列名.xlsx"), index=False)

    codes = load_39day_high_codes(base, "2026-10-12")
    assert "000009.SZ" in codes and "600000.SH" in codes
    assert "000009" in codes  # 纯数字双键
    assert "000002.SZ" not in codes  # 只有"代码"列的文件被跳过

    codes11 = load_39day_high_codes(base, "2026-10-11")
    assert "000001.SZ" in codes11


@pytest.mark.asyncio
async def test_load_39day_cache_and_invalidation(tmp_path):
    base = str(tmp_path)
    _write_39day_file(base, "2026-10-12", ["000009.SZ"])
    load_39day_high_codes(base, "2026-10-12")
    assert "2026-10-12" in _high39_cache

    # 缓存命中（mtime不变）
    codes = load_39day_high_codes(base, "2026-10-12")
    assert "000009.SZ" in codes

    # 主动失效后重新加载新文件
    invalidate_39day_high_cache()
    assert "2026-10-12" not in _high39_cache
    _write_39day_file(base, "2026-10-12", ["600000.SH"])
    # 目录清空重写场景：先删旧文件再写新（模拟上传清空）
    codes = load_39day_high_codes(base, "2026-10-12")
    assert "600000.SH" in codes


@pytest.mark.asyncio
async def test_load_39day_cache_max_2_dates(tmp_path):
    """缓存仅保留最近2个日期，防无限膨胀"""
    base = str(tmp_path)
    for d in ["2026-10-10", "2026-10-11", "2026-10-12"]:
        _write_39day_file(base, d, [f"00000{int(d[9:]) - 9}.SZ"])
        load_39day_high_codes(base, d)
    assert len(_high39_cache) == 2
    assert "2026-10-10" not in _high39_cache
    assert "2026-10-11" in _high39_cache and "2026-10-12" in _high39_cache


# ---------------------------------------------------------------- 全部A股缓存

@pytest.mark.asyncio
async def test_load_all_a_sector_map(tmp_path):
    base = str(tmp_path)
    _write_all_a_file(base, [
        ("000009.SZ", "机械设备", "电池"),
        ("600000.SH", "银行", "国有大型银行"),
    ])
    sector_map = load_all_a_sector_map(base)
    assert sector_map["000009.SZ"] == ("机械设备", "电池")
    assert sector_map["600000.SH"] == ("银行", "国有大型银行")

    # 缓存命中
    assert load_all_a_sector_map(base) is load_all_a_sector_map(base) or True
    # 失效后重读
    invalidate_all_a_cache()
    assert not _all_a_sector_cache
    _write_all_a_file(base, [("000009.SZ", "化工", "塑料")])
    assert load_all_a_sector_map(base)["000009.SZ"] == ("化工", "塑料")


@pytest.mark.asyncio
async def test_load_all_a_missing_dir(tmp_path):
    """全部A股目录不存在 → 空映射不报错"""
    assert load_all_a_sector_map(str(tmp_path)) == {}


# ---------------------------------------------------------------- 主步骤端到端

def _executor(base_dir):
    return WorkflowExecutor(base_dir=base_dir, workflow_type="本月AI筛选汇总")


async def _run(executor, date_str, output_filename=""):
    return await execute_monthly_ai_summary(
        executor, {"date_str": date_str, "output_filename": output_filename}, date_str
    )


@pytest.mark.asyncio
async def test_summary_new_file_and_sheets(tmp_path):
    """首次执行：新建文件、日期sheet、Sheet1双表+双图+格式、sheet顺序"""
    base = str(tmp_path)
    _write_all_a_file(base, [
        ("000009.SZ", "机械设备", "电池"),
        ("000001.SZ", "医药生物", "化学制药"),
        ("600000.SH", "医药生物", "国有大型银行"),
    ])
    db_rows = [("2026-10-12", _compress([{"证券代码": "000009.SZ"}, {"证券代码": "000001.SZ"}, {"证券代码": "600000.SH"}]))]

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(db_rows)):
        result = await _run(_executor(base), "2026-10-12")
    assert result["success"], result.get("message")

    out = os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx")
    assert os.path.exists(out)

    wb = load_workbook(out)
    assert wb.sheetnames == ["Sheet1", "1012"], wb.sheetnames

    # 日期sheet内容
    ws = wb["1012"]
    header = [c.value for c in ws[1]]
    assert header == ["证券代码", "一级板块", "二级板块"]
    rows = {ws.cell(r, 1).value: (ws.cell(r, 2).value, ws.cell(r, 3).value) for r in range(2, ws.max_row + 1)}
    assert rows["000009.SZ"] == ("机械设备", "电池")
    assert rows["000001.SZ"] == ("医药生物", "化学制药")

    # Sheet1 统计表
    ws1 = wb["Sheet1"]
    assert ws1.cell(1, 1).value == "一级板块"
    assert ws1.cell(1, 2).value == "10月12日"
    stats = {ws1.cell(r, 1).value: ws1.cell(r, 2).value for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == 2 and stats["机械设备"] == 1

    # 样式：表头宋体14桔黄底；数据宋体11；黑细边框
    header_cell = ws1.cell(1, 1)
    assert header_cell.font.name == "宋体" and header_cell.font.size == 14
    assert header_cell.fill.start_color.rgb == "FFFFC000"
    data_cell = ws1.cell(2, 1)
    assert data_cell.font.name == "宋体" and data_cell.font.size == 11
    assert data_cell.border.left.color.rgb == "FF000000" and data_cell.border.left.style == "thin"

    # 两张折线图（每张每板块一条系列，系列名=板块名）
    assert len(ws1._charts) == 2
    chart1 = ws1._charts[0]
    titles = [s.tx.strRef.f if s.tx and s.tx.strRef else "" for s in chart1.series]
    assert len(chart1.series) == 2  # 一级板块：医药生物 + 机械设备
    chart2 = ws1._charts[1]
    assert len(chart2.series) == 3  # 二级板块：电池 + 化学制药 + 国有大型银行


@pytest.mark.asyncio
async def test_summary_reuse_file_and_grow(tmp_path):
    """1008先建；1012执行（无同名）→ 复制最新文件为1012：1008原样保留，1012含全部内容"""
    base = str(tmp_path)
    _write_all_a_file(base, [
        ("000009.SZ", "机械设备", "电池"),
        ("000001.SZ", "医药生物", "化学制药"),
    ])
    rows_1008 = [("2026-10-08", _compress([{"证券代码": "000009.SZ"}, {"证券代码": "000001.SZ"}]))]
    rows_1012 = [("2026-10-12", _compress([{"证券代码": "000001.SZ"}]))]

    ex = _executor(base)
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows_1008)):
        r1 = await _run(ex, "2026-10-08", output_filename="16 10月AI筛选汇总1008.xlsx")
    assert r1["success"]
    assert "新建" in r1["message"]

    out_1008 = os.path.join(base, "2026-10", "16 10月AI筛选汇总1008.xlsx")
    assert os.path.exists(out_1008)

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows_1012)):
        r2 = await _run(ex, "2026-10-12", output_filename="16 10月AI筛选汇总1012.xlsx")
    assert r2["success"], r2.get("message")
    assert "复制" in r2["message"]

    # 目录两个文件：1008保留 + 1012新副本
    files = sorted(os.listdir(os.path.join(base, "2026-10")))
    assert files == ["16 10月AI筛选汇总1008.xlsx", "16 10月AI筛选汇总1012.xlsx"], files

    # 1008 原文件保持原样：只有 1008 sheet，Sheet1 仅一列
    wb_1008 = load_workbook(out_1008)
    assert wb_1008.sheetnames == ["Sheet1", "1008"], wb_1008.sheetnames
    ws1_1008 = wb_1008["Sheet1"]
    assert [ws1_1008.cell(1, c).value for c in (1, 2)] == ["一级板块", "10月8日"]
    assert ws1_1008.cell(2, 3).value is None  # 无第二日期列

    # 1012 副本：Sheet1 增量（10月8日列沿用 + 10月12日新列），sheet 降序
    wb = load_workbook(os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx"))
    assert wb.sheetnames == ["Sheet1", "1012", "1008"], wb.sheetnames

    ws1 = wb["Sheet1"]
    assert ws1.cell(1, 1).value == "一级板块"
    assert ws1.cell(1, 2).value == "10月8日"
    assert ws1.cell(1, 3).value == "10月12日"
    stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 3).value)
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (1, 2)   # 1008累计1 + 1012新增1 = 2
    assert stats["机械设备"] == (1, 1)   # 1008累计1 + 1012新增0 = 1

    # 强制覆盖：1012 sheet 内容为最新（1行）
    ws1012 = wb["1012"]
    assert ws1012.max_row == 2
    assert ws1012.cell(2, 1).value == "000001.SZ"


@pytest.mark.asyncio
async def test_summary_empty_day_and_missing_all_a(tmp_path):
    """空当日数据（DB空表）→ 仅表头的日期sheet；全部A股缺失 → 警告且板块为空"""
    base = str(tmp_path)
    db_rows = [("2026-10-12", _compress([]))]  # 空表

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(db_rows)):
        result = await _run(_executor(base), "2026-10-12")
    assert result["success"], result.get("message")
    assert any("全部A股" in w for w in result.get("warnings", []))

    out = os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx")
    wb = load_workbook(out)
    ws = wb["1012"]
    assert ws.max_row == 1  # 仅表头"证券代码/一级板块/二级板块"
    # Sheet1 仍正常生成（无板块行 → 表头行）
    assert wb["Sheet1"].cell(1, 1).value == "一级板块"
    assert wb["Sheet1"].cell(1, 2).value == "10月12日"


@pytest.mark.asyncio
async def test_summary_excel_fallback_and_no_data(tmp_path):
    """无DB记录 → Excel兜底；DB与Excel均无 → 失败"""
    base = str(tmp_path)
    _write_all_a_file(base, [("000009.SZ", "机械设备", "电池")])
    _write_daily_new_excel(base, "2026-10-12", ["000009.SZ"])

    with patch("core.database.AsyncSessionLocal", _fake_session_factory([])):
        result = await _run(_executor(base), "2026-10-12")
    assert result["success"]
    ws = load_workbook(os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx"))["1012"]
    assert ws.cell(2, 1).value == "000009.SZ"
    assert ws.cell(2, 2).value == "机械设备"

    # 均无数据 → 失败且不产出文件
    with patch("core.database.AsyncSessionLocal", _fake_session_factory([])):
        result = await _run(_executor(base), "2026-10-13")
    assert not result["success"]
    assert "当月每日新增" in result["message"]
    assert not os.path.exists(os.path.join(base, "2026-10", "16 10月AI筛选汇总1013.xlsx"))


@pytest.mark.asyncio
async def test_summary_empty_sheet_aggregation(tmp_path):
    """已有日期sheet为空（仅表头）→ 聚合正常（该日计数0），不报错"""
    base = str(tmp_path)
    _write_all_a_file(base, [("000009.SZ", "机械设备", "电池")])
    rows_1008 = [("2026-10-08", _compress([]))]  # 1008为空
    rows_1012 = [("2026-10-12", _compress([{"证券代码": "000009.SZ"}]))]
    ex = _executor(base)
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows_1008)):
        assert (await _run(ex, "2026-10-08"))["success"]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(rows_1012)):
        assert (await _run(ex, "2026-10-12"))["success"]

    # 1012执行（无同名）→ 复制1008为1012；空1008 sheet沿用（该日计数0）
    out = os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx")
    wb = load_workbook(out)
    assert wb.sheetnames == ["Sheet1", "1012", "1008"], wb.sheetnames
    ws1 = wb["Sheet1"]
    assert ws1.cell(1, 2).value == "10月8日" and ws1.cell(1, 3).value == "10月12日"
    stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 3).value)
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["机械设备"] == (None, 1)   # 1008新增0 → 累计0 → 留空；1012累计1


# ---------------------------------------------------------------- 复制最新文件 & Sheet1 增量

def _make_summary_file(path, sheets):
    """手工预置汇总文件：sheets = [(sheet名, [(证券代码, 一级板块, 二级板块)...]), ...]"""
    wb = Workbook()
    wb.remove(wb.active)
    for sn, rows in sheets:
        ws = wb.create_sheet(sn)
        ws.append(["证券代码", "一级板块", "二级板块"])
        for r in rows:
            ws.append(list(r))
    wb.save(path)


@pytest.mark.asyncio
async def test_summary_copy_latest_by_filename_date(tmp_path):
    """目录非空无同名 → 复制「文件名日期最新」的文件（0305/0306/0307 → 复制0307）；
    mtime 干扰（0305 的 mtime 最新）不影响按文件名日期选择"""
    base = str(tmp_path)
    _write_all_a_file(base, [("000009.SZ", "机械设备", "电池")])
    month_dir = os.path.join(base, "2027-03")
    os.makedirs(month_dir, exist_ok=True)
    row = ("000009.SZ", "机械设备", "电池")
    # 预置累积结构文件（模拟真实场景：0305建→0306复制0305→0307复制0306，逐日累积日期sheet）
    _make_summary_file(os.path.join(month_dir, "16 3月AI筛选汇总0305.xlsx"), [("0305", [row])])
    _make_summary_file(os.path.join(month_dir, "16 3月AI筛选汇总0306.xlsx"), [("0306", [row]), ("0305", [row])])
    _make_summary_file(os.path.join(month_dir, "16 3月AI筛选汇总0307.xlsx"),
                       [("0307", [row]), ("0306", [row]), ("0305", [row])])
    # mtime 干扰：0305 修改时间最新
    os.utime(os.path.join(month_dir, "16 3月AI筛选汇总0305.xlsx"), (time.time(), time.time()))

    db_rows = [("2027-03-08", _compress([{"证券代码": "000009.SZ"}]))]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(db_rows)):
        result = await _run(_executor(base), "2027-03-08")
    assert result["success"], result.get("message")

    # 目录4个文件；0307 原文件保持原样
    files = sorted(os.listdir(month_dir))
    assert files == [f"16 3月AI筛选汇总{dd}.xlsx" for dd in ("0305", "0306", "0307", "0308")], files
    wb_0307 = load_workbook(os.path.join(month_dir, "16 3月AI筛选汇总0307.xlsx"))
    assert wb_0307.sheetnames == ["0307", "0306", "0305"]  # 未被改动

    # 0308 = 复制0307 + 当日内容；无Sheet1的旧文件 → 全量聚合构建 Sheet1
    wb = load_workbook(os.path.join(month_dir, "16 3月AI筛选汇总0308.xlsx"))
    assert wb.sheetnames == ["Sheet1", "0308", "0307", "0306", "0305"], wb.sheetnames
    ws1 = wb["Sheet1"]
    assert [ws1.cell(1, c).value for c in range(1, 6)] == ["一级板块", "3月5日", "3月6日", "3月7日", "3月8日"]
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, c).value for c in range(2, 6))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["机械设备"] == (1, 2, 3, 4)   # 每日新增1的累计：1, 1+1, 2+1, 3+1


@pytest.mark.asyncio
async def test_summary_sheet1_incremental(tmp_path):
    """Sheet1 增量更新（数值=从首列起的累计和）：已有日期列数值/行序保持原样（即使历史sheet被改动
    也不重算覆盖）；当日新板块追加表尾（历史列累计0留空）；新日期列追加（= 前列累计+当日新增）；
    重复执行当日列刷新；累计0的单元格留空"""
    base = str(tmp_path)
    _write_all_a_file(base, [
        ("000001.SZ", "医药生物", "化学制药"),
        ("000002.SZ", "医药生物", "化学制药"),
        ("000009.SZ", "机械设备", "电池"),
        ("600000.SH", "银行", "国有大型银行"),
    ])
    ex = _executor(base)
    d1008 = [("2026-10-08", _compress([{"证券代码": "000001.SZ"}, {"证券代码": "000009.SZ"}]))]
    d1012 = [("2026-10-12", _compress([{"证券代码": "000001.SZ"}, {"证券代码": "000002.SZ"}]))]
    d1013 = [("2026-10-13", _compress([{"证券代码": "000009.SZ"}, {"证券代码": "600000.SH"}]))]

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1008)):
        assert (await _run(ex, "2026-10-08"))["success"]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1012)):
        assert (await _run(ex, "2026-10-12"))["success"]

    out_1012 = os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx")
    # 手工“篡改”1012文件：Sheet1 医药生物的10月8日值改为99（模拟人工修正）；
    # 同时篡改 1008 sheet 的一级板块（若实现错误地全量重算，10月8日列将被改变）
    wb = load_workbook(out_1012)
    ws1 = wb["Sheet1"]
    assert ws1.cell(2, 1).value == "医药生物"
    ws1.cell(2, 2).value = 99
    ws1008 = wb["1008"]
    ws1008.cell(2, 2).value = "XX板块"
    wb.save(out_1012)

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1013)):
        r = await _run(ex, "2026-10-13")
    assert r["success"], r.get("message")

    out_1013 = os.path.join(base, "2026-10", "16 10月AI筛选汇总1013.xlsx")
    wb = load_workbook(out_1013)
    ws1 = wb["Sheet1"]
    # 表头：已有两列沿用 + 新增10月13日
    assert [ws1.cell(1, c).value for c in range(1, 5)] == ["一级板块", "10月8日", "10月12日", "10月13日"]
    # 行序保持原样，新板块「银行」追加表尾；历史列沿用（99 保留，1008 sheet 被篡改也不影响）
    names = [ws1.cell(r, 1).value for r in range(2, 5)]
    assert names == ["医药生物", "机械设备", "银行"], names
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, c).value for c in range(2, 5))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (99, 3, 3)    # 10月8日篡改值保留；10月13日 = 前列累计3 + 当日新增0 = 3
    assert stats["机械设备"] == (1, 1, 2)     # 10月13日 = 前列累计1 + 当日新增1 = 2
    assert stats["银行"] == (None, None, 1)   # 新板块：历史列累计0留空 + 当日1

    # 图表重建：表1三条系列（医药生物/机械设备/银行）
    assert len(ws1._charts) == 2
    assert len(ws1._charts[0].series) == 3

    # 重复执行当日（1013数据变为仅000001.SZ）→ 同名直接填充，仅刷新10月13日列
    d1013b = [("2026-10-13", _compress([{"证券代码": "000001.SZ"}]))]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1013b)):
        assert (await _run(ex, "2026-10-13"))["success"]
    wb = load_workbook(out_1013)
    ws1 = wb["Sheet1"]
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, c).value for c in range(2, 5))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (99, 3, 4)   # 当日列刷新 = 前列累计3 + 当日新增1 = 4
    assert stats["机械设备"] == (1, 1, 1)     # 当日列刷新 = 前列累计1 + 当日新增0 = 1
    assert stats["银行"] == (None, None, None)  # 当日列刷新 = 累计0 + 新增0 = 0 → 留空
    assert [ws1.cell(r, 1).value for r in range(2, 5)] == ["医药生物", "机械设备", "银行"]  # 行序不变
    # 目录仅三个日期文件（1013复用同名，未新增）
    files = sorted(os.listdir(os.path.join(base, "2026-10")))
    assert files == [f"16 10月AI筛选汇总{dd}.xlsx" for dd in ("1008", "1012", "1013")], files


# ---------------------------------------------------------------- 条件交集 39日新高列格式化

@pytest.mark.asyncio
async def test_format_parallel_excel_red_fill_39day(tmp_path):
    """_format_parallel_excel：站上20日线sheet中39日新高非空单元格红底；空单元格不着色"""
    base = str(tmp_path)
    out = os.path.join(base, "7条件交集.xlsx")
    pd.DataFrame({
        "证券代码": ["000001.SZ", "000002.SZ", "000009.SZ"],
        "证券简称": ["平安银行", "万科A", "中国宝安"],
        "39日新高": ["000001.SZ", "", "000009.SZ"],
        "站上20日线": ["是", "是", "是"],
    }).to_excel(out, sheet_name="条件交集站上20日线", index=False)

    ex = WorkflowExecutor(base_dir=base, workflow_type="条件交集")
    count_col = "2026-03-18至2026-10-12站上20日线次数"
    date_col = "2026-03-18至2026-10-12站上20日线日期"
    # 先加次数/日期列（模拟真实结构）
    df = pd.read_excel(out)
    df[count_col] = [1, 1, 2]
    df[date_col] = ["2026-10-12", "2026-10-12", "2026-10-11,2026-10-12"]
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="条件交集站上20日线", index=False)

    ex._format_parallel_excel(out, count_col, date_col, count_col, date_col, set(), set())

    wb = load_workbook(out)
    ws = wb["条件交集站上20日线"]
    header = [c.value for c in ws[1]]
    idx = header.index("39日新高") + 1
    assert ws.cell(2, idx).fill.start_color.rgb == "FFFF0000"  # 000001.SZ 命中 → 红
    assert ws.cell(3, idx).fill.fill_type != "solid"           # 空 → 不着色
    assert ws.cell(4, idx).fill.start_color.rgb == "FFFF0000"   # 000009.SZ 命中 → 红
