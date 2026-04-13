#!/usr/bin/env python3
"""
执行工作流并测试下载
"""
import requests
import time
import os

BASE_URL = "http://localhost:8000/api/v1"

def login():
    """登录获取token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"登录失败: {response.text}")

def execute_workflow_and_download(token, workflow_id):
    """执行工作流并测试下载"""
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n{'='*70}")
    print(f"执行工作流 {workflow_id} 并测试下载")
    print(f"{'='*70}")

    # 获取工作流信息
    response = requests.get(f"{BASE_URL}/workflows/{workflow_id}", headers=headers)
    workflow = response.json()

    print(f"\n工作流信息:")
    print(f"  名称: {workflow['name']}")
    print(f"  类型: {workflow.get('workflow_type', '默认')}")
    print(f"  步骤数: {len(workflow['steps'])}")

    # 执行每个步骤
    print(f"\n执行工作流...")
    for i in range(len(workflow['steps'])):
        print(f"\n步骤 {i+1}/{len(workflow['steps'])}: {workflow['steps'][i]['type']}")

        response = requests.post(
            f"{BASE_URL}/workflows/{workflow_id}/execute-step/",
            headers=headers,
            json={"step_index": i}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"  ✓ 执行成功")
            if 'output_file' in result.get('data', {}):
                print(f"    输出文件: {result['data']['output_file']}")
        else:
            print(f"  ✗ 执行失败: {response.text}")
            return

        time.sleep(0.5)

    # 测试下载
    print(f"\n测试下载...")
    download_url = f"{BASE_URL}/workflows/download-result/{workflow_id}"
    print(f"下载URL: {download_url}")

    response = requests.get(download_url, headers=headers)

    if response.status_code == 200:
        # 检查文件名
        content_disposition = response.headers.get('Content-Disposition', '')
        print(f"Content-Disposition: {content_disposition}")

        # 保存文件
        filename = f"test_download_{workflow_id}.xlsx"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✓ 下载成功: {filename}")
        print(f"  文件大小: {os.path.getsize(filename)} bytes")
        os.remove(filename)
    else:
        print(f"✗ 下载失败: {response.status_code}")
        print(f"  错误信息: {response.text}")

def main():
    print("=" * 70)
    print("执行工作流并测试下载")
    print("=" * 70)

    # 登录
    print("\n[1] 登录系统...")
    token = login()
    print("✓ 登录成功")

    # 获取工作流列表
    print("\n[2] 获取工作流列表...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/workflows/", headers=headers)
    workflows = response.json()
    print(f"✓ 找到 {len(workflows)} 个工作流")

    # 测试第一个工作流
    print("\n[3] 测试第一个工作流...")
    execute_workflow_and_download(token, workflows[0]['id'])

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
