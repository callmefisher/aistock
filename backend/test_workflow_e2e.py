#!/usr/bin/env python3
"""
完整的工作流执行测试 - 模拟真实执行流程
"""
import pandas as pd
import tempfile
import os
import sys
import asyncio
sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')

from services.workflow_executor import WorkflowExecutor

def setup_test_data(tmpdir):
    """创建测试数据"""
    daily_dir = os.path.join(tmpdir, '2026-04-09')
    public_dir = os.path.join(tmpdir, '2025public')
    os.makedirs(daily_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)

    df1 = pd.DataFrame({
        '序号': [1, 2, 3],
        '证券代码': ['002128.SZ', '600519.SH', '000001.SZ'],
        '证券简称': ['露天煤业', '贵州茅台', '平安银行'],
        '最新公告日': ['2026-04-01', '2026-04-09', '2026-04-05']
    })
    df1.to_excel(os.path.join(daily_dir, 'source_1.xlsx'), index=False)

    df2 = pd.DataFrame({
        '序号': [4, 5, 6],
        '证券代码': ['002128.SZ', '600519.SH', '000002.SZ'],
        '证券简称': ['露天煤业', '贵州茅台', '万科A'],
        '最新公告日': ['2026-04-09', '2026-04-01', '2026-04-03']
    })
    df2.to_excel(os.path.join(public_dir, 'public_1.xlsx'), index=False)

    return daily_dir, public_dir

def test_full_workflow_execution():
    """测试完整工作流执行"""
    print('=== 测试完整工作流执行 ===\n')

    with tempfile.TemporaryDirectory() as tmpdir:
        daily_dir, public_dir = setup_test_data(tmpdir)
        executor = WorkflowExecutor(base_dir=tmpdir)

        print(f'测试目录: {tmpdir}')
        print(f'当日目录: {daily_dir}')
        print(f'公共目录: {public_dir}')
        print(f'当日目录文件: {os.listdir(daily_dir)}')
        print(f'公共目录文件: {os.listdir(public_dir)}')
        print()

        step1_config = {
            'date_str': '2026-04-09',
            'output_filename': 'total_1.xlsx',
            'exclude_patterns': ['total_', 'output_']
        }
        print('步骤1: 合并Excel')
        print(f'配置: {step1_config}')
        result1 = asyncio.run(executor.execute_step(
            step_type='merge_excel',
            step_config=step1_config,
            date_str=step1_config['date_str']
        ))
        print(f'结果: {result1}')

        if not result1.get('success'):
            print(f'❌ 步骤1失败: {result1.get("message")}')
            return False

        merged_df = result1.get('data')
        print(f'合并后数据行数: {len(merged_df)}')
        print(f'合并后数据:\n{merged_df}')
        print()

        step2_config = {
            'stock_code_column': '证券代码',
            'date_column': '最新公告日'
        }
        print('步骤2: 智能去重')
        print(f'配置: {step2_config}')
        result2 = asyncio.run(executor.execute_step(
            step_type='smart_dedup',
            step_config=step2_config,
            input_data=merged_df
        ))
        print(f'结果: {result2}')

        if not result2.get('success'):
            print(f'❌ 步骤2失败: {result2.get("message")}')
            return False

        deduped_df = result2.get('data')
        print(f'去重后数据行数: {len(deduped_df)}')
        print(f'去重后数据:\n{deduped_df}')
        print()

        step3_config = {
            'use_fixed_columns': True,
            'output_filename': 'output_1.xlsx'
        }
        print('步骤3: 提取列')
        print(f'配置: {step3_config}')
        result3 = asyncio.run(executor.execute_step(
            step_type='extract_columns',
            step_config=step3_config,
            input_data=deduped_df
        ))
        print(f'结果: {result3}')

        if not result3.get('success'):
            print(f'❌ 步骤3失败: {result3.get("message")}')
            return False

        final_df = result3.get('data')
        print(f'提取后数据列: {list(final_df.columns)}')
        print(f'提取后数据行数: {len(final_df)}')
        print(f'最终数据:\n{final_df}')
        print()

        output_path = result3.get('file_path')
        print(f'输出文件: {output_path}')
        if os.path.exists(output_path):
            print(f'✓ 输出文件已生成')
            result_df = pd.read_excel(output_path)
            print(f'验证读取: {len(result_df)}行, 列: {list(result_df.columns)}')
        else:
            print(f'❌ 输出文件不存在')

        print('\n=== 测试完成 ===')
        return True

def test_merge_step_only():
    """只测试合并步骤（最常用）"""
    print('\n=== 测试合并Excel步骤 ===\n')

    with tempfile.TemporaryDirectory() as tmpdir:
        daily_dir, public_dir = setup_test_data(tmpdir)
        executor = WorkflowExecutor(base_dir=tmpdir)

        config = {
            'date_str': '2026-04-09',
            'output_filename': 'total_1.xlsx',
            'exclude_patterns': ['total_', 'output_'],
            'exclude_patterns_text': 'total_,output_'
        }

        print(f'base_dir: {tmpdir}')
        print(f'配置: {config}')

        result = asyncio.run(executor.execute_step(
            step_type='merge_excel',
            step_config=config,
            date_str='2026-04-09'
        ))

        print(f'\n执行结果:')
        print(f'  success: {result.get("success")}')
        print(f'  message: {result.get("message")}')
        print(f'  files_merged: {result.get("files_merged")}')
        print(f'  rows: {result.get("rows")}')
        print(f'  file_path: {result.get("file_path")}')

        if result.get('success'):
            merged_df = result.get('data')
            print(f'\n合并数据预览:')
            print(merged_df.head())

            if os.path.exists(result.get('file_path')):
                print(f'\n✓ 文件已生成: {result.get("file_path")}')
            else:
                print(f'\n❌ 文件未生成')
                return False
        else:
            print(f'\n❌ 合并失败: {result.get("message")}')
            return False

        return True

if __name__ == '__main__':
    try:
        success1 = test_merge_step_only()
        if success1:
            print('\n\n=== 合并步骤测试通过 ===')
        else:
            print('\n\n=== 合并步骤测试失败 ===')
            exit(1)

        success2 = test_full_workflow_execution()
        if success2:
            print('\n\n=== 完整工作流测试通过 ===')
        else:
            print('\n\n=== 完整工作流测试失败 ===')
            exit(1)

        print('\n\n✅ 所有测试通过!')
    except Exception as e:
        print(f'\n\n❌ 测试异常: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
