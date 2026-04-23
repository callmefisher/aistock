import os
import tempfile
import shutil
import pytest
import pandas as pd
from openpyxl import load_workbook
from unittest.mock import patch

from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def tmp_base():
    d = tempfile.mkdtemp()
    # 准备好涨幅排名需要的目录结构
    os.makedirs(os.path.join(d, "涨幅排名", "2026-04-22"), exist_ok=True)
    os.makedirs(os.path.join(d, "涨幅排名", "2026-04-22", "public"), exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _build_input_df(include_ytd_mtd: bool = True, n_rows: int = 6):
    """构造 ranking_sort 的 input_data（merge_excel 的输出）。
    列 0=板块名称, 列 1=今日涨跌幅(多行), 之后随意列，含"本年初"/"本月初"多行列名。"""
    cols = {
        "板块名称": [f"板块{i+1}" for i in range(n_rows)],
        "成份区间涨跌幅(算术平均)\n[起始交易日期] 2026-04-22\n[终止交易日期] 2026-04-22": [
            5.0, 3.0, 1.0, -1.0, -3.0, -5.0
        ][:n_rows],
    }
    if include_ytd_mtd:
        cols["成份区间涨跌幅(算术平均)\n[起始交易日期] 本年初\n[终止交易日期] 2026-04-22"] = [
            39.59, 27.0, -3.09, 32.0, "--", ""
        ][:n_rows]
        cols["成份区间涨跌幅(算术平均)\n[起始交易日期] 本月初\n[终止交易日期] 2026-04-22"] = [
            10.0, 20.0, 5.0, 15.0, 25.0, None
        ][:n_rows]
    return pd.DataFrame(cols)


@pytest.mark.asyncio
async def test_extended_layout_basic(tmp_base):
    """启用扩展布局：列顺序 + YTD/MTD 排名 + 文件结构"""
    exe = WorkflowExecutor(base_dir=tmp_base, workflow_type="涨幅排名")
    df = _build_input_df(include_ytd_mtd=True, n_rows=6)

    with patch.object(exe.resolver, "find_previous_public_file", return_value=(None, None)):
        res = await exe._ranking_sort(
            {"date_str": "2026-04-22"}, df, "2026-04-22"
        )

    assert res["success"] is True
    cols = res["columns"]
    # 顺序：板块 | 年初 | B排名 | 月初 | D排名 | 今日 | 次数 | 日期列
    assert cols[0] == "板块名称"
    assert cols[1] == "年初涨跌幅"
    assert cols[2] == "B列的数值升序排序结果"
    assert cols[3] == "月初涨跌幅"
    assert cols[4] == "D列的数值升序排序结果"
    assert cols[5] == "今日涨跌幅"
    assert cols[6] == "迄今为止排进前5(次数)"
    assert cols[7] == "4月22日"

    # 打开文件验证排名数字正确
    wb = load_workbook(res["file_path"], data_only=True)
    ws = wb.active
    # 读出所有行数据（row1 表头）
    data_rows = list(ws.iter_rows(min_row=2, values_only=True))
    # 第二列=年初值, 第三列=年初排名
    # 原值 [39.59, 27, -3.09, 32, "--", ""] → 降序排名 39.59(1) 32(2) 27(3) -3.09(4) + 2 个 invalid (5, 6)
    # 但注意 rows 按今日涨跌幅降序排过 (5,3,1,-1,-3,-5)，板块1-6 行顺序不变
    ytd_values = [r[1] for r in data_rows]
    ytd_ranks = [r[2] for r in data_rows]

    # 板块1 年初=39.59 → rank=1; 板块2 年初=27 → rank=3; 板块3 年初=-3.09 → rank=4;
    # 板块4 年初=32 → rank=2; 板块5 年初="--" → rank=5; 板块6 年初="" → rank=6
    # 今日排序后顺序：5,3,1,-1,-3,-5 对应板块1,2,3,4,5,6
    assert ytd_ranks[0] == 1  # 板块1
    assert ytd_ranks[1] == 3  # 板块2
    assert ytd_ranks[2] == 4  # 板块3
    assert ytd_ranks[3] == 2  # 板块4
    assert ytd_ranks[4] == 5  # 板块5
    assert ytd_ranks[5] == 6  # 板块6


@pytest.mark.asyncio
async def test_legacy_layout_when_no_ytd_mtd(tmp_base):
    """没有本年初/本月初列：走老逻辑，保持原输出格式"""
    exe = WorkflowExecutor(base_dir=tmp_base, workflow_type="涨幅排名")
    df = _build_input_df(include_ytd_mtd=False, n_rows=3)

    with patch.object(exe.resolver, "find_previous_public_file", return_value=(None, None)):
        res = await exe._ranking_sort(
            {"date_str": "2026-04-22"}, df, "2026-04-22"
        )

    assert res["success"] is True
    cols = res["columns"]
    # 老布局：板块 | 今日 | 次数 | 日期
    assert cols[0] == "板块名称"
    assert cols[1] == "今日涨跌幅"
    assert cols[2] == "迄今为止排进前5(次数)"
    assert cols[3] == "4月22日"
    # 没有年初/月初
    assert "年初涨跌幅" not in cols
    assert "月初涨跌幅" not in cols


@pytest.mark.asyncio
async def test_extended_layout_only_ytd_falls_back_to_legacy(tmp_base):
    """只有年初没有月初：回退老逻辑"""
    exe = WorkflowExecutor(base_dir=tmp_base, workflow_type="涨幅排名")
    df = _build_input_df(include_ytd_mtd=False, n_rows=3)
    df["成份区间涨跌幅(算术平均)\n[起始交易日期] 本年初"] = [1.0, 2.0, 3.0]

    with patch.object(exe.resolver, "find_previous_public_file", return_value=(None, None)):
        res = await exe._ranking_sort(
            {"date_str": "2026-04-22"}, df, "2026-04-22"
        )

    assert res["success"] is True
    assert "年初涨跌幅" not in res["columns"]
