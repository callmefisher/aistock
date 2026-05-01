import httpx
import time

BASE_URL = "http://localhost:7654"
API_URL = "http://localhost:8000"

print("=" * 50)
print("自动登录测试")
print("=" * 50)

# 1. 注册用户
unique_id = int(time.time()) % 100000
username = f"autotest{unique_id}"
email = f"autotest{unique_id}@test.com"
password = "Test123456"

print(f"\n[1] 注册用户: {username}")
client = httpx.Client(base_url=API_URL, timeout=30.0, follow_redirects=True)

register_resp = client.post("/api/v1/auth/register", json={
    "username": username,
    "email": email,
    "password": password
})

if register_resp.status_code == 200:
    print(f"    ✅ 注册成功")
else:
    print(f"    ⚠️ 注册响应: {register_resp.status_code} - {register_resp.text[:100]}")

# 2. 登录获取token
print(f"\n[2] 登录获取Token")
login_resp = client.post("/api/v1/auth/login", data={
    "username": username,
    "password": password
})

if login_resp.status_code == 200:
    token = login_resp.json()["access_token"]
    print(f"    ✅ 登录成功")
    print(f"    Token: {token[:50]}...")
else:
    print(f"    ❌ 登录失败: {login_resp.status_code}")
    exit(1)

# 3. 访问受保护资源
print(f"\n[3] 验证Token访问受保护资源")
headers = {"Authorization": f"Bearer {token}"}

endpoints = [
    "/api/v1/data-sources/",
    "/api/v1/rules/",
    "/api/v1/tasks/",
]

for endpoint in endpoints:
    resp = client.get(endpoint, headers=headers)
    status = "✅" if resp.status_code == 200 else f"❌ ({resp.status_code})"
    print(f"    {status} {endpoint}")

# 4. 获取用户信息
print(f"\n[4] 获取当前用户信息")
me_resp = client.get("/api/v1/auth/me", headers=headers)
if me_resp.status_code == 200:
    user_data = me_resp.json()
    print(f"    ✅ 用户名: {user_data['username']}")
    print(f"    ✅ 邮箱: {user_data['email']}")

print("\n" + "=" * 50)
print("自动登录测试完成!")
print("=" * 50)
print(f"\n💡 现在打开浏览器访问: {BASE_URL}")
print(f"   使用以下凭据登录:")
print(f"   用户名: {username}")
print(f"   密码: {password}")
