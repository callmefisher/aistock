#!/usr/bin/env python3
"""
简化的API测试 - 测试API接口和参数传递
"""
import os
import sys
import tempfile
import pandas as pd
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

    return tmpdir

def test_executor_with_config():
    """测试执行器使用配置的参数"""
    print('=== 测试执行器使用配置的参数 ===\n')

    with tempfile.TemporaryDirectory() as tmpdir:
        setup_test_data(tmpdir)
        executor = WorkflowExecutor(base_dir=tmpdir)

        print(f'测试目录: {tmpdir}')
        print(f'目录结构:')
        print(f'  2026-04-09/: {os.listdir(os.path.join(tmpdir, "2026-04-09"))}')
        print(f'  2025public/: {os.listdir(os.path.join(tmpdir, "2025public"))}')

        workflow_steps = [
            {
                "type": "merge_excel",
                "config": {
                    "date_str": "2026-04-09",
                    "output_filename": "total_1.xlsx",
                    "exclude_patterns": ["total_", "output_"]
                }
            },
            {
                "type": "smart_dedup",
                "config": {
                    "stock_code_column": "证券代码",
                    "date_column": "最新公告日"
                }
            },
            {
                "type": "extract_columns",
                "config": {
                    "use_fixed_columns": True,
                    "output_filename": "output_1.xlsx"
                }
            }
        ]

        current_data = None

        for i, step in enumerate(workflow_steps):
            step_type = step["type"]
            step_config = step["config"]
            date_str = step_config.get("date_str")

            print(f'\n步骤 {i+1}: {step_type}')
            print(f'  配置: {step_config}')
            print(f'  date_str: {date_str}')

            result = asyncio.run(executor.execute_step(
                step_type=step_type,
                step_config=step_config,
                input_data=current_data,
                date_str=date_str
            ))

            print(f'  结果: success={result.get("success")}')
            print(f'  消息: {result.get("message")}')

            if not result.get("success"):
                print(f'  ❌ 步骤失败!')
                return False

            current_data = result.get("data")

            if step_type == "merge_excel":
                print(f'  合并文件数: {result.get("files_merged")}')
                print(f'  合并后行数: {result.get("rows")}')
            elif step_type == "smart_dedup":
                print(f'  去重前行数: {result.get("original_rows")}')
                print(f'  去重后行数: {result.get("deduped_rows")}')
                print(f'  删除行数: {result.get("removed_rows")}')
            elif step_type == "extract_columns":
                print(f'  提取列: {result.get("columns")}')
                print(f'  输出文件: {result.get("file_path")}')

        print(f'\n最终数据:')
        print(current_data)

        output_path = os.path.join(tmpdir, '2026-04-09', 'output_1.xlsx')
        if os.path.exists(output_path):
            final_df = pd.read_excel(output_path)
            print(f'\n✅ 输出文件验证:')
            print(f'  路径: {output_path}')
            print(f'  行数: {len(final_df)}')
            print(f'  列: {list(final_df.columns)}')
            print(final_df)
            return True
        else:
            print(f'\n❌ 输出文件不存在: {output_path}')
            return False

def test_pydantic_models():
    """测试Pydantic模型能正确解析配置"""
    print('\n\n=== 测试Pydantic模型解析 ===\n')

    from api.workflows import WorkflowStep, WorkflowStepConfig

    step_data = {
        "type": "merge_excel",
        "config": {
            "date_str": "2026-04-09",
            "output_filename": "total_1.xlsx",
            "exclude_patterns": ["total_", "output_"],
            "exclude_patterns_text": "total_,output_",
            "use_fixed_columns": True
        },
        "status": "pending"
    }

    try:
        step = WorkflowStep(**step_data)
        print(f'✓ WorkflowStep解析成功')
        print(f'  type: {step.type}')
        print(f'  config: {step.config}')
        return True
    except Exception as e:
        print(f'❌ WorkflowStep解析失败: {e}')
        return False

if __name__ == '__main__':
    try:
        success1 = test_pydantic_models()
        if not success1:
            print('\n❌ Pydantic模型测试失败')
            exit(1)
        print('\n✅ Pydantic模型测试通过')

        success2 = test_executor_with_config()
        if not success2:
            print('\n❌ 执行器测试失败')
            exit(1)
        print('\n✅ 执行器测试通过')

        print('\n\n✅✅✅ 所有测试完全通过 ✅✅✅')
        print('测试结果: 执行器能正确接收前端传递的配置参数并执行')
    except Exception as e:
        print(f'\n\n❌ 测试异常: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
