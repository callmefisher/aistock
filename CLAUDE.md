# 选股池自动化系统

## 流程

设计 → 实施 → review → 测试 → `./deploy.sh build && ./deploy.sh restart`

- 需求不明确先澄清，不猜测编码
- \> 3 文件变更分解子任务
- Bug 修复遵循 TDD：写失败测试 → 修复 → 全部通过
- 代码尽量简洁，结果导向可验证
- 文件 <900 行、函数 <200 行；高频模块抽公共
- 前后端统一北京时区

## 命令

```bash
./deploy.sh build | restart | ps | logs [service]
cd backend && python -m pytest tests/ -v
cd frontend && npm test
```

| 服务   | 地址                        | 服务   | 地址    |
| ------ | --------------------------- | ------ | ------- |
| 前端   | http://localhost:7654       | MySQL  | :3306   |
| API    | http://localhost:8000/docs  | Redis  | :6379   |

## 架构

`Nginx(:7654) → Vue 3 SPA + /api/* → FastAPI(:8000) → MySQL/Redis/FileStorage`

关键文件：

- `backend/services/workflow_executor.py`：11 步骤类型（merge/dedup/match_*/condition_intersection）
- `backend/services/path_resolver.py`：按 workflow_type 动态路径
- `backend/config/workflow_type_config.py`：7 类型 + 条件交集定义
- `backend/utils/beijing_time.py`：北京时区工具
- `frontend/src/views/Workflows.vue`：核心页面（含 `todayBeijing()`）
- `frontend/src/utils/quickUploadRules.js`：前缀匹配规则

## 工作流

| 类型   | 上传目录                      | 公共目录                      |
| ------ | ------------------------- | ------------------------- |
| 并购重组 | `data/excel/{date}/`      | `data/excel/2025public/`  |
| 股权转让 | `data/excel/股权转让/{date}/` | `data/excel/股权转让/public/` |

标准步骤链：`merge_excel → smart_dedup → extract_columns → match_high_price → match_ma20 → match_soe → match_sector`

**条件交集**（聚合类，读其他工作流 DB 结果）：仅 `condition_intersection` 一步；过滤百日新高/20日均线/国企/一级板块（全局 AND/OR）；输出双 Sheet，Sheet2 交集选股池写 `stock_pools` 表。**唯一性约束**：同 `workflow_type + date_str` 全局只允许一个。

**关键逻辑**：`merge_excel` 公共文件 skiprows=1、非公共文件动态查找序号=1行；`smart_dedup` 按日期降序 + 按证券代码 keep=first，过滤 .NQ；股权转让列映射 代码→证券代码/名称→证券简称/公告日期→最新公告日；`normalize_stock_code()` + `match_stock_code_flexible()` 跨格式匹配；JWT HS256 7天过期；`.env` 必需 MYSQL_*/SECRET_KEY，可选 OPENAI_API_KEY/SMTP_*。

## 数据目录

```
data/excel/
  2025public/  百日新高/  20日均线/  国企/  一级板块/
  {date}/                    # 日上传 + 步骤输出
  股权转让/public/  股权转让/{date}/
```
