"""阶段4 - 条件交集中质押类型的"资本运作行为"细分测试。

由于 _condition_intersection 内部依赖 DB（从 workflow_results 解压数据），
这里用 mock AsyncSession 模拟数据库返回，测试仅针对"质押分支的资本运作行为派生"逻辑。
"""
import json
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from services.workflow_executor import WorkflowExecutor


def _compress(records: list[dict]) -> bytes:
    return zlib.compress(json.dumps(records, ensure_ascii=False).encode("utf-8"), 6)


class _FakeSession:
    """Async with 协议 + execute 返回指定 row 列表。"""
    def __init__(self, rows_by_wtype: dict):
        self.rows_by_wtype = rows_by_wtype

    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass

    async def execute(self, query, params):
        wtype = params.get("wtype") or params.get("wtype_cn", "")
        rows = self.rows_by_wtype.get(wtype, [])
        mock_result = MagicMock()
        mock_result.fetchone = MagicMock(return_value=rows[0] if rows else None)
        return mock_result

    async def commit(self): pass


def _patch_session(rows_by_wtype):
    """返回一个 async 上下文管理器工厂。"""
    def factory(*a, **kw):
        return _FakeSession(rows_by_wtype)
    return factory


@pytest.mark.asyncio
async def test_pledge_source_zhongdapan_mapped():
    """来源=中大盘 → 资本运作行为 = 质押中大盘。"""
    pledge_records = [
        {"序号": 1, "证券代码": "000001", "证券简称": "平安银行",
         "最新公告日": "2026-04-14", "百日新高": "Y", "20日均线": "", "国企": "", "一级板块": "银行",
         "来源": "中大盘"},
    ]
    rows = {"质押": [(_compress(pledge_records),)]}
    import tempfile, os
    with tempfile.TemporaryDirectory() as base:
        os.makedirs(os.path.join(base, "条件交集", "2026-04-20"), exist_ok=True)
        ex = WorkflowExecutor(base_dir=base, workflow_type="条件交集")
        with patch("core.database.AsyncSessionLocal", _patch_session(rows)):
            result = await ex._condition_intersection(
                {"type_order": ["质押"], "filter_conditions": [{"column": "百日新高", "enabled": True}]},
                date_str="2026-04-20"
            )
    assert result["success"], result["message"]
    df = result["_df"]
    assert (df["资本运作行为"] == "质押中大盘").all()
    assert "warnings" in result and result["warnings"] == []


@pytest.mark.asyncio
async def test_pledge_source_xiaopan_mapped():
    """来源=小盘 → 资本运作行为 = 质押小盘。"""
    pledge_records = [
        {"序号": 1, "证券代码": "300001", "证券简称": "特锐德",
         "最新公告日": "2026-04-14", "百日新高": "Y", "20日均线": "", "国企": "", "一级板块": "电气",
         "来源": "小盘"},
    ]
    rows = {"质押": [(_compress(pledge_records),)]}
    import tempfile, os
    with tempfile.TemporaryDirectory() as base:
        os.makedirs(os.path.join(base, "条件交集", "2026-04-20"), exist_ok=True)
        ex = WorkflowExecutor(base_dir=base, workflow_type="条件交集")
        with patch("core.database.AsyncSessionLocal", _patch_session(rows)):
            result = await ex._condition_intersection(
                {"type_order": ["质押"], "filter_conditions": [{"column": "百日新高", "enabled": True}]},
                date_str="2026-04-20"
            )
    df = result["_df"]
    assert (df["资本运作行为"] == "质押小盘").all()


@pytest.mark.asyncio
async def test_pledge_source_missing_falls_back_to_xiaopan_with_warning():
    """来源 为空或非法 → 兜底"质押小盘" + warnings 冒泡。"""
    pledge_records = [
        {"序号": 1, "证券代码": "000001", "证券简称": "平安",
         "最新公告日": "2026-04-14", "百日新高": "Y", "20日均线": "", "国企": "", "一级板块": "银行",
         "来源": ""},
        {"序号": 2, "证券代码": "300001", "证券简称": "特锐德",
         "最新公告日": "2026-04-14", "百日新高": "Y", "20日均线": "", "国企": "", "一级板块": "电气",
         "来源": "莫名其妙"},
    ]
    rows = {"质押": [(_compress(pledge_records),)]}
    import tempfile, os
    with tempfile.TemporaryDirectory() as base:
        os.makedirs(os.path.join(base, "条件交集", "2026-04-20"), exist_ok=True)
        ex = WorkflowExecutor(base_dir=base, workflow_type="条件交集")
        with patch("core.database.AsyncSessionLocal", _patch_session(rows)):
            result = await ex._condition_intersection(
                {"type_order": ["质押"], "filter_conditions": [{"column": "百日新高", "enabled": True}]},
                date_str="2026-04-20"
            )
    df = result["_df"]
    # 两行都应兜底为 质押小盘
    assert (df["资本运作行为"] == "质押小盘").all()
    assert len(result["warnings"]) == 1
    assert "2/2" in result["warnings"][0]


@pytest.mark.asyncio
async def test_pledge_column_missing_entirely_all_fallback():
    """来源 列完全缺失 → 全部"质押小盘" + warning。"""
    pledge_records = [
        {"序号": 1, "证券代码": "000001", "证券简称": "平安",
         "最新公告日": "2026-04-14", "百日新高": "Y", "20日均线": "", "国企": "", "一级板块": "银行"},
    ]
    rows = {"质押": [(_compress(pledge_records),)]}
    import tempfile, os
    with tempfile.TemporaryDirectory() as base:
        os.makedirs(os.path.join(base, "条件交集", "2026-04-20"), exist_ok=True)
        ex = WorkflowExecutor(base_dir=base, workflow_type="条件交集")
        with patch("core.database.AsyncSessionLocal", _patch_session(rows)):
            result = await ex._condition_intersection(
                {"type_order": ["质押"], "filter_conditions": [{"column": "百日新高", "enabled": True}]},
                date_str="2026-04-20"
            )
    df = result["_df"]
    assert (df["资本运作行为"] == "质押小盘").all()
    assert len(result["warnings"]) == 1
    assert "完全缺少'来源'列" in result["warnings"][0]
