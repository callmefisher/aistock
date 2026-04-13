# Codebase Reference (代码库详细参考)

本文档详细记录每个模块的职责、关键函数签名、数据流和依赖关系，供快速定位和接管使用。

---

## 1. Backend — API Layer (`backend/api/`)

### auth.py — 认证模块

| Endpoint | Method | 功能 |
|----------|--------|------|
| `/register` | POST | 用户注册 (username, email, password) |
| `/login` | POST | OAuth2 密码登录，返回 JWT token |
| `/me` | GET | 获取当前用户信息 |

**依赖**: `models.User`, `core.config.settings`, `jose.jwt`, `passlib.bcrypt`

### workflows.py — 工作流模块 (最核心)

| Endpoint | Method | 功能 |
|----------|--------|------|
| `/` | POST | 创建工作流 (name, steps[], workflow_type) |
| `/` | GET | 分页列表 |
| `/{id}` | GET/PUT/DELETE | CRUD |
| `/types/` | GET | 可用工作流类型列表 |
| `/{id}/execute-step/` | POST | 执行单个步骤 (step_index) |
| `/{id}/run/` | POST | 触发工作流 |
| `/batch-run/` | POST | 批量并行执行多个工作流 |
| `/batch-status/{task_id}/` | GET | 批量执行状态查询 |
| `/batch-download/{task_id}` | GET | 批量结果 ZIP 下载 |
| `/download-result/{id}` | GET | 单个工作流结果下载 |
| `/upload-step-file/` | POST | 上传步骤源文件 |
| `/step-files/` | GET | 列出步骤目录文件 |
| `/delete-step-file/` | DELETE | 删除步骤文件 |
| `/preview-step-file/` | GET | 预览文件内容 |
| `/upload-public-file/` | POST | 上传公共文件 |
| `/public-files/` | GET | 列出公共文件 |
| `/delete-public-file/` | DELETE | 删除公共文件 |
| `/preview-public-file/` | GET | 预览公共文件 |

**关键逻辑 — `execute_workflow_step()`** (line 180-303):
- 从 DB 读取 workflow 和 steps 配置
- 解析 `date_str` (优先取第一步的 date_str)
- 如果 step_index > 0，读取上一步输出文件作为 input_data
- 调用 `WorkflowExecutor.execute_step()`
- 返回数据预览 (前100行)

**关键逻辑 — `batch_run_workflows()`**:
- 创建 `BatchExecution` 记录
- `asyncio.create_task` 启动后台执行
- 每个 workflow 顺序执行所有步骤
- 聚合结果到 batch_execution

### data_api.py — 金融数据模块

| Endpoint | Method | 功能 |
|----------|--------|------|
| `/query/sql` | POST | 自定义 SQL 查询 |
| `/query/stock-daily` | POST | 日线数据查询 |
| `/query/stocks-filter` | POST | 多条件筛选 (PE, PB, 市值等) |
| `/query/ai` | POST | 自然语言转 SQL (OpenAI) |
| `/stock/list` | GET | 全部股票列表 |
| `/industry/list` | GET | 行业分类列表 |
| `/stock/spot` | GET | 实时行情 (akshare) |
| `/fetch/daily-bar` | POST | 拉取并存储日线数据 |

### tasks.py, rules.py, data_sources.py, stock_pools.py

标准 CRUD + 业务逻辑，参见 CLAUDE.md 中的 API 概览。

---

## 2. Backend — Services Layer (`backend/services/`)

### workflow_executor.py — 工作流引擎 (核心)

**类**: `WorkflowExecutor(base_dir, workflow_type)`

| 方法 | 步骤类型 | 输入 | 输出文件 |
|------|---------|------|---------|
| `_merge_excel()` | merge_excel | 目录下所有 Excel | `total_1.xlsx` |
| `_smart_dedup()` | smart_dedup | DataFrame | `deduped.xlsx` |
| `_extract_columns()` | extract_columns | DataFrame | `output_2.xlsx` |
| `_match_high_price()` | match_high_price | DataFrame | `output_3.xlsx` |
| `_match_ma20()` | match_ma20 | DataFrame | `output_4.xlsx` |
| `_match_soe()` | match_soe | DataFrame | `output_5.xlsx` |
| `_match_sector()` | match_sector | DataFrame | `{type}{date}.xlsx` |
| `_import_excel()` | import_excel | 文件路径 | — |
| `_export_excel()` | export_excel | DataFrame | 自定义文件名 |
| `_dedup()` | dedup | DataFrame | — |

**`_merge_excel()` 详细逻辑** (line 169-301):
1. 获取上传目录 + 公共目录下的所有 Excel
2. 排除 `total_`, `output_`, `deduped` 开头的文件
3. 公共文件: `pd.read_excel(filepath, skiprows=1)`
4. 非公共文件: 动态查找序号=1所在行，从该行开始读取 (跳过元数据行)
   - 如果序号=1前一行包含已知列名（证券代码、证券简称、最新公告日等），自动重映射列名（双行表头支持）
   - 否则仅跳过元数据行，保留原始列名
5. 股权转让类型: 列名映射 (代码→证券代码, 名称→证券简称, 公告日期→最新公告日)
6. 仅保留 [序号, 证券代码, 证券简称, 最新公告日] 列
7. 按日期降序排序
8. 重编序号
9. 输出到 `total_1.xlsx`

**`_smart_dedup()` 详细逻辑** (line 322-409):
1. 自动检测 stock_code_col 和 date_col
2. 日期转 datetime → 降序排序 → `drop_duplicates(keep="first")`
3. 过滤 .NQ 后缀股票
4. 格式化日期为 YYYY-MM-DD
5. 重编序号
6. 输出到 `deduped.xlsx`

**`_match_*()` 共同逻辑**:
1. 从对应目录读取所有参考 Excel
2. 提取 stock_code → stock_name 映射
3. 对输入 DataFrame 的 证券代码 列调用 `match_stock_code_flexible()`
4. 匹配结果写入新列
5. 保存输出文件

### path_resolver.py — 路径解析器

**类**: `WorkflowPathResolver(base_dir, workflow_type)`

| 方法 | 用途 |
|------|------|
| `get_upload_directory(date_str)` | `{base_dir}/{date}` 或 `{base_dir}/股权转让/{date}` |
| `get_public_directory()` | `{base_dir}/2025public` 或 `{base_dir}/股权转让/public` |
| `get_output_filename(step_type, date_str)` | 步骤输出文件名 |
| `get_match_source_directory(step_type)` | 匹配源数据目录 |

缓存: `_resolvers` 字典按 `base_dir_workflow_type` 缓存实例。

### rule_engine.py — 规则引擎

**类**: `RuleEngine`

| 方法 | 用途 |
|------|------|
| `parse_natural_language(text)` | NL → filter_conditions + excel_formula |
| `_parse_with_openai(text)` | GPT-3.5-turbo 解析 |
| `_parse_with_rules(text)` | 正则模式匹配 (中文运算符) |

支持运算符: 大于/高于(>), 小于/低于(<), 等于(=), 包含(contains), 不包含(!contains)

### excel_processor.py — Excel 处理器

| 函数 | 用途 |
|------|------|
| `save_to_excel(df, filepath)` | 带格式保存 (蓝色表头、自适应列宽) |
| `read_excel(filepath)` | 读取为 DataFrame |
| `generate_stock_pool_excel()` | 生成多 Sheet 选股池报告 |

### data_extractor.py — 数据提取器

| 方法 | 用途 |
|------|------|
| `extract_from_website(url, config)` | Selenium 抓取网页表格 |
| `download_excel(url)` | HTTP 直接下载 Excel |
| `fetch_api_data(url, params)` | API JSON 请求 |

---

## 3. Backend — Data Layer

### models/models.py — ORM 模型

```python
class User:          # username, email (unique), hashed_password, is_active, is_superuser
class DataSource:    # name, website_url, login_type, login_config(JSON), extraction_config(JSON)
class Rule:          # name, natural_language, excel_formula, filter_conditions(JSON), priority
class Task:          # name, data_source_ids(JSON), rule_ids(JSON), schedule_type, status
class ExecutionLog:  # task_id(FK), status, start_time, end_time, duration, records_processed
class StockPool:     # name, task_id(FK), file_path, total_stocks, data(JSON)
class Workflow:      # name, description, workflow_type, steps(JSON[]), status, last_run_time
class BatchExecution: # id(UUID), workflow_ids(JSON), status, total, completed, failed, results(JSON)
```

### core/database.py

```python
async_engine    = create_async_engine(DATABASE_URL)        # aiomysql
sync_engine     = create_engine(DATABASE_URL_SYNC)         # pymysql
AsyncSessionLocal = sessionmaker(async_engine, AsyncSession)
SyncSessionLocal  = sessionmaker(sync_engine, Session)
```

### config/workflow_type_config.py

```python
WORKFLOW_TYPE_CONFIG = {
    "": { ... },           # 默认 = 并购重组
    "并购重组": { ... },    # 明确指定
    "股权转让": {
        "base_subdir": "股权转让",
        "directories": {
            "upload_date": "股权转让/{date}",
            "public": "股权转让/public",
        },
        ...
    }
}
```

新增工作流类型: 在此文件添加新 entry，PathResolver 自动适配。

---

## 4. Backend — Utils

### stock_code_normalizer.py

| 函数 | 签名 | 用途 |
|------|------|------|
| `normalize_stock_code(code)` | `str → str` | 清洗股票代码 (去空格/特殊字符) |
| `extract_numeric_code(code)` | `str → str` | 提取纯数字部分 (如 000001) |
| `match_stock_code_flexible(code, stock_dict)` | `str, dict → str` | 灵活匹配，返回匹配到的名称或空 |
| `is_public_file(filepath, public_dir)` | `str, str → bool` | 判断文件是否在公共目录下 |

---

## 5. Frontend Architecture

### 技术栈

| 库 | 版本 | 用途 |
|----|------|------|
| Vue | 3.3.8 | 框架 |
| Element Plus | 2.4.3 | UI 组件库 |
| Pinia | 2.1.7 | 状态管理 |
| Vue Router | 4.2.5 | 路由 |
| Axios | 1.6.2 | HTTP 客户端 |
| ECharts | 5.4.3 | 图表 |
| Vite | 5.0.4 | 构建工具 |

### 路由 (router/index.js)

| Path | Component | 说明 |
|------|-----------|------|
| `/login` | Login.vue | 公开 |
| `/` | Dashboard.vue | 需登录 |
| `/workflows` | Workflows.vue | 需登录 |
| `/tasks` | Tasks.vue | 需登录 |
| `/rules` | Rules.vue | 需登录 |
| `/data-sources` | DataSources.vue | 需登录 |
| `/stock-pools` | StockPools.vue | 需登录 |
| `/finance-data` | FinanceData.vue | 需登录 |
| `/excel-compare` | ExcelCompare.vue | 需登录 |

Auth guard: `beforeEach` 检查 `localStorage.token`，无 token 重定向到 `/login`。

### API 层 (utils/api.js)

```javascript
const api = axios.create({ baseURL: '/api/v1', timeout: 300000 })
// Request interceptor: Authorization: Bearer {token}
// Response interceptor: 401 → logout, 403/404/500 → ElMessage.error
// api.download(url, params) → blob 下载
```

### 状态管理 (stores/auth.js)

```javascript
const useAuthStore = defineStore('auth', {
  state: { token, user },
  actions: { login(), register(), fetchUser(), logout() }
})
// token 和 user 持久化到 localStorage
```

### 核心页面 — Workflows.vue

最复杂的组件 (~900+ 行)，功能包括:
- 工作流列表表格 + 批量选择
- 创建/编辑对话框 + 步骤构建器
- 10 种步骤类型的条件渲染和配置表单
- 文件上传 + 公共文件上传
- 实时文件预览
- 单步执行 + 全流程执行
- 批量执行 + 进度跟踪
- 结果下载 (单个/ZIP)

---

## 6. Infrastructure

### Docker Compose (docker-compose.minimal.yml)

```
mysql (8.0)       → port 3306, volume mysql_data, init.sql
redis (7-alpine)  → port 6379, volume redis_data
backend           → port 8000, build ./backend, depends mysql+redis
frontend          → port 7654, build ./frontend, depends backend
```

Network: `stock_network` (bridge)

### Nginx (frontend 内置)

```nginx
/ → /usr/share/nginx/html (Vue SPA, try_files $uri /index.html)
/api/ → http://backend:8000
/docs → http://backend:8000
client_max_body_size 50m
proxy_read_timeout 300s
```

### 部署脚本

| 脚本 | 用途 |
|------|------|
| `deploy.sh up` | 构建 + 启动所有服务 |
| `deploy.sh build` | 仅构建镜像 |
| `deploy.sh restart` | 停止 + 启动 |
| `deploy.sh ps` | 查看状态 |
| `deploy.sh logs [service]` | 查看日志 |
| `deploy.sh init-db` | 执行 fix_tables.sql |
| `build.sh` | 底层构建脚本 (DOCKER_BUILDKIT=1) |

---

## 7. 数据流完整路径

### 工作流执行 (以并购重组为例)

```
1. 用户上传 Excel → POST /upload-step-file/
   → 保存到 /data/excel/2026-04-13/

2. 执行 Step 0: merge_excel
   → 读取 /data/excel/2026-04-13/*.xlsx + /data/excel/2025public/*.xlsx
   → 公共文件 skiprows=1；非公共文件从序号=1行开始
   → 排除 total_/output_/deduped 文件
   → concat → 保留 [序号,证券代码,证券简称,最新公告日] → 按日期降序
   → 输出 total_1.xlsx

3. 执行 Step 1: smart_dedup
   → 读取 total_1.xlsx
   → 按证券代码去重，保留最新公告日最大的行
   → 过滤 .NQ 股票
   → 输出 deduped.xlsx

4. 执行 Step 2: extract_columns
   → 读取 deduped.xlsx
   → 提取指定列
   → 输出 output_2.xlsx

5. 执行 Step 3-6: match_*
   → 读取上一步输出
   → 与 百日新高/20日均线/国企/一级板块 目录数据匹配
   → 每步追加一列匹配结果
   → 输出 output_3~5.xlsx，最终 并购重组20260413.xlsx

6. 用户下载结果
   → GET /download-result/{workflow_id}
   → 或 批量 ZIP: GET /batch-download/{task_id}
```

### 步骤间数据传递

`workflows.py:execute_workflow_step()` 中:
- Step 0 输出 Excel 文件
- Step N (N>0) 根据上一步的 step_type 确定输出文件名
- 从磁盘读取上一步输出文件为 DataFrame
- 传入当前步骤的 executor 方法

---

## 8. 测试

### Backend (pytest)

```bash
cd backend
python -m pytest tests/ -v                              # 全部
python -m pytest tests/test_workflow_executor.py -v      # 工作流引擎
python -m pytest tests/test_workflow_executor.py::TestMergeExcelStartRow -v  # 合并起始行
```

**配置**: `backend/pytest.ini`
**Fixture**: `backend/conftest.py` (event_loop for async)

**关键测试类**:
- `TestWorkflowExecutor` — 基础步骤测试
- `TestSmartDedupLogic` — 去重逻辑测试
- `TestMergeExcelStartRow` — 合并起始行 bug 修复验证

### Frontend (vitest)

```bash
cd frontend
npm test                # vitest 单元测试
npm run test:e2e        # playwright E2E
npm run test:coverage   # 覆盖率
```

---

## 9. 已知问题和注意事项

1. **TestWorkflowExecutor 部分测试失败**: 早期测试未适配 date 子目录结构，不影响功能
2. **Python 版本**: 本地 3.7.1 (测试用)，Docker 内 3.11 (生产)
3. **SettingWithCopyWarning**: `df.iloc[start_idx:].copy()` 已修复
4. **docker-compose.minimal.yml `version` 字段**: Docker 警告 obsolete，不影响运行
5. **CORS**: 后端允许所有来源 (`allow_origins=["*"]`)，生产环境应限制

---

## 10. 扩展指南

### 添加新工作流类型

1. 在 `config/workflow_type_config.py` 的 `WORKFLOW_TYPE_CONFIG` 中添加新 entry
2. PathResolver 自动适配新目录结构
3. 如需列名映射，在 `_merge_excel()` 中添加条件分支

### 添加新步骤类型

1. 在 `WorkflowExecutor` 中添加 `_new_step()` 方法
2. 在 `execute_step()` 的 elif 链中注册
3. 在 `path_resolver.py` 的 `get_output_filename()` 中添加输出文件名映射
4. 在前端 `Workflows.vue` 中添加步骤类型的 UI 配置表单
5. 在 `workflows.py` 的 `execute_workflow_step()` 中确保数据传递正确
