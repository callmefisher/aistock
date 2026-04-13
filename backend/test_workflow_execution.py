#!/usr/bin/env python3
"""
模拟真实点击执行工作流测试
"""
import requests
import json
import time

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

def execute_workflow_step(token, workflow_id, step_index):
    """执行工作流的单个步骤"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/workflows/{workflow_id}/execute-step/",
        headers=headers,
        json={"step_index": step_index}
    )
    return response

def main():
    print("=" * 70)
    print("模拟真实点击执行工作流测试")
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

    # 找到choice工作流
    choice_workflow = None
    for wf in workflows:
        if "choice" in wf["name"].lower():
            choice_workflow = wf
            break

    if not choice_workflow:
        print("✗ 未找到choice工作流")
        return

    print(f"\n[3] 找到工作流: {choice_workflow['name']} (ID: {choice_workflow['id']})")
    print(f"    类型: {choice_workflow.get('workflow_type', '默认')}")
    print(f"    步骤数: {len(choice_workflow['steps'])}")

    # 逐个执行步骤
    print("\n[4] 开始执行工作流步骤...")
    for i, step in enumerate(choice_workflow['steps']):
        print(f"\n步骤 {i+1}/{len(choice_workflow['steps'])}: {step['type']}")
        print(f"  配置: {json.dumps(step.get('config', {}), ensure_ascii=False, indent=4)}")

        try:
            response = execute_workflow_step(token, choice_workflow['id'], i)

            if response.status_code == 200:
                result = response.json()
                print(f"  ✓ 执行成功")
                if 'data' in result:
                    if 'records' in result['data']:
                        print(f"    返回记录数: {len(result['data']['records'])}")
                    if 'output_file' in result['data']:
                        print(f"    输出文件: {result['data']['output_file']}")
            else:
                print(f"  ✗ 执行失败")
                print(f"    状态码: {response.status_code}")
                print(f"    错误信息: {response.text}")
                break

        except Exception as e:
            print(f"  ✗ 执行异常: {e}")
            break

        time.sleep(1)

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
