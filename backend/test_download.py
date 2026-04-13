#!/usr/bin/env python3
"""
测试下载功能
"""
import requests
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

def test_download(token, workflow_id):
    """测试下载功能"""
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\n测试下载工作流 {workflow_id} 的结果...")

    # 获取工作流信息
    response = requests.get(f"{BASE_URL}/workflows/{workflow_id}", headers=headers)
    if response.status_code != 200:
        print(f"✗ 获取工作流失败: {response.text}")
        return

    workflow = response.json()
    print(f"工作流名称: {workflow['name']}")
    print(f"工作流类型: {workflow.get('workflow_type', '默认')}")

    # 测试下载
    download_url = f"{BASE_URL}/workflows/download-result/{workflow_id}"
    print(f"下载URL: {download_url}")

    response = requests.get(download_url, headers=headers)

    if response.status_code == 200:
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
    print("测试下载功能")
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

    # 测试每个工作流的下载功能
    print("\n[3] 测试下载功能...")
    for wf in workflows[:3]:  # 只测试前3个
        test_download(token, wf['id'])

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
