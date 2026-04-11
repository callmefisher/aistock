#!/usr/bin/env python3
import pandas as pd
import tempfile
import sys
import asyncio
sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')
from services.workflow_executor import WorkflowExecutor

df = pd.DataFrame({
    '证券代码': ['002128.SZ', '002128.SZ', '002128.SZ'],
    '证券简称': ['A', 'B', 'C'],
    '最新公告日': ['2026-04-09', '2026-04-01', '2026-05-01']
})

with tempfile.TemporaryDirectory() as tmpdir:
    executor = WorkflowExecutor(base_dir=tmpdir)
    result = asyncio.run(executor._smart_dedup({}, df))
    print('原始行数:', result['original_rows'])
    print('去重后行数:', result['deduped_rows'])
    print('保留的数据:')
    print(result['data'])
    print('最新公告日值类型:', type(result['data'].iloc[0]['最新公告日']))
    print('最新公告日值:', result['data'].iloc[0]['最新公告日'])
