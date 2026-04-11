#!/usr/bin/env python3
"""测试完整工作流执行，查看步骤2的错误"""
import os
import sys
import pandas as pd
import asyncio

sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')

from services.workflow_executor import WorkflowExecutor

def test_workflow_step_by_step():
    print('=== 步骤执行测试 ===\n')

    executor = WorkflowExecutor()

    print(f'base_dir: {executor.base_dir}')

    print('\n步骤1: 合并Excel')
    result1 = asyncio.run(executor.execute_step(
        step_type='merge_excel',
        step_config={
            'date_str': '2026-04-09',
            'output_filename': 'total_1.xlsx',
            'exclude_patterns': ['total_', 'output_']
        },
        date_str='2026-04-09'
    ))
    print(f'成功: {result1.get("success")}')
    print(f'消息: {result1.get("message")}')

    if not result1.get('success'):
        print(f'❌ 步骤1失败')
        return

    merged_df = result1.get('data')
    print(f'\n合并后数据:')
    print(f'  列名: {list(merged_df.columns)}')
    print(f'  行数: {len(merged_df)}')
    print(f'  前3行:\n{merged_df.head(3)}')

    print('\n步骤2: 智能去重')
    result2 = asyncio.run(executor.execute_step(
        step_type='smart_dedup',
        step_config={
            'stock_code_column': '证券代码',
            'date_column': '最新公告日'
        },
        input_data=merged_df
    ))
    print(f'成功: {result2.get("success")}')
    print(f'消息: {result2.get("message")}')

    if not result2.get('success'):
        print(f'❌ 步骤2失败')
        return

    deduped_df = result2.get('data')
    print(f'\n去重后数据:')
    print(f'  列名: {list(deduped_df.columns)}')
    print(f'  行数: {len(deduped_df)}')
    print(f'  前3行:\n{deduped_df.head(3)}')

    print('\n步骤3: 提取列')
    result3 = asyncio.run(executor.execute_step(
        step_type='extract_columns',
        step_config={
            'use_fixed_columns': True,
            'output_filename': 'output_1.xlsx'
        },
        input_data=deduped_df
    ))
    print(f'成功: {result3.get("success")}')
    print(f'消息: {result3.get("message")}')

    if result3.get('success'):
        print(f'\n✅ 全部步骤执行成功!')
    else:
        print(f'❌ 步骤3失败')

if __name__ == '__main__':
    test_workflow_step_by_step()
