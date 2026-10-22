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
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from openpyxl import Workbook, load_workbook

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


def test_resolve_backtrack_picks_largest_mmdd_not_mtime(tmp_path):
    """用户实测场景回归：回溯目录同时存在 1015 老文件（用户后上传、mtime 更新）
    与 1016 工作流文件（先生成、mtime 较旧）→ 必须拷贝文件名日期最大的 1016，
    不得按 mtime 误选 1015。13/14/18 三表共用该解析逻辑。"""
    import time
    base = str(tmp_path)
    # 10-16 回溯目录：先写 1016（老mtime），后写 1015（新mtime，模拟用户上传）
    d16 = os.path.join(base, "2026-10-16", "输出")
    os.makedirs(d16)
    f16 = os.path.join(d16, "13 占20日线无振幅1016.xlsx")
    pd.DataFrame({"日期": ["10月16日"], "股票数量": [100]}).to_excel(f16, index=False)
    old_ts = time.time() - 3600
    os.utime(f16, (old_ts, old_ts))
    f15 = os.path.join(d16, "13 占20日线无振幅 1015.xlsx")
    pd.DataFrame({"日期": ["10月15日"], "股票数量": [50]}).to_excel(f15, index=False)
    # f15 mtime = now > f16 mtime：若按 mtime 排序会错误选中 1015

    # 数据日期 10-17，当日目录无文件 → 回溯 10-16
    path, mode = resolve_daily_output_file(base, "2026-10-17", "输出", "13 占20日线无振幅1017.xlsx")
    assert mode == "copy"
    assert os.path.basename(path) == "13 占20日线无振幅1017.xlsx"
    # 拷贝内容来自 1016（文件名日期最大），而非 mtime 更新的 1015
    wb = load_workbook(path)
    ws = wb.worksheets[0]
    assert ws.cell(2, 1).value == "10月16日"
    assert ws.cell(2, 2).value == 100
    # 两个源文件均原样保留
    assert os.path.exists(f15) and os.path.exists(f16)


def test_resolve_daily_dir_multiple_files_picks_largest_mmdd(tmp_path):
    """数据日期目录内有多个其他名文件 → 同样按文件名 MMDD 最大选源"""
    base = str(tmp_path)
    d = os.path.join(base, "2026-10-17", "输出")
    os.makedirs(d)
    pd.DataFrame({"x": ["old"]}).to_excel(os.path.join(d, "14 总市值大于1000亿 本周最高价格大于上周最高价格1015.xlsx"), index=False)
    pd.DataFrame({"x": ["new"]}).to_excel(os.path.join(d, "14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx"), index=False)
    path, mode = resolve_daily_output_file(base, "2026-10-17", "输出",
                                           "14 总市值大于1000亿 本周最高价格大于上周最高价格1017.xlsx")
    assert mode == "copy"
    wb = load_workbook(path)
    assert wb.worksheets[0].cell(2, 1).value == "new", "应选文件名日期最大的 1016"


def test_filename_mmdd_key_extraction():
    """MMDD 键提取：13/14/18 号表命名格式 + 无日期名兜底"""
    from services.weekly_common import _filename_mmdd_key
    assert _filename_mmdd_key("/x/13 占20日线无振幅1016.xlsx") == 1016
    assert _filename_mmdd_key("/x/13 占20日线无振幅 1015.xlsx") == 1015
    assert _filename_mmdd_key("/x/14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx") == 1016
    assert _filename_mmdd_key("/x/18 全部A股总市值大于800亿1015.xlsx") == 1015
    assert _filename_mmdd_key("/x/20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx") == -1
    assert _filename_mmdd_key("/x/无数字.xlsx") == -1


def test_resolve_output_file_reuse_same_name(tmp_path):
    """数据日期目录已有同名可读文件 → 直接复用（同名强制覆盖更新语义）"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    pd.DataFrame({"x": [1]}).to_excel(os.path.join(d, "a1015.xlsx"), index=False)
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "reuse"
    assert path == os.path.join(d, "a1015.xlsx")


def test_resolve_output_file_reuse_other_name(tmp_path):
    """数据日期目录只有其他名可读文件 → 拷贝重命名为默认名（新副本编辑），老文件不动"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    src = os.path.join(d, "old1014.xlsx")
    pd.DataFrame({"x": [1]}).to_excel(src, index=False)
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "copy"
    assert os.path.basename(path) == "a1015.xlsx"
    assert os.path.exists(src), "老文件不应被删除/修改"
    assert os.path.exists(path), "新副本已生成"


def test_resolve_output_file_corrupt_same_name_skipped(tmp_path):
    """数据日期目录默认名文件损坏（0字节）→ 跳过不阻断；无其他候选 → 全新生成"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    open(os.path.join(d, "a1015.xlsx"), "w").close()  # 0字节损坏文件
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "new"
    # 损坏文件保留在原地（由下次上传清理），不抛异常
    assert os.path.exists(os.path.join(d, "a1015.xlsx"))


def test_resolve_output_file_corrupt_falls_back_to_other_readable(tmp_path):
    """默认名损坏 + 目录内其他可读文件 → 拷贝其他文件为默认名（不因坏文件中断）"""
    d = os.path.join(str(tmp_path), "2026-10-15", "输出")
    os.makedirs(d)
    open(os.path.join(d, "a1015.xlsx"), "w").close()
    pd.DataFrame({"x": [2]}).to_excel(os.path.join(d, "backup.xlsx"), index=False)
    path, mode = resolve_daily_output_file(str(tmp_path), "2026-10-15", "输出", "a1015.xlsx")
    assert mode == "copy"
    wb = load_workbook(path)
    assert wb.worksheets[0].cell(2, 1).value == 2


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
    # 输出只保留2个sheet：筛选结果 + 当前数据日期（历史 MMDD sheet 1015 删除）
    assert wb.sheetnames == ["筛选结果", "1016"]
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
async def test_all_a_800_append_tight_after_last_valid_row(tmp_path):
    """新增行紧贴最后一个有效数据行追加：表格下方有“数据来源”杂散行时不跳行不覆盖"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "全部A股800亿", _A800_ROWS[:2])
    assert (await _run18(base, "2026-10-15"))["success"]

    out15 = _out18(base, "2026-10-15")
    wb = load_workbook(out15)
    ws = wb.worksheets[0]
    # 模拟表格下方杂散内容（隔1个空行）
    ws.cell(row=4, column=1).value = "数据来源：同花顺iFinD"
    wb.save(out15)
    wb.close()

    # 数据日期目录无文件 → 回溯拷贝 10-15（含杂散行），新增 600519
    _write_public_file(base, "2026-10-16", "全部A股800亿", _A800_ROWS[:3])
    result = await _run18(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-16"))
    ws = wb.worksheets[0]
    # 新增行紧贴最后有效行(行2)的下一行(行3)，杂散行下移到行5、内容不被覆盖
    assert ws.cell(2, 1).value == "000001.SZ"
    assert ws.cell(3, 1).value == "600519.SH"
    assert ws.cell(5, 1).value == "数据来源：同花顺iFinD"


@pytest.mark.asyncio
async def test_all_a_800_sector_pure_numeric_matches_suffixed_map(tmp_path):
    """板块为空根因回归：全部A股代码带 .SZ 后缀、源文件代码纯数字 → 双键匹配命中"""
    base = str(tmp_path)
    rows = [("证券代码", "证券简称", "总市值"), ("000001", "平安", "900")]
    _write_public_file(base, "2026-10-15", "全部A股800亿", rows)
    _write_all_a_industry_file(base, [("000001.SZ", "银行")])  # 映射键带后缀

    result = await _run18(base, "2026-10-15")
    assert result["success"], result.get("error")
    wb = load_workbook(_out18(base, "2026-10-15"))
    ws = wb.worksheets[0]
    assert ws.cell(2, 4).value == "银行", "纯数字代码应命中带后缀的全部A股板块映射"
    assert "板块命中 1" in result["message"]


@pytest.mark.asyncio
async def test_all_a_800_39day_rematches_existing_rows(tmp_path):
    """39日新高整列重匹配：每次执行对全部已有行按当日39日新高重新匹配——
    命中填代码、未命中清空；历史日期列不修改"""
    base = str(tmp_path)
    # Day1: 000001 命中
    _write_public_file(base, "2026-10-15", "全部A股800亿", _A800_ROWS[:3])
    _write_39day_file(base, "2026-10-15", ["000001.SZ"])
    assert (await _run18(base, "2026-10-15"))["success"]

    # Day2: 无新增（同数据源），当日39日新高变为 600519
    _write_public_file(base, "2026-10-16", "全部A股800亿", _A800_ROWS[:3])
    _write_39day_file(base, "2026-10-16", ["600519.SH"])
    result = await _run18(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-16"))
    ws = wb.worksheets[0]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    col16 = header.index("10/16\n39日新高") + 1
    col15 = header.index("10/15\n39日新高") + 1
    row_map = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
    # 000001：昨日命中、今日未命中 → 当日列清空；历史列(10/15)保留
    assert ws.cell(row_map["000001.SZ"], col16).value in (None, "")
    assert ws.cell(row_map["000001.SZ"], col15).value == "000001.SZ"
    # 600519：今日命中 → 当日列填代码
    assert ws.cell(row_map["600519.SH"], col16).value == "600519.SH"
    # message 报告整列重匹配结果
    assert "39日新高整列重匹配 2 行、命中 1" in result["message"]


@pytest.mark.asyncio
async def test_mv1000_output_keeps_only_two_sheets(tmp_path):
    """14号表输出只保留2个sheet：第1个「筛选结果」+ 第2个当前数据日期；
    拷贝继承的历史日期sheet（如1014/1015）全部删除；并透传20号表下载路径"""
    base = str(tmp_path)
    # Day1: 正常生成（含 1015 sheet）
    _write_public_file(base, "2026-10-15", "本周总市值千亿新高", _MV_ROWS)
    assert (await _run14(base, "2026-10-15"))["success"]

    # 手工给 10-15 文件添加更早期残留 sheet 1014
    out15 = _out14(base, "2026-10-15")
    wb = load_workbook(out15)
    wb.create_sheet("1014")
    wb.save(out15)
    wb.close()

    # Day2: 拷贝继承 10-15（此时含 筛选结果/1015/1014 三个sheet）
    _write_public_file(base, "2026-10-16", "本周总市值千亿新高", _MV_ROWS)
    result = await _run14(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out14(base, "2026-10-16"))
    assert wb.sheetnames == ["筛选结果", "1016"], f"应只保留2个sheet: {wb.sheetnames}"
    # 20号表相对 {date} 的下载路径透传（前端批量下载用）
    assert result["_extra_outputs"]["output_filename_table20"] == (
        "20号表本周总市值千亿新高A列/20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx"
    )


@pytest.mark.asyncio
async def test_ma13_int_serial_date_rows_appended_not_overwritten(tmp_path):
    """用户实测bug回归：上传的老13号表日期列是 int 序列值（如46184，General格式）——
    修复前 _cell_to_date 对 int 返回 None，导致新行写入第2行覆盖历史数据、图表只画单点。
    修复后：历史行不覆盖、新行追加在最后日期行后、int行刷日期格式、图表覆盖全部数据行。"""
    base = str(tmp_path)
    # 模拟快捷上传：老文件（带空格1015名）已在 10-16 输出目录
    out_dir = os.path.join(base, "2026-10-16", "本周20日收盘价新高输出")
    os.makedirs(out_dir, exist_ok=True)
    old_path = os.path.join(out_dir, "13 占20日线无振幅 1015.xlsx")
    wb0 = Workbook()
    ws0 = wb0.active
    ws0.title = "趋势图"
    ws0.append(["日期", "股票数量"])
    for serial, cnt in [(46184, 421), (46185, 626), (46188, 695)]:  # int序列值 + General格式
        ws0.append([serial, cnt])
    wb0.save(old_path)
    wb0.close()

    # 10-16 公共数据源
    _write_public_file(base, "2026-10-16", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 4)

    result = await _run13(base, "2026-10-16")
    assert result["success"], result.get("error")

    new_path = _out13(base, "2026-10-16")
    assert os.path.basename(new_path) == "13 占20日线无振幅1016.xlsx"
    wb = load_workbook(new_path)
    ws = wb["趋势图"]

    # 历史行不被覆盖：r=2 的 int 序列值 46184 刷日期格式后保存，
    # openpyxl 按日期语义读回 datetime(2026,6,11)（值未变，显示 6月11日）
    assert ws.cell(2, 1).value == datetime(2026, 6, 11)
    assert ws.cell(2, 2).value == 421
    # 新行追加在最后日期行(r=4)之后 r=5，为 datetime 10/16
    assert ws.cell(5, 1).value == datetime(2026, 10, 16)
    assert ws.cell(5, 2).value == 4
    # 日期显示格式统一「X月X日」（点击可见年月日）
    assert ws.cell(2, 1).number_format == 'm"月"d"日"'

    # 图表覆盖全部数据行（4个数据点），不再是单点
    chart = ws._charts[0]
    assert chart.series[0].val.numRef.f == "'趋势图'!$B$2:$B$5"
    assert chart.series[0].cat.numRef.f == "'趋势图'!$A$2:$A$5"

    # 幂等：同日重复执行只刷新数量，不新增行
    _write_public_file(base, "2026-10-16", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 7)
    result2 = await _run13(base, "2026-10-16")
    assert result2["success"]
    wb2 = load_workbook(new_path)
    ws2 = wb2["趋势图"]
    assert ws2.max_row == 5, "同日重复执行不应新增行"
    assert ws2.cell(5, 2).value == 7


def test_ma13_cell_to_date_int_serial():
    """int 序列值 → 日期；范围外数字（如股票数量列误传）不误判"""
    from services.weekly_ma20_close_high import _cell_to_date
    assert _cell_to_date(46184) == date(2026, 6, 11)
    assert _cell_to_date(46216) == date(2026, 7, 13)
    assert _cell_to_date(3.0) is None      # 1900年 → 范围外
    assert _cell_to_date(99999999) is None  # 远超2100年
    assert _cell_to_date("10月15日") == date(datetime.now().year, 10, 15)
    assert _cell_to_date(None) is None


@pytest.mark.asyncio
async def test_ma13_garbage_a_column_never_overwrites_row2(tmp_path):
    """防御：A列全是无法解析的杂散内容（非日期非序列值）时，从 max_row+1 追加，
    绝不覆盖第2行既有内容"""
    base = str(tmp_path)
    out_dir = os.path.join(base, "2026-10-16", "本周20日收盘价新高输出")
    os.makedirs(out_dir, exist_ok=True)
    old_path = os.path.join(out_dir, "13 占20日线无振幅1016.xlsx")
    wb0 = Workbook()
    ws0 = wb0.active
    ws0.title = "Sheet1"
    ws0.append(["日期", "股票数量"])
    ws0.append(["随便的内容", 100])
    ws0.append(["备注", 200])
    wb0.save(old_path)
    wb0.close()

    _write_public_file(base, "2026-10-16", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 2)
    result = await _run13(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out13(base, "2026-10-16"))
    ws = wb["Sheet1"]
    # 原有内容不动，新行追加在最后
    assert ws.cell(2, 1).value == "随便的内容"
    assert ws.cell(2, 2).value == 100
    assert ws.cell(4, 1).value == datetime(2026, 10, 16)
    assert ws.cell(4, 2).value == 2


@pytest.mark.asyncio
async def test_mv1000_mmdd_sheet_excludes_invalid_rows(tmp_path):
    """14号表 MMDD sheet 排除「数据来源」/undefined/null/全空 行；
    「筛选结果」sheet 不修改（原样保留，含杂散行）；20号表联动输出干净。"""
    base = str(tmp_path)
    rows = [
        ("股票代码", "证券简称", "总市值"),
        ("600519.SH", "茅台", "2100"),
        ("数据来源：同花顺iFinD", None, None),   # 表尾说明行
        ("undefined", "x", "1"),                  # undefined 脏数据
        ("000001.SZ", "平安", "900"),
        (None, None, None),                       # 全空行
        (None, "null", None),                     # null 脏数据
    ]
    _write_public_file(base, "2026-10-16", "本周总市值千亿新高", rows)

    result = await _run14(base, "2026-10-16")
    assert result["success"], result.get("error")

    wb = load_workbook(_out14(base, "2026-10-16"))
    # MMDD sheet：表头 + 2个正常行（降序），无效行全部排除。
    # insert_cols(3) 在B列后插入空白列 → 原第3列(总市值)位于第4列
    ws = wb["1016"]
    values = [[ws.cell(r, c).value for c in (1, 2, 4)] for r in range(1, ws.max_row + 1)]
    assert values == [
        ["股票代码", "证券简称", "总市值"],
        ["600519.SH", "茅台", "2100"],
        ["000001.SZ", "平安", "900"],
    ], "数据来源/undefined/null/全空行应全部排除"
    # B列后空白列（原逻辑保留）
    assert ws.cell(1, 3).value in (None, "")
    assert ws.max_column == 4

    # 筛选结果 sheet：原样保留（不修改，含杂散行）
    ws1 = wb["筛选结果"]
    codes1 = [ws1.cell(r, 1).value for r in range(2, ws1.max_row + 1)]
    assert "数据来源：同花顺iFinD" in codes1, "筛选结果sheet应保持公共文件原貌"

    # 20号表联动：输出也干净（仅正常代码，降序）
    t20 = os.path.join(base, "2026-10-16", "20号表本周总市值千亿新高A列",
                       "20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx")
    wb2 = load_workbook(t20)
    ws2 = wb2["1016"]
    col = [ws2.cell(r, 1).value for r in range(1, ws2.max_row + 1)]
    assert col == ["股票代码", "600519.SH", "000001.SZ"]


@pytest.mark.asyncio
async def test_all_a_800_missing_public(tmp_path):
    result = await _run18(str(tmp_path), "2026-10-15")
    assert not result["success"]
    assert "公共数据源缺失" in result["error"]


@pytest.mark.asyncio
async def test_all_a_800_skips_data_source_rows(tmp_path):
    """B 公共文件表尾“数据来源：xxx”行 → 不追加、不参与比对（异常行排除）"""
    base = str(tmp_path)
    rows = [
        ("证券代码", "证券简称", "总市值"),
        ("000001.SZ", "平安", "900"),
        ("数据来源：同花顺iFinD", "", ""),   # 表尾说明行
    ]
    _write_public_file(base, "2026-10-15", "全部A股800亿", rows)

    result = await _run18(base, "2026-10-15")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-15"))
    ws = wb.worksheets[0]
    codes = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
    assert codes == ["000001.SZ"], "数据来源行不应被追加"
    # message 中报告排除的非代码行数
    assert "排除非代码行 1" in result["message"]


@pytest.mark.asyncio
async def test_all_a_800_header_wrap_text_two_lines(tmp_path):
    """「M/D\\n39日新高」表头打开即双行显示：wrap_text + 行高（无需点击单元格）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-15", "全部A股800亿", _A800_ROWS[:2])
    _write_all_a_industry_file(base, [("000001.SZ", "银行")])
    _write_39day_file(base, "2026-10-15", ["000001.SZ"])

    result = await _run18(base, "2026-10-15")
    assert result["success"], result.get("error")

    wb = load_workbook(_out18(base, "2026-10-15"))
    ws = wb.worksheets[0]
    header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    col39 = header.index("10/15\n39日新高") + 1
    cell = ws.cell(1, col39)
    assert cell.alignment.wrap_text is True, "表头需自动换行才能默认双行显示"
    assert ws.row_dimensions[1].height == 30


@pytest.mark.asyncio
async def test_all_a_800_multiline_code_header(tmp_path):
    """B 代码列表头为多行文本（如“证券代码\\n[单位]只”）→ 包含匹配仍能定位代码列"""
    base = str(tmp_path)
    # 用 openpyxl 直接构造多行表头（pandas 不方便写含换行的列名读取场景）
    d = os.path.join(base, "2026-10-15", "全部A股800亿")
    os.makedirs(d, exist_ok=True)
    wb0 = Workbook()
    ws0 = wb0.active
    ws0.append(["证券代码\n[单位]只", "证券简称", "总市值"])
    ws0.append(["000001.SZ", "平安", "900"])
    ws0.append(["600519.SH", "茅台", "2100"])
    wb0.save(os.path.join(d, "800亿.xlsx"))
    wb0.close()

    result = await _run18(base, "2026-10-15")
    assert result["success"], result.get("error")
    wb = load_workbook(_out18(base, "2026-10-15"))
    ws = wb.worksheets[0]
    codes = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
    assert sorted(codes) == ["000001.SZ", "600519.SH"]


@pytest.mark.asyncio
async def test_ma20_append_after_last_date_row_not_max_row(tmp_path):
    """13号表：表格下方有杂散内容/空行时，新行必须追加到最后一个日期行的下一行（非最后一行）"""
    base = str(tmp_path)
    _write_public_file(base, "2026-10-14", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 2)
    assert (await _run13(base, "2026-10-14"))["success"]

    out14 = _out13(base, "2026-10-14")
    wb = load_workbook(out14)
    ws = wb["Sheet1"]
    # 模拟表格下方杂散内容（如备注行）
    ws.cell(row=5, column=1).value = "备注：手工添加"
    wb.save(out14)
    wb.close()

    _write_public_file(base, "2026-10-15", "本周20日收盘价新高",
                       [("证券代码",)] + [("000001.SZ",)] * 4)
    # 数据日期目录为空 → 回溯拷贝 10-14 文件（含杂散行）
    result = await _run13(base, "2026-10-15")
    assert result["success"], result.get("error")

    wb = load_workbook(_out13(base, "2026-10-15"))
    ws = wb["Sheet1"]
    # 新行紧贴最后日期行（第2行）的下一行 = 第3行，而不是杂散行之后
    assert ws.cell(2, 1).value == datetime(2026, 10, 14)
    assert ws.cell(3, 1).value == datetime(2026, 10, 15)
    assert ws.cell(3, 2).value == 4
    assert ws.cell(5, 1).value == "备注：手工添加"  # 杂散内容不受影响
    # 图表数据范围截止最后日期行（第3行），不包含杂散行
    # （titles_from_data=True：首行作系列名，系列值从第2行起；引用带 sheet 前缀）
    chart = ws._charts[0]
    assert chart.series[0].val.numRef.f == "'Sheet1'!$B$2:$B$3"
    assert chart.series[0].cat.numRef.f == "'Sheet1'!$A$2:$A$3"


def test_export_table20_reads_from_generated_mv1000_file(tmp_path):
    """20号表数据源 = 已生成的14号表文件 MMDD sheet 的第一列（而非公共文件）：
    构造14号表A列内容与公共文件不同，断言20号表跟随14号表文件内容且降序、仅此一列；
    同时验证「数据来源」/undefined/null 等无效行被排除。"""
    from services.weekly_mv1000_high import _export_table20

    base = str(tmp_path)
    out_dir = os.path.join(base, "2026-10-16", "本周总市值千亿新高输出")
    os.makedirs(out_dir, exist_ok=True)
    mv1000_path = os.path.join(out_dir, "14 总市值大于1000亿 本周最高价格大于上周最高价格1016.xlsx")

    # 构造14号表：MMDD sheet A列故意乱序、含手工修改值（与公共文件无关），
    # 并混入无效行：数据来源说明行、undefined、null、空行
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "筛选结果"
    ws1.append(["随便什么"])
    ws2 = wb.create_sheet("1016")
    for v in ["股票代码", "000003.SZ", "数据来源：同花顺iFinD", "000001.SZ",
              "undefined", "600519.SH", "null", None, ""]:
        ws2.append([v])
    wb.save(mv1000_path)
    wb.close()

    t20 = _export_table20(base, "2026-10-16", mv1000_path, "1016")
    wb2 = load_workbook(t20)
    assert wb2.sheetnames == ["1016"]
    ws = wb2["1016"]
    assert ws.max_column == 1, "20号表只应有一列"
    assert [ws.cell(r, 1).value for r in range(1, ws.max_row + 1)] == [
        "股票代码", "600519.SH", "000003.SZ", "000001.SZ",
    ], "应为14号表A列内容且按代码降序，且排除数据来源/undefined/null/空行"
    # 样式与模板「21ok.xlsx」一致：A列整列统一格式（列级样式，覆盖空行区域）
    # 默认行高16.8、默认列宽9；数值格式 0.00_);[Red]\(0.00\)；
    # 宋体11、charset=134（GB2312）、颜色主题色1、字体方案minor、列宽18.75
    assert ws.sheet_format.defaultRowHeight == 16.8
    assert ws.sheet_format.defaultColWidth == 9
    col_dim = ws.column_dimensions["A"]
    assert col_dim.width == 18.75
    assert col_dim.number_format == "0.00_);[Red]\\(0.00\\)"
    assert col_dim.font.name == "宋体" and col_dim.font.sz == 11
    assert col_dim.font.charset == 134, "整列字体字符集应为134（GB2312）"
    # 已有单元格（含表头）显式同格式，优先生效
    for r in range(1, ws.max_row + 1):
        cell = ws.cell(r, 1)
        assert cell.number_format == "0.00_);[Red]\\(0.00\\)"
        f = cell.font
        assert f.name == "宋体" and f.sz == 11 and f.charset == 134
        assert f.color is not None and f.color.theme == 1, "字体颜色应为主题色1"
        assert f.scheme == "minor", "字体方案应为minor"

    # XML级断言：实际单元格样式引用链与模板 21ok.xlsx 完全一致
    # （数据单元格 s="1" → cellXfs[1] numFmtId=176 fontId=0 → fonts[0]=宋体）
    import zipfile as _zf
    import re as _re
    with _zf.ZipFile(t20) as z:
        # OPC 包规范断言（Choice 兼容）：[Content_Types].xml 必须是 zip 第一个条目
        # （openpyxl 原生排在最后）；所有 xml/rels 部件必须带 <?xml?> 声明
        # （openpyxl 3.1 除 theme 外均不写声明）——严格解析器（Choice 导入器）依赖两者，
        # Excel/WPS 手动重存能修复导入，正是因为重存自动补齐了这两点。
        _names = z.namelist()
        assert _names[0] == "[Content_Types].xml", \
            "[Content_Types].xml 应为 zip 第一个条目（OPC 规范）"
        for _n in _names:
            if _n.endswith((".xml", ".rels")):
                assert z.read(_n).lstrip().startswith(b"<?xml"), \
                    f"部件 {_n} 应带 <?xml?> 声明"
        # 关系目标规范化断言：worksheet 关系必须用相对 Target（如 worksheets/sheet1.xml）。
        # openpyxl 原生写包绝对路径 Target="/xl/worksheets/sheet1.xml"（OPC 允许但非主流），
        # Excel/WPS 均写相对路径；Choice 等导入器按「基目录+Target」拼接解析，绝对形式直接
        # 解析失败——这正是手动重存后可导入的另一个规范化点。
        _rels_raw = z.read("xl/_rels/workbook.xml.rels").decode()
        assert 'Target="/xl/' not in _rels_raw, \
            "workbook 关系不应使用包绝对路径 Target=\"/xl/...\"（openpyxl 怪癖）"
        assert 'Target="worksheets/sheet1.xml"' in _rels_raw, \
            "worksheet 关系应为相对 Target"
        _wb_raw = z.read("xl/workbook.xml").decode()
        assert "<workbookProtection/>" not in _wb_raw, "不应有空 workbookProtection（WPS 重存会丢弃）"
        assert "<definedNames/>" not in _wb_raw, "不应有空 definedNames"
        st = z.read("xl/styles.xml").decode()
        ws_xml = z.read([n for n in z.namelist() if n.startswith("xl/worksheets/sheet")][0]).decode()
        ct = z.read("[Content_Types].xml").decode()
        rels = z.read("xl/_rels/workbook.xml.rels").decode()
        has_sst = "xl/sharedStrings.xml" in z.namelist()
        sst = z.read("xl/sharedStrings.xml").decode() if has_sst else ""
    tpl_path = "/Users/xiayanji/Desktop/21ok.xlsx"
    if os.path.exists(tpl_path):
        # 本机有模板原件时做逐字节比对
        tpl_st = _zf.ZipFile(tpl_path).read("xl/styles.xml").decode()
        assert st == tpl_st, "styles.xml 应与模板逐字节一致"
    fonts0 = _re.findall(r"<font>.*?</font>", _re.search(r"<fonts.*?</fonts>", st, _re.S).group(0))[0]
    assert 'name val="宋体"' in fonts0 and 'charset val="134"' in fonts0
    assert '<color theme="1"/>' in fonts0 and '<scheme val="minor"/>' in fonts0
    xf1 = _re.findall(r"<xf [^>]*/>", _re.search(r"<cellXfs.*?</cellXfs>", st, _re.S).group(0))[1]
    assert 'fontId="0"' in xf1 and 'numFmtId="176"' in xf1
    m = _re.search(r'<c r="A2" s="(\d+)"', ws_xml)
    assert m and m.group(1) == "1", "数据单元格应引用样式索引 s=1"
    assert 'numFmtId="176"' in _re.search(r"<numFmts.*?</numFmts>", st, _re.S).group(0)

    # 标准化保存断言：字符串单元格为 Excel 原生 t="s" + sharedStrings 形态
    # （openpyxl 默认只写 inlineStr 且无 sharedStrings.xml，Choice 等第三方导入器不识别；
    # Excel 手动重存后能导入正是因为重存完成了该规范化）
    assert has_sst, "应生成 xl/sharedStrings.xml"
    assert 't="inlineStr"' not in ws_xml, "不应残留 inlineStr 形态单元格"
    assert '<c r="A2" s="1" t="s"><v>' in ws_xml, "数据单元格应为 t=\"s\" + <v>索引</v>"
    assert "sharedStrings+xml" in ct, "[Content_Types].xml 应注册 sharedStrings 部件"
    assert "relationships/sharedStrings" in rels, "workbook 关系应包含 sharedStrings"
    assert "股票代码" in sst and "600519.SH" in sst, "共享字符串表应含表头与代码"
    # openpyxl 回读（经 sharedStrings 解析）内容不变
    wb3 = load_workbook(t20)
    ws3 = wb3["1016"]
    assert [ws3.cell(r, 1).value for r in range(1, ws3.max_row + 1)] == [
        "股票代码", "600519.SH", "000003.SZ", "000001.SZ"]


@pytest.mark.asyncio
async def test_mv1000_corrupt_file_in_date_dir_falls_back(tmp_path):
    """用户报错场景：数据日期目录只有损坏的 14号表文件 → 跳过，回溯拷贝可读文件，
    14号表与20号表照常输出，步骤不失败"""
    base = str(tmp_path)
    # 10-15 有可读的 14号表
    _write_public_file(base, "2026-10-15", "本周总市值千亿新高", _MV_ROWS)
    assert (await _run14(base, "2026-10-15"))["success"]

    # 10-16：公共文件 + 输出目录放一个损坏的 1015 名文件（模拟用户现场）
    _write_public_file(base, "2026-10-16", "本周总市值千亿新高", _MV_ROWS)
    out_dir = os.path.join(base, "2026-10-16", "本周总市值千亿新高输出")
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "14 总市值大于1000亿 本周最高价格大于上周最高价格1015.xlsx"), "w").close()

    result = await _run14(base, "2026-10-16")
    assert result["success"], result.get("error")

    # 新文件用当前数据日期命名（1016），内容来自 10-15 拷贝
    out16 = _out14(base, "2026-10-16")
    assert os.path.exists(out16)
    wb = load_workbook(out16)
    assert "筛选结果" in wb.sheetnames and "1016" in wb.sheetnames
    # 20号表照常输出
    t20 = os.path.join(base, "2026-10-16", "20号表本周总市值千亿新高A列",
                       "20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx")
    assert os.path.exists(t20)
    # 损坏文件保留原地（由下次上传清理），未阻断执行
    assert os.path.exists(os.path.join(out_dir, "14 总市值大于1000亿 本周最高价格大于上周最高价格1015.xlsx"))


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
