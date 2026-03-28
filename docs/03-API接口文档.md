# API接口文档

## 基础信息

### 基础URL
```
http://localhost/api/v1
```

### 认证方式
使用JWT Bearer Token认证：
```
Authorization: Bearer <your_token>
```

### 通用响应格式

#### 成功响应
```json
{
  "id": 1,
  "name": "资源名称",
  "created_at": "2024-01-01T00:00:00"
}
```

#### 错误响应
```json
{
  "detail": "错误信息描述"
}
```

### HTTP状态码
| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 422 | 验证错误 |
| 500 | 服务器错误 |

## 认证接口

### 用户注册

**POST** `/auth/register`

#### 请求参数
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```

#### 响应示例
```json
{
  "id": 1,
  "username": "testuser",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false
}
```

#### 错误示例
```json
{
  "detail": "用户名已存在"
}
```

### 用户登录

**POST** `/auth/login`

#### 请求参数
```
Content-Type: application/x-www-form-urlencoded

username=testuser&password=password123
```

#### 响应示例
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 获取当前用户信息

**GET** `/auth/me`

#### 请求头
```
Authorization: Bearer <your_token>
```

#### 响应示例
```json
{
  "id": 1,
  "username": "testuser",
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false
}
```

## 数据源接口

### 获取数据源列表

**GET** `/data-sources`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | integer | 否 | 跳过记录数，默认0 |
| limit | integer | 否 | 返回记录数，默认100 |

#### 响应示例
```json
[
  {
    "id": 1,
    "name": "东方财富",
    "website_url": "https://www.eastmoney.com",
    "login_type": "password",
    "data_format": "excel",
    "is_active": true,
    "last_login_time": "2024-01-01T10:00:00",
    "last_fetch_time": "2024-01-01T10:30:00",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### 创建数据源

**POST** `/data-sources`

#### 请求参数
```json
{
  "name": "东方财富",
  "website_url": "https://www.eastmoney.com",
  "login_type": "password",
  "login_config": {
    "username": "your_username",
    "password": "your_password",
    "username_selector": "#username",
    "password_selector": "#password",
    "submit_selector": "#login-btn",
    "success_indicator": ".user-info"
  },
  "data_format": "excel",
  "extraction_config": {
    "download_url": "https://www.eastmoney.com/export",
    "method": "GET"
  }
}
```

#### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 数据源名称 |
| website_url | string | 是 | 网站URL |
| login_type | string | 是 | 登录类型：password/captcha/qrcode/cookie |
| login_config | object | 否 | 登录配置 |
| data_format | string | 是 | 数据格式：excel/table/api |
| extraction_config | object | 否 | 数据提取配置 |

#### login_config配置说明

##### password登录类型
```json
{
  "username": "用户名",
  "password": "密码",
  "username_selector": "用户名输入框CSS选择器",
  "password_selector": "密码输入框CSS选择器",
  "submit_selector": "提交按钮CSS选择器",
  "success_indicator": "登录成功标识CSS选择器"
}
```

##### captcha登录类型
```json
{
  "username": "用户名",
  "password": "密码",
  "captcha_selector": "验证码图片CSS选择器",
  "captcha_input_selector": "验证码输入框CSS选择器"
}
```

##### qrcode登录类型
```json
{
  "qrcode_selector": "二维码图片CSS选择器"
}
```

##### cookie登录类型
```json
{
  "cookies": [
    {
      "name": "cookie_name",
      "value": "cookie_value",
      "domain": ".example.com"
    }
  ]
}
```

#### extraction_config配置说明

##### Excel下载类型
```json
{
  "download_url": "Excel下载链接",
  "method": "GET或POST",
  "params": {}
}
```

##### 网页表格类型
```json
{
  "table_selector": "表格CSS选择器",
  "wait_time": 10,
  "pagination": {
    "enabled": true,
    "next_button_selector": "下一页按钮CSS选择器",
    "max_pages": 10
  }
}
```

##### API接口类型
```json
{
  "api_url": "API地址",
  "method": "GET或POST",
  "headers": {},
  "params": {},
  "data_key": "数据在响应中的key"
}
```

#### 响应示例
```json
{
  "id": 1,
  "name": "东方财富",
  "website_url": "https://www.eastmoney.com",
  "login_type": "password",
  "data_format": "excel",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

### 获取数据源详情

**GET** `/data-sources/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 数据源ID |

#### 响应示例
```json
{
  "id": 1,
  "name": "东方财富",
  "website_url": "https://www.eastmoney.com",
  "login_type": "password",
  "data_format": "excel",
  "is_active": true,
  "last_login_time": "2024-01-01T10:00:00",
  "created_at": "2024-01-01T00:00:"
}
```

### 更新数据源

**PUT** `/data-sources/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 数据源ID |

#### 请求参数
```json
{
  "name": "东方财富（更新）",
  "is_active": false
}
```

#### 响应示例
```json
{
  "id": 1,
  "name": "东方财富（更新）",
  "is_active": false,
  "updated_at": "2024-01-01T12:00:00"
}
```

### 删除数据源

**DELETE** `/data-sources/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 数据源ID |

#### 响应示例
```json
{
  "message": "数据源已删除"
}
```

## 规则接口

### 获取规则列表

**GET** `/rules`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | integer | 否 | 跳过记录数，默认0 |
| limit | integer | 否 | 返回记录数，默认100 |

#### 响应示例
```json
[
  {
    "id": 1,
    "name": "低估值筛选",
    "description": "筛选PE小于20且ROE大于15%的股票",
    "natural_language": "筛选PE小于20且ROE大于15%的股票",
    "excel_formula": "=AND(PE<20,ROE>15)",
    "filter_conditions": [
      {
        "column": "PE",
        "operator": "less_than",
        "value": 20
      },
      {
        "column": "ROE",
        "operator": "greater_than",
        "value": 15
      }
    ],
    "priority": 0,
    "is_active": true,
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### 创建规则

**POST** `/rules`

#### 请求参数
```json
{
  "name": "低估值筛选",
  "description": "筛选PE小于20且ROE大于15%的股票",
  "natural_language": "筛选PE小于20且ROE大于15%的股票"
}
```

#### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 规则名称 |
| description | string | 否 | 规则描述 |
| natural_language | string | 是 | 自然语言规则描述 |

#### 支持的自然语言格式
- "筛选PE小于20的股票"
- "选择市值大于100亿的股票"
- "过滤掉ST股票"
- "筛选PE小于20且ROE大于15%的股票"
- "选择股价在10到50元之间的股票"

#### 响应示例
```json
{
  "id": 1,
  "name": "低估值筛选",
  "natural_language": "筛选PE小于20且ROE大于15%的股票",
  "excel_formula": "=AND(PE<20,ROE>15)",
  "filter_conditions": [
    {
      "column": "PE",
      "operator": "less_than",
      "value": 20
    }
  ],
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

### 获取规则详情

**GET** `/rules/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 规则ID |

#### 响应示例
```json
{
  "id": 1,
  "name": "低估值筛选",
  "description": "筛选PE小于20且ROE大于15%的股票",
  "natural_language": "筛选PE小于20且ROE大于15%的股票",
  "excel_formula": "=AND(PE<20,ROE>15)",
  "filter_conditions": [...],
  "is_active": true
}
```

### 更新规则

**PUT** `/rules/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 规则ID |

#### 请求参数
```json
{
  "name": "低估值筛选（更新）",
  "natural_language": "筛选PE小于25且ROE大于12%的股票"
}
```

#### 响应示例
```json
{
  "id": 1,
  "name": "低估值筛选（更新）",
  "natural_language": "筛选PE小于25且ROE大于12%的股票",
  "excel_formula": "=AND(PE<25,ROE>12)",
  "updated_at": "2024-01-01T12:00:00"
}
```

### 删除规则

**DELETE** `/rules/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 规则ID |

#### 响应示例
```json
{
  "message": "规则已删除"
}
```

### 验证规则

**POST** `/rules/{id}/validate`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 规则ID |

#### 请求参数
```json
{
  "columns": ["PE", "ROE", "Name", "Price"]
}
```

#### 响应示例
```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

#### 错误示例
```json
{
  "valid": false,
  "errors": [
    "列 'MarketCap' 不存在于数据中"
  ],
  "warnings": []
}
```

## 任务接口

### 获取任务列表

**GET** `/tasks`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | integer | 否 | 跳过记录数，默认0 |
| limit | integer | 否 | 返回记录数，默认100 |

#### 响应示例
```json
[
  {
    "id": 1,
    "name": "每日选股任务",
    "data_source_ids": [1, 2],
    "rule_ids": [1, 2],
    "schedule_type": "cron",
    "schedule_config": {
      "cron_expression": "0 9 * * 1-5"
    },
    "status": "completed",
    "last_run_time": "2024-01-01T09:00:00",
    "next_run_time": "2024-01-02T09:00:00",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00"
  }
]
```

### 创建任务

**POST** `/tasks`

#### 请求参数
```json
{
  "name": "每日选股任务",
  "data_source_ids": [1, 2],
  "rule_ids": [1, 2],
  "schedule_type": "cron",
  "schedule_config": {
    "cron_expression": "0 9 * * 1-5"
  }
}
```

#### 字段说明
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 任务名称 |
| data_source_ids | array | 是 | 数据源ID列表 |
| rule_ids | array | 是 | 规则ID列表 |
| schedule_type | string | 是 | 调度类型：manual/cron/interval |
| schedule_config | object | 否 | 调度配置 |

#### schedule_config配置说明

##### manual类型
```json
{
  "schedule_type": "manual"
}
```

##### cron类型
```json
{
  "schedule_type": "cron",
  "schedule_config": {
    "cron_expression": "0 9 * * 1-5"
  }
}
```

Cron表达式格式：`分 时 日 月 周`
- `0 9 * * 1-5` - 每个工作日早上9点
- `0 */2 * * *` - 每2小时
- `30 18 * * *` - 每天18:30

##### interval类型
```json
{
  "schedule_type": "interval",
  "schedule_config": {
    "interval_seconds": 3600
  }
}
```

#### 响应示例
```json
{
  "id": 1,
  "name": "每日选股任务",
  "data_source_ids": [1, 2],
  "rule_ids": [1, 2],
  "schedule_type": "cron",
  "status": "pending",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00"
}
```

### 获取任务详情

**GET** `/tasks/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 任务ID |

#### 响应示例
```json
{
  "id": 1,
  "name": "每日选股任务",
  "data_source_ids": [1, 2],
  "rule_ids": [1, 2],
  "schedule_type": "cron",
  "schedule_config": {...},
  "status": "completed",
  "last_run_time": "2024-01-01T09:00:00",
  "next_run_time": "2024-01-02T09:00:00",
  "is_active": true
}
```

### 更新任务

**PUT** `/tasks/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 任务ID |

#### 请求参数
```json
{
  "name": "每日选股任务（更新）",
  "is_active": false
}
```

#### 响应示例
```json
{
  "id": 1,
  "name": "每日选股任务（更新）",
  "is_active": false,
  "updated_at": "2024-01-01T12:00:00"
}
```

### 删除任务

**DELETE** `/tasks/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 任务ID |

#### 响应示例
```json
{
  "message": "任务已删除"
}
```

### 执行任务

**POST** `/tasks/{id}/run`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 任务ID |

#### 响应示例
```json
{
  "message": "任务 1 已加入执行队列"
}
```

### 获取任务执行日志

**GET** `/tasks/{id}/logs`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 任务ID |

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | integer | 否 | 跳过记录数，默认0 |
| limit | integer | 否 | 返回记录数，默认50 |

#### 响应示例
```json
[
  {
    "id": 1,
    "task_id": 1,
    "status": "completed",
    "start_time": "2024-01-01T09:00:00",
    "end_time": "2024-01-01T09:05:00",
    "duration": 300.5,
    "records_processed": 1000,
    "output_file": "/app/data/excel/stock_pool_task1_20240101.xlsx",
    "created_at": "2024-01-01T09:00:00"
  }
]
```

## 选股池接口

### 获取选股池列表

**GET** `/stock-pools`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | integer | 否 | 跳过记录数，默认0 |
| limit | integer | 否 | 返回记录数，默认100 |

#### 响应示例
```json
[
  {
    "id": 1,
    "name": "选股池_20240101",
    "task_id": 1,
    "file_path": "/app/data/excel/stock_pool_task1_20240101.xlsx",
    "total_stocks": 50,
    "is_active": true,
    "created_at": "2024-01-01T09:05:00",
    "updated_at": "2024-01-01T09:05:00"
  }
]
```

### 获取选股池详情

**GET** `/stock-pools/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 选股池ID |

#### 响应示例
```json
{
  "id": 1,
  "name": "选股池_20240101",
  "task_id": 1,
  "file_path": "/app/data/excel/stock_pool_task1_20240101.xlsx",
  "total_stocks": 50,
  "is_active": true,
  "created_at": "2024-01-01T09:05:00"
}
```

### 下载选股池

**GET** `/stock-pools/{id}/download`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 选股池ID |

#### 响应
返回Excel文件流，Content-Type为：
```
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

#### 响应头
```
Content-Disposition: attachment; filename="stock_pool_1.xlsx"
```

### 删除选股池

**DELETE** `/stock-pools/{id}`

#### 路径参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | integer | 是 | 选股池ID |

#### 响应示例
```json
{
  "message": "选股池已删除"
}
```

## 错误码说明

### 通用错误码
| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未认证，需要登录 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 422 | 数据验证失败 |
| 500 | 服务器内部错误 |

### 业务错误码
| 错误信息 | 说明 |
|----------|------|
| 用户名已存在 | 注册时用户名重复 |
| 邮箱已存在 | 注册时邮箱重复 |
| 用户名或密码错误 | 登录失败 |
| 数据源不存在 | 数据源ID无效 |
| 规则不存在 | 规则ID无效 |
| 任务不存在 | 任务ID无效 |
| 选股池不存在 | 选股池ID无效 |
| 文件不存在 | Excel文件丢失 |

## 使用示例

### 完整工作流示例

#### 1. 用户注册和登录
```bash
# 注册
curl -X POST http://localhost/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "user@example.com",
    "password": "password123"
  }'

# 登录
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"

# 返回token
# {"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", "token_type": "bearer"}
```

#### 2. 创建数据源
```bash
curl -X POST http://localhost/api/v1/data-sources \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "东方财富",
    "website_url": "https://www.eastmoney.com",
    "login_type": "password",
    "login_config": {...},
    "data_format": "excel",
    "extraction_config": {...}
  }'
```

#### 3. 创建规则
```bash
curl -X POST http://localhost/api/v1/rules \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "低估值筛选",
    "natural_language": "筛选PE小于20且ROE大于15%的股票"
  }'
```

#### 4. 创建任务
```bash
curl -X POST http://localhost/api/v1/tasks \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "每日选股任务",
    "data_source_ids": [1],
    "rule_ids": [1],
    "schedule_type": "cron",
    "schedule_config": {
      "cron_expression": "0 9 * * 1-5"
    }
  }'
```

#### 5. 执行任务
```bash
curl -X POST http://localhost/api/v1/tasks/1/run \
  -H "Authorization: Bearer <your_token>"
```

#### 6. 查看结果
```bash
# 获取选股池列表
curl -X GET http://localhost/api/v1/stock-pools \
  -H "Authorization: Bearer <your_token>"

# 下载选股池
curl -X GET http://localhost/api/v1/stock-pools/1/download \
  -H "Authorization: Bearer <your_token>" \
  -o stock_pool.xlsx
```

## 最佳实践

### 1. 错误处理
始终检查HTTP状态码和响应中的`detail`字段。

### 2. Token管理
- Token有效期：7天
- 在Token过期前刷新Token
- 安全存储Token，避免泄露

### 3. 数据源配置
- 先测试登录配置是否正确
- 使用CSS选择器时确保选择器准确
- 定期更新Cookie

### 4. 规则编写
- 使用清晰的自然语言描述
- 先验证规则再应用到任务
- 测试规则在示例数据上的效果

### 5. 任务调度
- 合理设置调度频率，避免过于频繁
- 监控任务执行日志
- 设置错误通知机制
