#!/usr/bin/env python3
"""
工作流文件上传和下载端到端测试
测试真实Docker环境中的所有功能
"""

import requests
import json
import time
import os
import tempfile
import pandas as pd
from io import BytesIO

BASE_URL = "http://localhost:8000/api/v1"
DATA_DIR = "/Users/xiayanji/qbox/aistock/data/excel"

def login():
    """登录获取token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    print(f"登录失败: {response.status_code} - {response.text}")
    return None

def get_headers(token):
    """获取认证头"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def create_test_excel(filepath, data=None):
    """创建测试Excel文件"""
    if data is None:
        data = {
            "证券代码": ["002128.SZ", "600519.SH", "000001.SZ"],
            "证券简称": ["露天煤业", "贵州茅台", "平安银行"],
            "最新公告日": ["2026-04-01", "2026-04-09", "2026-04-05"]
        }
    df = pd.DataFrame(data)
    df.to_excel(filepath, index=False)
    print(f"创建测试文件: {filepath}")
    return filepath

def test_upload_file(token, workflow_id, step_index, step_type, date_str, filepath):
    """测试文件上传"""
    print(f"\n=== 测试上传文件: {filepath} ===")
    headers = {"Authorization": f"Bearer {token}"}

    with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        params = {
            'workflow_id': workflow_id,
            'step_index': step_index,
            'step_type': step_type,
            'date_str': date_str
        }
        response = requests.post(
            f"{BASE_URL}/workflows/upload-step-file/",
            files=files,
            params=params,
            headers=headers
        )

    print(f"上传响应状态: {response.status_code}")
    print(f"上传响应内容: {response.text}")
    assert response.status_code == 200, f"上传失败: {response.text}"
    result = response.json()
    assert result.get("success") == True, f"上传失败: {result}"
    print(f"✓ 文件上传成功")
    return result

def test_list_files(token, step_type, date_str):
    """测试获取文件列表"""
    print(f"\n=== 测试获取文件列表: step_type={step_type}, date_str={date_str} ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/workflows/step-files/",
        params={"step_type": step_type, "date_str": date_str},
        headers=headers
    )

    print(f"列表响应状态: {response.status_code}")
    print(f"列表响应内容: {response.text}")
    assert response.status_code == 200, f"获取文件列表失败: {response.text}"
    result = response.json()
    assert result.get("success") == True, f"获取文件列表失败: {result}"
    files = result.get("files", [])
    print(f"✓ 文件列表获取成功，共 {len(files)} 个文件")
    return files

def test_preview_file(token, file_path):
    """测试预览文件"""
    print(f"\n=== 测试预览文件: {file_path} ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/workflows/step-files/preview",
        params={"file_path": file_path},
        headers=headers
    )

    print(f"预览响应状态: {response.status_code}")
    print(f"预览响应内容: {response.text[:500]}")
    assert response.status_code == 200, f"预览失败: {response.text}"
    result = response.json()
    assert result.get("success") == True, f"预览失败: {result}"
    print(f"✓ 文件预览成功，行数: {result.get('total_rows')}")
    return result

def test_delete_file(token, file_path):
    """测试删除文件"""
    print(f"\n=== 测试删除文件: {file_path} ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(
        f"{BASE_URL}/workflows/step-files/",
        params={"file_path": file_path},
        headers=headers
    )

    print(f"删除响应状态: {response.status_code}")
    print(f"删除响应内容: {response.text}")
    assert response.status_code == 200, f"删除失败: {response.text}"
    result = response.json()
    assert result.get("success") == True, f"删除失败: {result}"
    print(f"✓ 文件删除成功")
    return result

def test_create_workflow(token):
    """测试创建工作流"""
    print(f"\n=== 测试创建工作流 ===")
    headers = get_headers(token)
    workflow_data = {
        "name": f"测试上传工作流_{int(time.time())}",
        "description": "用于测试文件上传功能",
        "steps": [
            {
                "type": "merge_excel",
                "config": {
                    "date_str": "2026-04-12",
                    "output_filename": "test_merged.xlsx",
                    "exclude_patterns_text": "total_,output_"
                },
                "status": "pending"
            }
        ]
    }
    response = requests.post(
        f"{BASE_URL}/workflows/",
        json=workflow_data,
        headers=headers
    )

    print(f"创建工作流响应状态: {response.status_code}")
    print(f"创建工作流响应内容: {response.text}")
    assert response.status_code == 200, f"创建工作流失败: {response.text}"
    result = response.json()
    print(f"✓ 工作流创建成功，ID: {result.get('id')}")
    return result

def test_execute_workflow(token, workflow_id, step_index=0):
    """测试执行工作流步骤"""
    print(f"\n=== 测试执行工作流: workflow_id={workflow_id}, step_index={step_index} ===")
    headers = get_headers(token)
    response = requests.post(
        f"{BASE_URL}/workflows/{workflow_id}/execute-step/",
        json={"step_index": step_index},
        headers=headers
    )

    print(f"执行响应状态: {response.status_code}")
    print(f"执行响应内容: {response.text[:500]}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 步骤执行成功: {result.get('message')}")
        return result
    else:
        print(f"⚠ 步骤执行返回: {response.status_code}")
        return None

def test_download_result(token, workflow_id, step_index=None):
    """测试下载结果"""
    print(f"\n=== 测试下载结果: workflow_id={workflow_id} ===")
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/workflows/download-result/{workflow_id}"
    if step_index is not None:
        url += f"?step_index={step_index}"

    response = requests.get(url, headers=headers)

    print(f"下载响应状态: {response.status_code}")
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        print(f"✓ 下载成功，Content-Type: {content_type}")
        return response.content
    else:
        print(f"⚠ 下载返回: {response.status_code} - {response.text[:200]}")
        return None

def test_match_workflow(token):
    """测试匹配类工作流"""
    print(f"\n=== 测试匹配类工作流 ===")
    headers = get_headers(token)

    workflow_data = {
        "name": f"测试匹配工作流_{int(time.time())}",
        "description": "用于测试匹配功能",
        "steps": [
            {
                "type": "merge_excel",
                "config": {
                    "date_str": "2026-04-12",
                    "output_filename": "for_match.xlsx"
                },
                "status": "pending"
            },
            {
                "type": "match_high_price",
                "config": {
                    "source_dir": "百日新高",
                    "new_column_name": "百日新高",
                    "output_filename": "matched.xlsx"
                },
                "status": "pending"
            }
        ]
    }
    response = requests.post(
        f"{BASE_URL}/workflows/",
        json=workflow_data,
        headers=headers
    )

    print(f"创建匹配工作流响应状态: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 匹配工作流创建成功，ID: {result.get('id')}")
        return result
    return None

def main():
    print("=" * 60)
    print("工作流文件上传和下载端到端测试")
    print("=" * 60)

    # 1. 登录
    print("\n>>> 1. 登录...")
    token = login()
    if not token:
        print("登录失败，测试终止")
        return False
    print(f"✓ 登录成功")

    # 2. 创建测试工作流
    print("\n>>> 2. 创建测试工作流...")
    workflow = test_create_workflow(token)
    workflow_id = workflow.get("id")

    # 3. 创建测试Excel文件
    print("\n>>> 3. 准备测试数据...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # 为merge_excel创建测试文件
        merge_file = os.path.join(tmpdir, "test_data_1.xlsx")
        create_test_excel(merge_file)

        # 为百日新高创建测试文件
        high_price_data = {
            "股票代码": ["002128", "600519"],
            "股票简称": ["露天煤业", "贵州茅台"]
        }
        df = pd.DataFrame(high_price_data)
        high_price_file = os.path.join(tmpdir, "match_test.xlsx")
        df.to_excel(high_price_file, index=False)
        print(f"创建百日新高测试文件: {high_price_file}")

        # 4. 测试上传到merge_excel步骤（日期目录）
        print("\n>>> 4. 测试上传到merge_excel...")
        upload_result = test_upload_file(
            token, workflow_id, 0, "merge_excel", "2026-04-12", merge_file
        )

        # 5. 获取文件列表（merge_excel）
        print("\n>>> 5. 获取merge_excel文件列表...")
        files = test_list_files(token, "merge_excel", "2026-04-12")
        if files:
            # 6. 预览文件
            print("\n>>> 6. 预览文件...")
            test_preview_file(token, files[0]["path"])

            # 7. 删除文件
            print("\n>>> 7. 删除文件...")
            test_delete_file(token, files[0]["path"])

        # 8. 上传到match_high_price步骤
        print("\n>>> 8. 上传到百日新高目录...")
        upload_result = test_upload_file(
            token, workflow_id, 1, "match_high_price", "2026-04-12", high_price_file
        )

        # 9. 获取百日新高文件列表
        print("\n>>> 9. 获取百日新高文件列表...")
        files = test_list_files(token, "match_high_price", "2026-04-12")
        print(f"百日新高目录文件数: {len(files)}")

    # 10. 测试匹配工作流
    print("\n>>> 10. 创建匹配工作流...")
    match_workflow = test_match_workflow(token)
    if match_workflow:
        match_workflow_id = match_workflow.get("id")

        # 11. 上传百日新高数据
        print("\n>>> 11. 上传百日新高数据...")
        with tempfile.TemporaryDirectory() as tmpdir:
            high_price_data = {
                "股票代码": ["002128", "600519"],
                "股票简称": ["露天煤业", "贵州茅台"]
            }
            df = pd.DataFrame(high_price_data)
            high_price_file = os.path.join(tmpdir, "match_test.xlsx")
            df.to_excel(high_price_file, index=False)

            upload_result = test_upload_file(
                token, match_workflow_id, 1, "match_high_price", "2026-04-12", high_price_file
            )

            # 12. 获取百日新高文件
            print("\n>>> 12. 获取百日新高文件列表...")
            files = test_list_files(token, "match_high_price", "2026-04-12")

    # 13. 执行工作流
    print("\n>>> 13. 执行工作流...")
    test_execute_workflow(token, workflow_id, 0)

    # 14. 下载结果
    print("\n>>> 14. 下载结果...")
    content = test_download_result(token, workflow_id, 0)
    if content:
        print(f"✓ 下载成功，内容大小: {len(content)} bytes")

    print("\n" + "=" * 60)
    print("所有端到端测试完成!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    main()
