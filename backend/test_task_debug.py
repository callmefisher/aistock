import httpx

base_url = "http://localhost:8000"
client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

unique_id = "task_debug"
client.post("/api/v1/auth/register", json={
    "username": f"task_{unique_id}",
    "email": f"task_{unique_id}@test.com",
    "password": "TestPass123!"
})

login_resp = client.post("/api/v1/auth/login", data={
    "username": f"task_{unique_id}",
    "password": "TestPass123!"
})
token = login_resp.json()["access_token"]

ds_resp = client.post("/api/v1/data-sources/",
    headers={"Authorization": f"Bearer {token}"},
    json={"name": "测试", "website_url": "https://test.com", "login_type": "password", "data_format": "excel"}
)
print(f"Create DS: {ds_resp.status_code}")
ds_id = ds_resp.json()["id"]

rule_resp = client.post("/api/v1/rules/",
    headers={"Authorization": f"Bearer {token}"},
    json={"name": "测试规则", "description": "测试", "natural_language": "筛选PE小于20"}
)
print(f"Create Rule: {rule_resp.status_code}")
print(f"Rule Response: {rule_resp.text}")
rule_id = rule_resp.json()["id"]

task_resp = client.post("/api/v1/tasks/",
    headers={"Authorization": f"Bearer {token}"},
    json={"name": "测试任务", "data_source_ids": [ds_id], "rule_ids": [rule_id], "schedule_type": "manual"}
)
print(f"Create Task: {task_resp.status_code}")
print(f"Task Response: {task_resp.text[:500] if task_resp.text else 'empty'}")
