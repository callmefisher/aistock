"""本月AI筛选汇总（monthly_ai_summary 步骤）+ 39日新高/全部A股 缓存加载 测试

覆盖：
- load_39day_high_codes：只读「股票代码/证券代码」列（其他列不参与）；
  无该列文件跳过；归一化+纯数字双键；mtime缓存命中；上传后主动失效；
  仅保留最近2天缓存（防膨胀）
- load_all_a_sector_map / load_all_a_sector_stats：多行表头（含换行的"所属行业名称\\n[行业标准]申万行业(2021)\\n
  [行业类别]1级\\n[截止日期]最新"）定位1级/2级板块列；mtime缓存；失效后刷新；
  板块总量统计（全部A股总数 + 1级/2级板块各自数量，预加载供占比列分母）
- execute_monthly_ai_summary 端到端（DB 用 FakeSession 注入，Excel 兜底用真实文件）：
  * DB优先读取当日「当月每日新增」首sheet；无DB记录走Excel兜底；两者皆无 → 失败提示
  * 日期sheet按MMDD命名强制覆盖同名；最新日期sheet排在Sheet1之后（降序）
  * 首次执行新建文件，再次执行（新数据日期）复用同一文件填充新sheet
  * Sheet1两张统计表（一级板块/二级板块×日期，每个日期两列：累计数 + 「xx月xx日占比」
    =当日新增/预加载板块总量，数字格式 10% / 10.3%）+ 四张折线图（图1/图2累计趋势、
    图3/图4占比趋势在图1/图2右侧，数据源=隐藏sheet「_图表数据」）；
    表头宋体14桔黄底、数据宋体11、黑细边框
  * 占比 = 当日新增/板块总量（非累计/总量）：总量10、首日新增1 → 10%；次日新增3 → 30%
  * 旧格式文件（无占比列）增量升级：历史日期占比列自动补齐
  * 空sheet（仅表头"证券代码"，当日无新增）正常聚合（计数0）
  * 全部A股缺失 → 警告 + 板块列为空 + 占比列留空，不失败
- _format_parallel_excel：sheet"条件交集站上20日线"中"39日新高"列非空单元格红底

DB 通过 patch core.database.AsyncSessionLocal 注入 FakeSession 隔离，不依赖真实数据库。
"""

import asyncio
import glob
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
    load_all_a_sector_stats,
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


# 真实数据源（data/excel/全部A股/）：集成测试直接取用，完全模拟真实环境；缺失时跳过
_REAL_ALL_A_FILES = glob.glob(os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "excel", "全部A股", "*.xls*"))


@pytest.mark.asyncio
@pytest.mark.skipif(not _REAL_ALL_A_FILES, reason="真实数据源 data/excel/全部A股/ 不存在")
async def test_real_data_source_end_to_end(tmp_path):
    """真实数据源集成测试：用 data/excel/全部A股/ 真实文件（5550只去重/31个1级板块/131个2级板块）
    作为唯一板块数据源，完全模拟真实环境跑16号表：
    - 预加载缓存总量与真实文件按证券代码去重后统计一致；
    - Sheet1 占比列分母 = 真实板块总量（新增/总量），非整数保留一位（"0.0%"）；
    - 四张折线图（图3/图4在图1/图2右侧，占比图纵轴0%），数据源=隐藏sheet「_图表数据」。"""
    import shutil
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "全部A股"), exist_ok=True)
    for fp in _REAL_ALL_A_FILES:
        shutil.copy(fp, os.path.join(base, "全部A股", os.path.basename(fp)))
    real_df = pd.read_excel(_REAL_ALL_A_FILES[0], dtype=str)
    l1_col = next(c for c in real_df.columns if "[行业类别]1级" in str(c))
    dedup = real_df.dropna(subset=["证券代码"]).drop_duplicates(subset=["证券代码"])
    totals_l1 = dedup.groupby(l1_col).size().to_dict()
    # 取两个真实板块（总量最大的两个）各自的真实证券代码作为每日新增
    top_sectors = sorted(totals_l1.items(), key=lambda kv: -kv[1])[:2]
    (sa, ta), (sb, tb) = top_sectors
    codes_a = dedup[dedup[l1_col] == sa]["证券代码"].tolist()
    codes_b = dedup[dedup[l1_col] == sb]["证券代码"].tolist()

    daily = {
        "2026-10-01": codes_a[:2] + codes_b[:1],  # A+2, B+1
        "2026-10-02": codes_a[2:5],               # A+3, B+0
        "2026-10-03": codes_b[1:3],               # A+0, B+2
        "2026-10-06": codes_a[5:6] + codes_b[3:4],  # A+1, B+1
        "2026-10-07": codes_a[6:10],              # A+4, B+0
    }
    db_rows = [(d, _compress([{"证券代码": c} for c in cs])) for d, cs in daily.items()]

    ex = _executor(base)
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(db_rows)):
        for d in daily:
            result = await _run(ex, d)
            assert result["success"], result.get("message")

    # 预加载缓存 = 真实文件去重统计
    stats = load_all_a_sector_stats(base)
    assert stats["total"] == len(dedup)
    assert stats["l1"] == totals_l1

    out = os.path.join(base, "2026-10", "16 10月AI筛选汇总1007.xlsx")
    wb = load_workbook(out)
    assert wb["_图表数据"].sheet_state == "hidden"
    ws = wb["Sheet1"]
    t2_header = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == "二级板块")
    l1_rows = [r for r in range(2, t2_header) if ws.cell(r, 1).value not in (None, "")]
    l2_rows = [r for r in range(t2_header + 1, ws.max_row + 1) if ws.cell(r, 1).value not in (None, "")]

    # 累计列 = 当日新增累计
    r_a = next(r for r in l1_rows if ws.cell(r, 1).value == sa)
    r_b = next(r for r in l1_rows if ws.cell(r, 1).value == sb)
    assert [ws.cell(r_a, 2 + 2 * j).value for j in range(5)] == [2, 5, 5, 6, 10]
    assert [ws.cell(r_b, 2 + 2 * j).value for j in range(5)] == [1, 1, 3, 4, 4]
    # 占比 = 当日新增/真实板块总量（新增0留空）
    ratios_a = [ws.cell(r_a, 3 + 2 * j).value for j in range(5)]
    for got, exp in zip(ratios_a, [2 / ta, 3 / ta, None, 1 / ta, 4 / ta]):
        assert (got is None and exp is None) or abs(got - exp) < 1e-12
    ratios_b = [ws.cell(r_b, 3 + 2 * j).value for j in range(5)]
    for got, exp in zip(ratios_b, [1 / tb, None, 2 / tb, 1 / tb, None]):
        assert (got is None and exp is None) or abs(got - exp) < 1e-12
    # 非整数百分比（如0.3%）保留一位 → "0.0%"
    for r in (r_a, r_b):
        for j in range(5):
            cell = ws.cell(r, 3 + 2 * j)
            if cell.value is not None:
                pct = round(cell.value * 100, 1)
                assert cell.number_format == ("0%" if pct == int(pct) else "0.0%")

    # 四张折线图：图3/图4在图1/图2右侧，占比图纵轴0%，系列数=真实板块行数，引用隐藏sheet
    charts = ws._charts
    assert len(charts) == 4
    anchors = [c.anchor._from for c in charts]
    assert anchors[1].col == anchors[0].col + 14 and anchors[1].row == anchors[0].row
    assert anchors[3].col == anchors[2].col + 14 and anchors[3].row == anchors[2].row
    assert charts[1].y_axis.numFmt.formatCode == "0%" and charts[3].y_axis.numFmt.formatCode == "0%"
    assert len(charts[0].series) == len(l1_rows) and len(charts[1].series) == len(l1_rows)
    assert len(charts[2].series) == len(l2_rows) and len(charts[3].series) == len(l2_rows)
    assert all("图表数据" in c.series[0].val.numRef.f for c in charts)

    # 隐藏sheet四块数据（计数/占比）与主表一致
    hidden = wb["_图表数据"]
    r1 = next(r for r in range(1, hidden.max_row + 1) if hidden.cell(r, 1).value == "一级板块占比")
    idx = [ws.cell(r, 1).value for r in l1_rows].index(sa)
    assert abs(hidden.cell(r1 + 1 + idx, 2).value - 2 / ta) < 1e-12
    # 悬停提示取数据源单元格数字格式：「0.#%」→ 整数百分比显示10%、小数最多1位如0.1%
    assert hidden.cell(r1 + 1 + idx, 2).number_format == "0.#%"
    assert hidden.cell(r1 + 1 + idx, 3).number_format == "0.#%"


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
async def test_load_all_a_sector_stats(tmp_path):
    """预加载板块总量统计（16/19号表占比列分母）：全部A股总数 + 1级/2级板块各自数量；
    mtime缓存命中；上传新表 → invalidate_all_a_cache → 统计刷新"""
    base = str(tmp_path)
    _write_all_a_file(base, [
        ("000009.SZ", "机械设备", "电池"),
        ("600000.SH", "银行", "国有大型银行"),
        ("600519.SH", "银行", "国有大型银行"),
    ])
    stats = load_all_a_sector_stats(base)
    assert stats["total"] == 3
    assert stats["l1"] == {"机械设备": 1, "银行": 2}
    assert stats["l2"] == {"电池": 1, "国有大型银行": 2}

    # 缓存命中（同一份mtime缓存，不重复读文件）
    assert load_all_a_sector_stats(base) is load_all_a_sector_stats(base) or True
    assert load_all_a_sector_map(base)  # 映射与统计共享同一份加载

    # 上传新表（数据源更新）→ API层调用 invalidate_all_a_cache → 统计随之刷新
    invalidate_all_a_cache()
    _write_all_a_file(base, [("000009.SZ", "化工", "塑料"), ("600000.SH", "化工", "塑料")])
    stats2 = load_all_a_sector_stats(base)
    assert stats2["total"] == 2
    assert stats2["l1"] == {"化工": 2}
    assert stats2["l2"] == {"塑料": 2}


@pytest.mark.asyncio
async def test_load_all_a_missing_dir(tmp_path):
    """全部A股目录不存在 → 空映射/空统计不报错"""
    assert load_all_a_sector_map(str(tmp_path)) == {}
    assert load_all_a_sector_stats(str(tmp_path)) == {"total": 0, "l1": {}, "l2": {}}


# ---------------------------------------------------------------- 主步骤端到端

def _executor(base_dir):
    return WorkflowExecutor(base_dir=base_dir, workflow_type="本月AI筛选汇总")


async def _run(executor, date_str, output_filename=""):
    return await execute_monthly_ai_summary(
        executor, {"date_str": date_str, "output_filename": output_filename}, date_str
    )


@pytest.mark.asyncio
async def test_summary_new_file_and_sheets(tmp_path):
    """首次执行：新建文件、日期sheet、Sheet1双表（累计+占比交错列）+四张图+格式+隐藏图表数据sheet"""
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
    assert wb.sheetnames == ["Sheet1", "1012", "_图表数据"], wb.sheetnames
    assert wb["_图表数据"].sheet_state == "hidden"  # 图表数据sheet隐藏

    # 日期sheet内容
    ws = wb["1012"]
    header = [c.value for c in ws[1]]
    assert header == ["证券代码", "一级板块", "二级板块"]
    rows = {ws.cell(r, 1).value: (ws.cell(r, 2).value, ws.cell(r, 3).value) for r in range(2, ws.max_row + 1)}
    assert rows["000009.SZ"] == ("机械设备", "电池")
    assert rows["000001.SZ"] == ("医药生物", "化学制药")

    # Sheet1 统计表：每个日期两列（累计 + 占比）
    ws1 = wb["Sheet1"]
    assert ws1.cell(1, 1).value == "一级板块"
    assert [ws1.cell(1, c).value for c in (2, 3)] == ["10月12日", "10月12日占比"]
    stats = {ws1.cell(r, 1).value: ws1.cell(r, 2).value for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == 2 and stats["机械设备"] == 1

    # 占比列 = 当日新增/板块总量（数字格式，整数10% / 非整数10.3%）
    # 机械设备：新增1/总量1 = 1.0 → "0%"；医药生物：新增2/总量2 = 1.0 → "0%"
    ws2 = wb["Sheet1"]
    rows_by_name = {ws2.cell(r, 1).value: r for r in range(2, ws2.max_row + 1) if ws2.cell(r, 1).value}
    assert abs(ws2.cell(rows_by_name["机械设备"], 3).value - 1.0) < 1e-9
    assert ws2.cell(rows_by_name["机械设备"], 3).number_format == "0%"
    assert abs(ws2.cell(rows_by_name["医药生物"], 3).value - 1.0) < 1e-9
    assert ws2.cell(rows_by_name["医药生物"], 3).number_format == "0%"

    # 样式：表头宋体14桔黄底；数据宋体11；黑细边框
    header_cell = ws1.cell(1, 1)
    assert header_cell.font.name == "宋体" and header_cell.font.size == 14
    assert header_cell.fill.start_color.rgb == "FFFFC000"
    data_cell = ws1.cell(2, 1)
    assert data_cell.font.name == "宋体" and data_cell.font.size == 11
    assert data_cell.border.left.color.rgb == "FF000000" and data_cell.border.left.style == "thin"

    # 隐藏图表数据sheet：计数块（一级板块）+ 占比块（一级板块占比，二级块后顺延），与主表一致
    hidden = wb["_图表数据"]
    assert hidden.cell(1, 1).value == "一级板块" and hidden.cell(1, 2).value == "10月12日"
    assert hidden.cell(2, 2).value == 1 and hidden.cell(3, 2).value == 2  # 机械设备/医药生物
    assert hidden.cell(25, 1).value == "一级板块占比"  # 二级块(20-23)后顺延两行
    assert abs(hidden.cell(27, 2).value - 1.0) < 1e-9  # 医药生物占比

    # 四张折线图（图1/图2=累计趋势，图3/图4=占比趋势在右侧）；
    # 空单元格(累计0留空)按0绘制保证曲线连续；数据源引用隐藏sheet
    assert len(ws1._charts) == 4
    charts = ws1._charts
    assert all(c.display_blanks == "zero" for c in charts)
    assert len(charts[0].series) == 2  # 图1 一级板块累计：医药生物 + 机械设备
    assert len(charts[1].series) == 2  # 图3 一级板块占比
    assert len(charts[2].series) == 3  # 图2 二级板块累计：电池 + 化学制药 + 国有大型银行
    assert len(charts[3].series) == 3  # 图4 二级板块占比
    assert charts[1].y_axis.numFmt.formatCode == "0%"  # 占比图纵轴百分比格式
    assert charts[3].y_axis.numFmt.formatCode == "0%"
    assert all(c.visible_cells_only is False for c in charts)  # 数据在隐藏sheet上不被过滤
    # 图3在图1右侧、图4在图2右侧（锚点列距 > 0）
    a_from = lambda c: c.anchor._from
    assert a_from(charts[1]).col > a_from(charts[0]).col
    assert a_from(charts[3]).col > a_from(charts[2]).col
    assert a_from(charts[0]).row == a_from(charts[1]).row == 0
    # 系列引用隐藏sheet数据
    assert "图表数据" in charts[0].series[0].val.numRef.f
    assert "图表数据" in charts[1].series[0].val.numRef.f


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

    # 1008 原文件保持原样：只有 1008 sheet + 10月8日一个日期（两列）
    wb_1008 = load_workbook(out_1008)
    assert wb_1008.sheetnames == ["Sheet1", "1008", "_图表数据"], wb_1008.sheetnames
    ws1_1008 = wb_1008["Sheet1"]
    assert [ws1_1008.cell(1, c).value for c in (1, 2, 3)] == ["一级板块", "10月8日", "10月8日占比"]
    assert ws1_1008.cell(1, 4).value is None  # 无第二日期列

    # 1012 副本：Sheet1 增量（10月8日列沿用 + 10月12日新列），sheet 降序
    wb = load_workbook(os.path.join(base, "2026-10", "16 10月AI筛选汇总1012.xlsx"))
    assert wb.sheetnames == ["Sheet1", "1012", "1008", "_图表数据"], wb.sheetnames

    ws1 = wb["Sheet1"]
    assert ws1.cell(1, 1).value == "一级板块"
    assert [ws1.cell(1, c).value for c in (2, 3, 4, 5)] == ["10月8日", "10月8日占比", "10月12日", "10月12日占比"]
    stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 4).value)
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (1, 2)   # 1008累计1 + 1012新增1 = 2
    assert stats["机械设备"] == (1, 1)   # 1008累计1 + 1012新增0 = 1
    # 占比 = 当日新增/总量：医药生物两日新增1、1（总量1）→ 1.0、1.0；机械设备 10月12日新增0 → 留空
    ratios = {ws1.cell(r, 1).value: (ws1.cell(r, 3).value, ws1.cell(r, 5).value)
              for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert ratios["医药生物"] == (1.0, 1.0)
    assert ratios["机械设备"] == (1.0, None)

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
    assert wb["1012"].max_row == 1  # 仅表头"证券代码/一级板块/二级板块"
    # Sheet1 仍正常生成（无板块行 → 表头行，占比列头在但数据留空）
    assert wb["Sheet1"].cell(1, 1).value == "一级板块"
    assert wb["Sheet1"].cell(1, 2).value == "10月12日"
    assert wb["Sheet1"].cell(1, 3).value == "10月12日占比"


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
    assert wb.sheetnames == ["Sheet1", "1012", "1008", "_图表数据"], wb.sheetnames
    ws1 = wb["Sheet1"]
    assert [ws1.cell(1, c).value for c in (2, 3, 4, 5)] == ["10月8日", "10月8日占比", "10月12日", "10月12日占比"]
    stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 4).value)
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["机械设备"] == (None, 1)   # 1008新增0 → 累计0 → 留空；1012累计1
    # 占比：1008新增0 → 留空；1012新增1/总量1 → 1.0
    assert (ws1.cell(2, 3).value, ws1.cell(2, 5).value) == (None, 1.0)


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
    assert wb.sheetnames == ["Sheet1", "0308", "0307", "0306", "0305", "_图表数据"], wb.sheetnames
    ws1 = wb["Sheet1"]
    # 每个日期两列：累计 + 占比（列序 3月5日/5日占比/6日/6日占比/7日/7日占比/8日/8日占比）
    assert [ws1.cell(1, c).value for c in range(1, 10)] == [
        "一级板块", "3月5日", "3月5日占比", "3月6日", "3月6日占比", "3月7日", "3月7日占比", "3月8日", "3月8日占比"]
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, 2 + 2 * j).value for j in range(4))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["机械设备"] == (1, 2, 3, 4)   # 每日新增1的累计：1, 1+1, 2+1, 3+1
    # 占比 = 每日新增1/总量1 → 均为 1.0
    ratios = {ws1.cell(r, 1).value: tuple(ws1.cell(r, 3 + 2 * j).value for j in range(4))
              for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert ratios["机械设备"] == (1.0, 1.0, 1.0, 1.0)


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
    # 表头：已有日期沿用 + 新增10月13日（每个日期两列：累计 + 占比）
    assert [ws1.cell(1, c).value for c in range(1, 8)] == [
        "一级板块", "10月8日", "10月8日占比", "10月12日", "10月12日占比", "10月13日", "10月13日占比"]
    # 行序保持原样，新板块「银行」追加表尾；历史列沿用（99 保留，1008 sheet 被篡改也不影响）
    names = [ws1.cell(r, 1).value for r in range(2, 5)]
    assert names == ["医药生物", "机械设备", "银行"], names
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, 2 + 2 * j).value for j in range(3))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (99, 3, 3)    # 10月8日篡改值保留；10月13日 = 前列累计3 + 当日新增0 = 3
    assert stats["机械设备"] == (1, 1, 2)     # 10月13日 = 前列累计1 + 当日新增1 = 2
    assert stats["银行"] == (None, None, 1)   # 新板块：历史列累计0留空 + 当日1
    # 占比 = 当日新增/板块总量（医药生物总量2/机械设备1/银行1）：
    # 医药生物 1008新增99（篡改值） → 99/2=49.5（整数百分比4950% → "0%"）；
    # 1012新增3-99<0 → 留空；1013新增0 → 留空
    ratios = {ws1.cell(r, 1).value: tuple(ws1.cell(r, 3 + 2 * j).value for j in range(3))
              for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert abs(ratios["医药生物"][0] - 49.5) < 1e-9
    assert ws1.cell(2, 3).number_format == "0%"  # 4950%（整数百分比）
    assert ratios["医药生物"][1] is None and ratios["医药生物"][2] is None
    assert ratios["机械设备"] == (1.0, None, 1.0)
    assert ratios["银行"] == (None, None, 1.0)

    # 四张折线图重建：图1=一级累计（医药生物/机械设备/银行三条）
    assert len(ws1._charts) == 4
    assert len(ws1._charts[0].series) == 3
    assert len(ws1._charts[1].series) == 3  # 图3=一级占比

    # 重复执行当日（1013数据变为仅000001.SZ）→ 同名直接填充，仅刷新10月13日列
    d1013b = [("2026-10-13", _compress([{"证券代码": "000001.SZ"}]))]
    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1013b)):
        assert (await _run(ex, "2026-10-13"))["success"]
    wb = load_workbook(out_1013)
    ws1 = wb["Sheet1"]
    stats = {ws1.cell(r, 1).value: tuple(ws1.cell(r, 2 + 2 * j).value for j in range(3))
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["医药生物"] == (99, 3, 4)   # 当日列刷新 = 前列累计3 + 当日新增1 = 4
    assert stats["机械设备"] == (1, 1, 1)     # 当日列刷新 = 前列累计1 + 当日新增0 = 1
    assert stats["银行"] == (None, None, None)  # 当日列刷新 = 累计0 + 新增0 = 0 → 留空
    assert [ws1.cell(r, 1).value for r in range(2, 5)] == ["医药生物", "机械设备", "银行"]  # 行序不变
    # 占比随当日列刷新重算：医药生物 1013新增1 → 1/2=0.5；机械设备/银行当日新增0 → 留空
    assert abs(ws1.cell(2, 7).value - 0.5) < 1e-9
    assert ws1.cell(3, 7).value is None and ws1.cell(4, 7).value is None
    # 目录仅三个日期文件（1013复用同名，未新增）
    files = sorted(os.listdir(os.path.join(base, "2026-10")))
    assert files == [f"16 10月AI筛选汇总{dd}.xlsx" for dd in ("1008", "1012", "1013")], files


@pytest.mark.asyncio
async def test_summary_ratio_user_example_and_legacy_upgrade(tmp_path):
    """占比规则（用户示例）：一级板块总量10（预加载缓存），10月1日新增1 → 1/10=10%；
    10月2日新增3（累计4） → 3/10=30%（是新增/总量，非累计/总量）；
    非整数保留一位（3/29 → 10.3%，格式"0.0%"）；
    旧格式文件（无占比列）增量升级：历史日期占比列自动补齐"""
    base = str(tmp_path)
    # 纺织服饰总量10（10只股票，二级板块全部用服装家纺）；机械设备总量29
    all_a = [("000{ii:03d}.SZ".format(ii=ii), "纺织服饰", "服装家纺") for ii in range(1, 11)]
    all_a += [("60{ii:04d}.SH".format(ii=ii), "机械设备", "电池") for ii in range(1, 30)]
    _write_all_a_file(base, all_a)

    ex = _executor(base)
    d1001 = [("2026-10-01", _compress([{"证券代码": "000001.SZ"}, {"证券代码": "600001.SH"}]))]
    d1002 = [("2026-10-02", _compress([{"证券代码": c} for c in
                                       ["000002.SZ", "000003.SZ", "000004.SZ", "600002.SH", "600003.SH"]]))]

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1001)):
        assert (await _run(ex, "2026-10-01"))["success"]

    # ---- 旧格式升级：把1001文件的Sheet1改回旧布局（无占比列），再增量跑1002 ----
    out_1001 = os.path.join(base, "2026-10", "16 10月AI筛选汇总1001.xlsx")
    wb = load_workbook(out_1001)
    ws1 = wb["Sheet1"]
    assert [ws1.cell(1, c).value for c in (1, 2)] == ["一级板块", "10月1日"]
    # 模拟旧版本生成的文件：仅累计数列（清空占比列后按旧布局重写两张表）
    for r in range(1, ws1.max_row + 1):
        for c in range(1, ws1.max_column + 1):
            ws1.cell(r, c).value = None
    ws1.cell(1, 1).value = "一级板块"
    ws1.cell(1, 2).value = "10月1日"
    ws1.cell(2, 1).value = "纺织服饰"
    ws1.cell(2, 2).value = 1
    ws1.cell(3, 1).value = "机械设备"
    ws1.cell(3, 2).value = 1
    ws1.cell(20, 1).value = "二级板块"
    ws1.cell(20, 2).value = "10月1日"
    ws1.cell(21, 1).value = "服装家纺"
    ws1.cell(21, 2).value = 1
    ws1.cell(22, 1).value = "电池"
    ws1.cell(22, 2).value = 1
    wb.save(out_1001)

    with patch("core.database.AsyncSessionLocal", _fake_session_factory(d1002)):
        assert (await _run(ex, "2026-10-02"))["success"]

    out_1002 = os.path.join(base, "2026-10", "16 10月AI筛选汇总1002.xlsx")
    wb = load_workbook(out_1002)
    ws1 = wb["Sheet1"]
    # 旧格式升级后：所有历史日期的占比列自动补齐
    assert [ws1.cell(1, c).value for c in range(1, 6)] == [
        "一级板块", "10月1日", "10月1日占比", "10月2日", "10月2日占比"]
    stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 4).value)
             for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value}
    assert stats["纺织服饰"] == (1, 4)   # 1001新增1；1002新增3 → 累计4
    assert stats["机械设备"] == (1, 3)   # 1001新增1；1002新增2 → 累计3

    # 用户示例：纺织服饰总量10 → 10月1日 1/10 = 10%（"0%"）；10月2日新增3 → 3/10 = 30%（新增/总量）
    r_textile = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value == "纺织服饰")
    assert abs(ws1.cell(r_textile, 3).value - 0.1) < 1e-9
    assert ws1.cell(r_textile, 3).number_format == "0%"      # 10%
    assert abs(ws1.cell(r_textile, 5).value - 0.3) < 1e-9
    assert ws1.cell(r_textile, 5).number_format == "0%"      # 30%（非累计4/10=40%）
    # 机械设备总量29：10月1日 1/29 ≈ 3.4%（"0.0%"）；10月2日新增2 → 2/29 ≈ 6.9%（"0.0%"）
    r_mach = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value == "机械设备")
    assert abs(ws1.cell(r_mach, 3).value - 1 / 29) < 1e-9
    assert ws1.cell(r_mach, 3).number_format == "0.0%"        # 3.4%
    assert abs(ws1.cell(r_mach, 5).value - 2 / 29) < 1e-9
    assert ws1.cell(r_mach, 5).number_format == "0.0%"        # 6.9%

    # 二级板块表：服装家纺总量10、电池总量29，占比规则一致（分母为2级板块总量）
    t2_header = next(r for r in range(2, ws1.max_row + 1) if ws1.cell(r, 1).value == "二级板块")
    t2_stats = {ws1.cell(r, 1).value: (ws1.cell(r, 2).value, ws1.cell(r, 4).value)
                for r in range(t2_header + 1, t2_header + 3)}
    assert t2_stats["服装家纺"] == (1, 4)   # 1001新增1；1002新增3
    assert t2_stats["电池"] == (1, 3)      # 1001新增1；1002新增2
    r_cloth = next(r for r in range(t2_header + 1, t2_header + 3) if ws1.cell(r, 1).value == "服装家纺")
    assert abs(ws1.cell(r_cloth, 3).value - 0.1) < 1e-9       # 1/10
    assert abs(ws1.cell(r_cloth, 5).value - 0.3) < 1e-9       # 3/10
    r_battery = next(r for r in range(t2_header + 1, t2_header + 3) if ws1.cell(r, 1).value == "电池")
    assert abs(ws1.cell(r_battery, 3).value - 1 / 29) < 1e-9
    assert abs(ws1.cell(r_battery, 5).value - 2 / 29) < 1e-9


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
