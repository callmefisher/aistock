#!/usr/bin/env python3
"""
真正的API端到端测试 - 通过HTTP请求测试完整流程
"""
import os
import sys
import tempfile
import pandas as pd

sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import asyncio

from main import app
from core.database import Base, get_async_db
from models.models import User, Workflow
from api.auth import get_current_user, create_access_token
from services.workflow_executor import WorkflowExecutor

test_user = User(
    id=1,
    username="testuser",
    email="test@example.com",
    hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4pWGz3pKlNO1rO.G",
    is_active=True
)

def override_get_current_user():
    return test_user

app.dependency_overrides[get_current_user] = override_get_current_user

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_async_db] = get_test_db

client = TestClient(app)

def setup_test_excel_files():
    """创建测试Excel文件"""
    tmpdir = tempfile.mkdtemp()
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

def test_full_api_workflow():
    """完整的API端到端测试"""
    print('=== 真正的API端到端测试 ===\n')

    tmpdir = setup_test_excel_files()
    print(f'测试目录: {tmpdir}')

    executor = WorkflowExecutor(base_dir=tmpdir)

    print('\n1. 测试创建工作流')
    workflow_data = {
        "name": "测试工作流",
        "description": "API测试工作流",
        "steps": [
            {
                "type": "merge_excel",
                "config": {
                    "date_str": "2026-04-09",
                    "output_filename": "total_1.xlsx",
                    "exclude_patterns": ["total_", "output_"],
                    "exclude_patterns_text": "total_,output_"
                },
                "status": "pending"
            },
            {
                "type": "smart_dedup",
                "config": {
                    "stock_code_column": "证券代码",
                    "date_column": "最新公告日"
                },
                "status": "pending"
            },
            {
                "type": "extract_columns",
                "config": {
                    "use_fixed_columns": True,
                    "output_filename": "output_1.xlsx"
                },
                "status": "pending"
            }
        ]
    }

    response = client.post("/api/v1/workflows/", json=workflow_data)
    print(f'   创建工作流响应: {response.status_code}')

    if response.status_code != 200:
        print(f'   ❌ 创建失败: {response.text}')
        return False

    workflow = response.json()
    workflow_id = workflow["id"]
    print(f'   ✓ 工作流创建成功, ID: {workflow_id}')

    print('\n2. 测试获取工作流列表')
    response = client.get("/api/v1/workflows/")
    print(f'   获取列表响应: {response.status_code}')
    workflows = response.json()
    print(f'   ✓ 当前工作流数量: {len(workflows)}')

    print('\n3. 测试执行工作流步骤')

    steps_results = []
    for step_index in range(len(workflow_data["steps"])):
        print(f'\n   步骤 {step_index + 1}: {workflow_data["steps"][step_index]["type"]}')

        response = client.post(
            f"/api/v1/workflows/{workflow_id}/execute-step/",
            json={"step_index": step_index}
        )

        print(f'   响应状态: {response.status_code}')

        if response.status_code != 200:
            print(f'   ❌ 步骤执行失败: {response.text}')
            return False

        result = response.json()
        print(f'   ✓ 消息: {result.get("message")}')
        if result.get("data"):
            print(f'      数据: 行数={result["data"].get("rows")}, 列={result["data"].get("columns")}')

        steps_results.append(result)

    print('\n4. 验证输出文件')

    output_file = os.path.join(tmpdir, '2026-04-09', 'output_1.xlsx')
    if os.path.exists(output_file):
        result_df = pd.read_excel(output_file)
        print(f'   ✓ 输出文件已生成: {output_file}')
        print(f'   ✓ 行数: {len(result_df)}')
        print(f'   ✓ 列: {list(result_df.columns)}')
        print(f'\n   最终数据:\n{result_df}')
    else:
        print(f'   ❌ 输出文件不存在: {output_file}')
        return False

    print('\n5. 测试删除工作流')
    response = client.delete(f"/api/v1/workflows/{workflow_id}/")
    print(f'   删除响应: {response.status_code}')
    if response.status_code == 200:
        print(f'   ✓ 工作流已删除')

    print('\n=== API端到端测试完成 ===')
    return True

def test_direct_executor():
    """直接测试执行器（验证核心逻辑）"""
    print('\n\n=== 直接执行器测试 ===\n')

    tmpdir = setup_test_excel_files()
    executor = WorkflowExecutor(base_dir=tmpdir)

    print(f'测试目录: {tmpdir}')
    print(f'当日目录文件: {os.listdir(os.path.join(tmpdir, "2026-04-09"))}')
    print(f'公共目录文件: {os.listdir(os.path.join(tmpdir, "2025public"))}')

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
    print(f'  结果: {result1.get("success")}, {result1.get("message")}')
    print(f'  合并后行数: {result1.get("rows")}')

    if not result1.get('success'):
        return False

    print('\n步骤2: 智能去重')
    result2 = asyncio.run(executor.execute_step(
        step_type='smart_dedup',
        step_config={
            'stock_code_column': '证券代码',
            'date_column': '最新公告日'
        },
        input_data=result1.get('data')
    ))
    print(f'  结果: {result2.get("success")}, {result2.get("message")}')
    print(f'  去重后行数: {result2.get("deduped_rows")}')

    if not result2.get('success'):
        return False

    print('\n步骤3: 提取列')
    result3 = asyncio.run(executor.execute_step(
        step_type='extract_columns',
        step_config={
            'use_fixed_columns': True,
            'output_filename': 'output_1.xlsx'
        },
        input_data=result2.get('data')
    ))
    print(f'  结果: {result3.get("success")}, {result3.get("message")}')
    print(f'  列: {result3.get("columns")}')
    print(f'  文件: {result3.get("file_path")}')

    if os.path.exists(result3.get('file_path')):
        df = pd.read_excel(result3.get('file_path'))
        print(f'\n  ✓ 最终结果: {len(df)}行, 列: {list(df.columns)}')
        print(df)
        return True
    else:
        print(f'\n  ❌ 输出文件不存在')
        return False

if __name__ == '__main__':
    try:
        success1 = test_direct_executor()
        if success1:
            print('\n\n✅ 直接执行器测试通过')
        else:
            print('\n\n❌ 直接执行器测试失败')
            exit(1)

        success2 = test_full_api_workflow()
        if success2:
            print('\n\n✅ API端到端测试通过')
        else:
            print('\n\n❌ API端到端测试失败')
            exit(1)

        print('\n\n✅✅✅ 所有测试完全通过 ✅✅✅')
    except Exception as e:
        print(f'\n\n❌ 测试异常: {e}')
        import traceback
        traceback.print_exc()
        exit(1)
