#!/usr/bin/env python3
"""
完整测试：单个工作流下载和批量下载
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

def test_single_download(token, workflow_id):
    """测试单个工作流下载"""
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n{'='*70}")
    print(f"测试单个工作流下载 (ID: {workflow_id})")
    print(f"{'='*70}")

    # 获取工作流信息
    response = requests.get(f"{BASE_URL}/workflows/{workflow_id}", headers=headers)
    if response.status_code != 200:
        print(f"✗ 获取工作流失败: {response.text}")
        return

    workflow = response.json()
    print(f"\n工作流信息:")
    print(f"  名称: {workflow['name']}")
    print(f"  类型: {workflow.get('workflow_type', '默认')}")
    print(f"  步骤数: {len(workflow['steps'])}")

    # 测试下载
    download_url = f"{BASE_URL}/workflows/download-result/{workflow_id}"
    print(f"\n下载URL: {download_url}")

    response = requests.get(download_url, headers=headers)

    if response.status_code == 200:
        # 检查文件名
        content_disposition = response.headers.get('Content-Disposition', '')
        print(f"Content-Disposition: {content_disposition}")

        # 保存文件
        filename = f"test_single_download_{workflow_id}.xlsx"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✓ 下载成功: {filename}")
        print(f"  文件大小: {os.path.getsize(filename)} bytes")
        os.remove(filename)
    else:
        print(f"✗ 下载失败: {response.status_code}")
        print(f"  错误信息: {response.text}")

def test_batch_download(token, workflow_ids):
    """测试批量下载"""
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n{'='*70}")
    print(f"测试批量下载")
    print(f"{'='*70}")

    # 启动批量执行
    print(f"\n启动批量执行...")
    response = requests.post(
        f"{BASE_URL}/workflows/batch-run/",
        headers=headers,
        json={"workflow_ids": workflow_ids}
    )

    if response.status_code != 200:
        print(f"✗ 启动批量执行失败: {response.text}")
        return

    task_id = response.json()['task_id']
    print(f"✓ 批量任务已启动: {task_id}")

    # 等待完成
    print(f"\n等待批量执行完成...")
    max_wait = 60
    for i in range(max_wait):
        time.sleep(1)
        response = requests.get(
            f"{BASE_URL}/workflows/batch-status/{task_id}/",
            headers=headers
        )
        status = response.json()
        print(f"  [{i+1}s] 状态: {status['status']}, 完成: {status['completed']}/{status['total']}")

        if status['status'] in ['completed', 'partial', 'failed']:
            break

    # 查看结果
    print(f"\n批量执行结果:")
    for result in status.get('results', []):
        print(f"\n工作流 {result['workflow_id']}:")
        print(f"  状态: {result['status']}")
        if result.get('output_file'):
            print(f"  输出文件: {result['output_file']}")

    # 测试批量下载
    print(f"\n测试批量下载...")
    download_url = f"{BASE_URL}/workflows/batch-download/{task_id}"
    print(f"下载URL: {download_url}")

    response = requests.get(download_url, headers=headers)

    if response.status_code == 200:
        filename = "test_batch_download.zip"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"✓ 批量下载成功: {filename}")
        print(f"  文件大小: {os.path.getsize(filename)} bytes")

        # 解压查看文件名
        import zipfile
        with zipfile.ZipFile(filename, 'r') as zip_ref:
            print(f"\n压缩包内容:")
            for name in zip_ref.namelist():
                print(f"  - {name}")

        os.remove(filename)
    else:
        print(f"✗ 批量下载失败: {response.status_code}")
        print(f"  错误信息: {response.text}")

def main():
    print("=" * 70)
    print("完整测试：单个工作流下载和批量下载")
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

    # 测试单个下载
    print("\n[3] 测试单个工作流下载...")
    test_single_download(token, workflows[0]['id'])

    # 测试批量下载
    print("\n[4] 测试批量下载...")
    test_batch_download(token, [wf['id'] for wf in workflows[:2]])

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
