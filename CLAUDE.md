# 选股池自动化系统

## 流程

设计 → 实施 → review → 测试 → `./deploy.sh build && ./deploy.sh restart`

- 需求不明确先澄清，不猜测编码
- >3 文件变更分解子任务
- Bug 修复遵循 TDD：写失败测试 → 修复 → 全部通过
- 用户纠正后在「经验教训」追加规则
- 文件 <900 行、函数 <200 行；高频模块抽公共
- 前后端统一北京时区

## 经验教训

1. **Excel 双行表头**（第1行分组头、第2行实际列名）：`_merge_excel` 动态查找"序号=1"所在行，检测前一行是否含已知列名（证券代码/证券简称/最新公告日等）再决定是否重映射；子列名重复必须去重（追加 `_1` 后缀），否则 `pd.concat` Reindex 报错。禁止硬编码 iloc。
2. **Mann-Kendall 小样本兜底**：n=4 严格单调时 p≈0.089 会漏判。`_detect_trend_mk` 在 3≤n<10 且 diffs 全同向时直接判 up/down。
3. **质押数据源**：东方财富 `datacenter-web/api/data/v1/get?reportName=RPTA_APP_ACCUMDETAILS&filter=(SECURITY_CODE="xxx")` 单股 0.18s 拉全量（含 `ACCUM_PLEDGE_TSR`）。AkShare `stock_gpzy_pledge_ratio_detail_em` 仅作降级（拉全市场 3.5min，缺 ACCUM 字段）。
4. **质押输出样式一次性施加**：红绿标色只在 `_finalize_pledge_output` 里做——中间 `to_excel` 会清样式。finalize 由 `api/workflows.py::run_workflow` 末尾 `executor.finalize_pledge_if_needed(...)` 统一触发，`_match_sector` / `_pledge_trend_analysis` **不再**调用 `_sync_pledge_final_to_public`（避免双写）。
5. **质押来源识别**：文件名前缀优先（`中大盘{date}.xlsx` / `小盘{date}.xlsx`），sheet 名前缀兜底。用 `startswith` 而非 `in`（`2026小盘汇总.xlsx` 不应误判）。`_derive_pledge_source(file_name, sheet_name)` 两参数必须都接。
6. **质押绿标基准** `_load_pledge_baseline(public_dir)`：合并 `/质押/public/` 所有 xlsx（遍历每 sheet 抽 `证券代码` + `最新公告日`/`股权质押公告日期*`）+ `stock_pools` 表 `is_active=True` 的 `data` JSON。只看 `证券代码` 键，新行日期 > baseline 或 code 未见过 → 绿标。
7. **百日新高行数统计** `count_high_price_rows`：源文件末行水印（"数据来源于..."）会误计入，必须按 `^\d{6}(\.[A-Za-z]{2,4})?$` 过滤。列名兼容"证券代码/股票代码/代码"（归一后比对）。
8. **快捷批量上传前缀匹配** `resolveTarget(filename)`：优先级"8+含涨跌幅例外 > 子目录关键字 > 严格单数字前缀"。严格单数字 = 首字符数字且第二字符非数字（`1adbd.xlsx`→并购重组；`11xxx.xlsx`/`88xxx.xlsx`→未匹配）。例外：`8、板块涨跌幅排名.xlsx` 按涨幅排名处理。含百日新高/20日均线/国央企/板块的文件（除例外外）归并购重组子目录。不影响后端 `is_public_file`（按路径判）。`POST /workflows/upload-step-file/` 的 `workflow_id` 允许 0。
9. **批量同步日期** `PUT /workflows/bulk-set-date`：同时更新 `Workflow.date_str` 和每 step `config.date_str`（后者必须 `copy.deepcopy` 构 `new_steps` 后整体赋值，否则 SQLAlchemy JSON in-place 失效）。
10. **FastAPI 路由顺序**：literal-path（如 `/bulk-set-date`）必须注册在 `/{workflow_id}` 之前，否则被当 int 解析 422。
11. **时区策略**（容器 UTC，**不要改 docker TZ**）：
    - 生成今日 `date_str`：前端用 `todayBeijing()` / `new Date().toLocaleDateString('sv-SE', {timeZone:'Asia/Shanghai'})`；后端用 `utils.beijing_time.beijing_today_str()`。禁用 `toISOString()` 和 `datetime.now().strftime('%Y-%m-%d')`。
    - 时间戳字段（`created_at`/`last_run_time` 等）：保持 `datetime.now()` 写入 UTC，前端 `formatBeijingTime(s)` 依赖"字符串 +Z 当 UTC +8 显示"假设，改写会双偏移到未来 16h。
    - `formatBeijingTime` 输出格式 `YYYY-MM-DD HH:mm:ss` 不得改。

## 命令

```bash
./deploy.sh build | restart | ps | logs [service]
cd backend && python -m pytest tests/ -v
cd frontend && npm test
```

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:7654 |
| API  | http://localhost:8000/docs |
| MySQL | :3306  |  Redis | :6379 |

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

| 类型 | 上传目录 | 公共目录 |
|------|---------|---------|
| 并购重组 | `data/excel/{date}/` | `data/excel/2025public/` |
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
