import asyncio
import sys
import os

sys.path.insert(0, "/Users/xiayanji/qbox/aistock/backend")
os.chdir("/Users/xiayanji/qbox/aistock/backend")

from services.workflow_executor import WorkflowExecutor

async def test_parallel():
    executor = WorkflowExecutor(base_dir="/Users/xiayanji/qbox/aistock/data/excel")
    config = {
        "date_str": "2026-04-30",
        "filter_conditions": [{"column": "百日新高并行20日均线", "enabled": True}],
        "filter_logic": "AND",
        "type_order": ["并购重组", "股权转让", "增发实现", "申报并购重组", "减持叠加质押和大宗交易", "质押", "招投标"],
        "output_filename": "7条件交集20260430.xlsx",
        "output_filename_high": "7条件交集20260430百日新高证券代码.xlsx",
        "output_filename_ma20": "7条件交集20260430站上20日线证券代码.xlsx",
        "high_price_periods": [{"start": "2026-03-18", "end": "2026-04-30"}],
        "_workflow_id": None,
    }
    result = await executor._condition_intersection(config, date_str="2026-04-30")
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    print(f"File: {result.get('file_path')}")
    print(f"Rows: {result.get('rows')}")
    if result.get('warnings'):
        for w in result['warnings']:
            print(f"Warning: {w}")

asyncio.run(test_parallel())
