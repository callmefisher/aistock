import requests
import pandas as pd
from io import BytesIO

# 登录
login_resp = requests.post('http://localhost:8000/api/v1/auth/login',
                          data={'username': 'admin', 'password': 'admin123'})
token = login_resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print('1. 登录成功')

# 创建测试Excel
df = pd.DataFrame({'证券代码': ['TEST001.SZ'], '证券简称': ['测试A']})
buffer = BytesIO()
df.to_excel(buffer, index=False)
buffer.seek(0)

print('2. 创建测试Excel成功')

# 上传
files = {'file': ('test_upload.xlsx', buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
data = {'workflow_id': '1', 'step_index': '0', 'step_type': 'merge_excel', 'date_str': '2026-04-12'}
resp = requests.post('http://localhost:8000/api/v1/workflows/upload-step-file/',
                     files=files, data=data, headers=headers)
print(f'3. 上传响应: {resp.status_code} - {resp.json()}')

# 检查文件列表
list_resp = requests.get('http://localhost:8000/api/v1/workflows/step-files/',
                         params={'step_type': 'merge_excel', 'date_str': '2026-04-12'},
                         headers=headers)
print(f'4. 文件列表: {list_resp.json()}')

print('\n测试完成!')
