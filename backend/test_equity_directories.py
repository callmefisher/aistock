#!/usr/bin/env python3
"""
测试创建股权转让类型工作流时的目录
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

def test_equity_transfer_directories():
    """测试股权转让类型的目录"""
    print("=" * 70)
    print("测试股权转让类型的目录")
    print("=" * 70)

    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    # 测试step-files API
    print("\n[1] 测试step-files API（股权转让类型）")
    response = requests.get(
        f"{BASE_URL}/workflows/step-files/",
        headers=headers,
        params={
            "step_type": "merge_excel",
            "date_str": "2026-04-12",
            "workflow_type": "股权转让"
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ API返回成功")
        print(f"  目录: {result['directory']}")
        print(f"  预期: /app/data/excel/股权转让/2026-04-12")
        print(f"  匹配: {'✓' if result['directory'] == '/app/data/excel/股权转让/2026-04-12' else '✗'}")
        print(f"  文件数: {len(result['files'])}")
    else:
        print(f"✗ API返回失败: {response.text}")

    # 测试public-files API
    print("\n[2] 测试public-files API（股权转让类型）")
    response = requests.get(
        f"{BASE_URL}/workflows/public-files/",
        headers=headers,
        params={
            "workflow_type": "股权转让"
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ API返回成功")
        print(f"  目录: {result['directory']}")
        print(f"  预期: /app/data/excel/股权转让/public")
        print(f"  匹配: {'✓' if result['directory'] == '/app/data/excel/股权转让/public' else '✗'}")
        print(f"  文件数: {len(result['files'])}")
    else:
        print(f"✗ API返回失败: {response.text}")

    # 测试默认类型
    print("\n[3] 测试step-files API（默认类型）")
    response = requests.get(
        f"{BASE_URL}/workflows/step-files/",
        headers=headers,
        params={
            "step_type": "merge_excel",
            "date_str": "2026-04-12",
            "workflow_type": ""
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ API返回成功")
        print(f"  目录: {result['directory']}")
        print(f"  预期: /app/data/excel/2026-04-12")
        print(f"  匹配: {'✓' if result['directory'] == '/app/data/excel/2026-04-12' else '✗'}")
    else:
        print(f"✗ API返回失败: {response.text}")

    print("\n[4] 测试public-files API（默认类型）")
    response = requests.get(
        f"{BASE_URL}/workflows/public-files/",
        headers=headers,
        params={
            "workflow_type": ""
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ API返回成功")
        print(f"  目录: {result['directory']}")
        print(f"  预期: /app/data/excel/2025public")
        print(f"  匹配: {'✓' if result['directory'] == '/app/data/excel/2025public' else '✗'}")
    else:
        print(f"✗ API返回失败: {response.text}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_equity_transfer_directories()
