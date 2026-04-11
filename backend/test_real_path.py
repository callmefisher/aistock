#!/usr/bin/env python3
"""
使用真实路径的端到端测试 - 能够发现真实环境的问题
"""
import os
import sys
import pandas as pd
import asyncio

sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')

from services.workflow_executor import WorkflowExecutor

REAL_BASE_DIR = "/Users/xiayanji/qbox/aistock/data/excel"

def test_real_path():
    """使用真实路径测试 - 能发现真实环境的问题"""
    print('=== 使用真实路径测试 ===\n')

    print(f'测试目录: {REAL_BASE_DIR}')
    print(f'检查目录是否存在...')

    if not os.path.exists(REAL_BASE_DIR):
        print(f'❌ 目录不存在: {REAL_BASE_DIR}')
        print(f'   可能的原因:')
        print(f'   1. Docker容器未挂载该目录')
        print(f'   2. 目录路径配置错误')
        print(f'   3. 权限问题')
        return False

    print(f'✓ 目录存在')

    executor = WorkflowExecutor(base_dir=REAL_BASE_DIR)
    print(f'✓ WorkflowExecutor初始化成功')

    date_str = '2026-04-09'
    daily_dir = os.path.join(REAL_BASE_DIR, date_str)
    print(f'\n检查当日目录: {daily_dir}')

    if os.path.exists(daily_dir):
        files = os.listdir(daily_dir)
        print(f'✓ 当日目录存在，文件: {files}')
    else:
        print(f'⚠ 当日目录不存在，将被创建')

    public_dir = os.path.join(REAL_BASE_DIR, '2025public')
    print(f'检查公共目录: {public_dir}')

    if os.path.exists(public_dir):
        files = os.listdir(public_dir)
        print(f'✓ 公共目录存在，文件: {files}')
    else:
        print(f'⚠ 公共目录不存在，将被创建')

    print('\n开始执行步骤1: 合并Excel')
    result = asyncio.run(executor.execute_step(
        step_type='merge_excel',
        step_config={
            'date_str': date_str,
            'output_filename': 'total_1.xlsx',
            'exclude_patterns': ['total_', 'output_']
        },
        date_str=date_str
    ))

    print(f'结果: success={result.get("success")}')
    print(f'消息: {result.get("message")}')

    if result.get('success'):
        print(f'✓ 合并成功')
        print(f'  合并文件数: {result.get("files_merged")}')
        print(f'  合并后行数: {result.get("rows")}')
    else:
        print(f'❌ 合并失败: {result.get("message")}')
        return False

    return True

if __name__ == '__main__':
    try:
        success = test_real_path()
        if success:
            print('\n✅ 测试通过')
        else:
            print('\n❌ 测试失败')
            exit(1)
    except Exception as e:
        print(f'\n❌ 测试异常: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
