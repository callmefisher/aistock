#!/usr/bin/env python3
import pandas as pd
import tempfile
import os
import sys
import asyncio
sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')

from services.workflow_executor import WorkflowExecutor

def test_smart_dedup():
    print('=== 测试智能去重 ===')
    df = pd.DataFrame({
        '证券代码': ['002128.SZ', '002128.SZ', '002128.SZ'],
        '证券简称': ['A', 'B', 'C'],
        '最新公告日': ['2026-04-09', '2026-04-01', '2026-05-01']
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = WorkflowExecutor(base_dir=tmpdir)
        result = asyncio.run(executor._smart_dedup({}, df))
        assert result['success'] == True, f"智能去重失败: {result['message']}"
        assert result['original_rows'] == 3, "原始行数错误"
        assert result['deduped_rows'] == 1, "去重后行数错误"
        retained_date = pd.Timestamp(result['data'].iloc[0]['最新公告日'])
        expected_date = pd.Timestamp('2026-05-01')
        assert retained_date == expected_date, f"保留的不是最新日期: {retained_date} vs {expected_date}"
        print(f'✓ 智能去重测试通过: 3行 -> 1行，保留最新公告日')

def test_merge_excel():
    print('\n=== 测试合并Excel ===')
    with tempfile.TemporaryDirectory() as tmpdir:
        daily_dir = os.path.join(tmpdir, '2026-04-09')
        public_dir = os.path.join(tmpdir, '2025public')
        os.makedirs(daily_dir, exist_ok=True)
        os.makedirs(public_dir, exist_ok=True)

        df1 = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
        df2 = pd.DataFrame({'A': [5, 6], 'B': [7, 8]})
        df3 = pd.DataFrame({'A': [9, 10], 'B': [11, 12]})

        df1.to_excel(os.path.join(daily_dir, 'file1.xlsx'), index=False)
        df2.to_excel(os.path.join(daily_dir, 'file2.xlsx'), index=False)
        df3.to_excel(os.path.join(public_dir, 'public1.xlsx'), index=False)

        executor = WorkflowExecutor(base_dir=tmpdir)
        result = asyncio.run(executor._merge_excel({'output_filename': 'total_1.xlsx'}))
        assert result['success'] == True, f"合并失败: {result['message']}"
        assert result['files_merged'] == 3, f"合并文件数错误: {result['files_merged']}"
        assert result['rows'] == 6, "合并后行数错误"
        print(f'✓ 合并Excel测试通过: 3个文件合并为6行')

def test_extract_columns():
    print('\n=== 测试提取固定列 ===')
    df = pd.DataFrame({
        '序号': [1, 2],
        '证券代码': ['002128.SZ', '600519.SH'],
        '证券简称': ['A', 'B'],
        '最新公告日': ['2026-04-01', '2026-04-02'],
        '其他列': ['x', 'y']
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = WorkflowExecutor(base_dir=tmpdir)
        result = asyncio.run(executor._extract_columns({}, df))
        assert result['success'] == True, f"提取列失败: {result['message']}"
        assert len(result['data'].columns) == 4, f"列数错误: {len(result['data'].columns)}"
        assert '证券代码' in result['columns'], "未包含证券代码列"
        assert '最新公告日' in result['columns'], "未包含最新公告日列"
        print(f'✓ 提取列测试通过: 提取了{len(result["columns"])}列: {result["columns"]}')

def test_exclude_total_output():
    print('\n=== 测试排除total_和output_文件 ===')
    with tempfile.TemporaryDirectory() as tmpdir:
        daily_dir = os.path.join(tmpdir, '2026-04-09')
        os.makedirs(daily_dir, exist_ok=True)

        df1 = pd.DataFrame({'A': [1]})
        df2 = pd.DataFrame({'A': [2]})
        df3 = pd.DataFrame({'A': [3]})
        df1.to_excel(os.path.join(daily_dir, 'source.xlsx'), index=False)
        df2.to_excel(os.path.join(daily_dir, 'total_1.xlsx'), index=False)
        df3.to_excel(os.path.join(daily_dir, 'output_1.xlsx'), index=False)

        executor = WorkflowExecutor(base_dir=tmpdir)
        result = asyncio.run(executor._merge_excel({'output_filename': 'merged.xlsx'}))
        assert result['success'] == True, f"合并失败: {result['message']}"
        assert result['files_merged'] == 1, f"应该只合并1个文件，实际: {result['files_merged']}"
        print(f'✓ 排除测试通过: 3个文件中排除了2个，只合并1个')

if __name__ == '__main__':
    try:
        test_smart_dedup()
        test_merge_excel()
        test_extract_columns()
        test_exclude_total_output()
        print('\n=== 所有核心测试通过! ===')
    except AssertionError as e:
        print(f'\n❌ 测试失败: {e}')
        exit(1)
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
