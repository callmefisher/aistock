import os
import tempfile
import shutil
import pytest
from unittest.mock import AsyncMock, patch
from openpyxl import Workbook

from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def tmp_base():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _seed_high_price(base: str, date_str: str, n: int):
    d = os.path.join(base, date_str, "百日新高")
    os.makedirs(d, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.append(["证券代码", "名称"])
    for i in range(n):
        ws.append([f"{600000+i:06d}.SH", f"name{i}"])
    wb.save(os.path.join(d, "hp.xlsx"))


@pytest.mark.asyncio
async def test_export_high_price_trend_基本(tmp_base):
    date_str = "2026-04-22"
    _seed_high_price(tmp_base, date_str, 5)

    exe = WorkflowExecutor(base_dir=tmp_base, workflow_type="百日新高总趋势")

    mock_records = [
        {"workflow_type": "百日新高总趋势", "date_str": "2026-04-20",
         "count": 100, "total": 0, "ratio": 0},
        {"workflow_type": "百日新高总趋势", "date_str": "2026-04-21",
         "count": 110, "total": 0, "ratio": 0},
    ]

    with patch("services.trend_service.save_trend_data", new=AsyncMock(return_value=True)) as m_save, \
         patch("services.trend_service.get_trend_data",
               new=AsyncMock(return_value=mock_records)) as m_get:
        result = await exe._export_high_price_trend(
            {"date_str": date_str, "date_preset": "custom"}, date_str
        )

    assert result["success"] is True
    assert result["today_count"] == 5
    assert result["file_path"].endswith(f"百日新高总趋势/{date_str}/11百日新高趋势图{date_str}.xlsx")
    assert os.path.exists(result["file_path"])
    m_save.assert_awaited_once()
    m_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_high_price_trend_count0_不入库(tmp_base):
    date_str = "2026-04-22"
    # 故意不 seed
    exe = WorkflowExecutor(base_dir=tmp_base, workflow_type="百日新高总趋势")

    with patch("services.trend_service.save_trend_data", new=AsyncMock(return_value=True)) as m_save, \
         patch("services.trend_service.get_trend_data", new=AsyncMock(return_value=[])) as m_get:
        result = await exe._export_high_price_trend(
            {"date_str": date_str, "date_preset": "custom"}, date_str
        )

    assert result["success"] is True
    assert result["today_count"] == 0
    m_save.assert_not_awaited()
    m_get.assert_awaited_once()
