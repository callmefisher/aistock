import httpx

base_url = "http://localhost:8000"
client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True)

unique_id = "debug2"
client.post("/api/v1/auth/register", json={
    "username": f"debug_{unique_id}",
    "email": f"debug_{unique_id}@test.com",
    "password": "TestPass123!"
})

login_resp = client.post("/api/v1/auth/login", data={
    "username": f"debug_{unique_id}",
    "password": "TestPass123!"
})
token = login_resp.json()["access_token"]

ds_resp = client.post("/api/v1/data-sources/",
    headers={"Authorization": f"Bearer {token}"},
    json={"name": "测试", "website_url": "https://test.com", "login_type": "password", "data_format": "excel"}
)
print(f"Create: {ds_resp.status_code}")
ds_id = ds_resp.json()["id"]

auth_client = httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True,
    headers={"Authorization": f"Bearer {token}"})

resp1 = auth_client.put(f"/api/v1/data-sources/{ds_id}/", json={"name": "更新"})
print(f"PUT with /: {resp1.status_code}")

resp2 = auth_client.put(f"/api/v1/data-sources/{ds_id}", json={"name": "更新"})
print(f"PUT without /: {resp2.status_code}")
