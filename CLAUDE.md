# 选股池自动化系统

> 最后验证版本：v0.0.6.20（2026-10-26）。本文件是 AI 会话的**唯一入口**，过期即误导。
> **维护纪律**：改 workflow 相关代码的 commit 必须同步更新本文件 + `docs/table-registry.md` + `docs/architecture-patterns.md`，并更新头部验证版本。

## 流程

设计 → 实施 → review → 测试 → `./deploy.sh smart-build && ./deploy.sh restart`

- 需求不明确先澄清，不猜测编码
- \> 3 文件变更分解子任务
- Bug 修复遵循 TDD：写失败测试 → 修复 → 全部通过
- 代码尽量简洁，结果导向可验证
- 文件 <900 行、函数 <200 行；高频模块抽公共
- 前后端统一北京时区

## 命令

```bash
./deploy.sh build | restart | smart-build | ps | logs [service]
cd backend && python -m pytest tests/ -v
cd frontend && npm test
docker exec stock_backend python /app/test_xxx.py  # 容器内跑后端 API 测试脚本（backend/test_xxx.py）
docker exec stock_backend tail -f /app/logs/app.log  # 后端日志排查
```

部署必须走 deploy.sh（smart-build 内容指纹、前后端分侧构建）；**禁止** `docker-compose up -d --no-deps`（只启旧容器，不重建镜像）。

| 服务 | 地址 | 服务 | 地址 |
| --- | --- | --- | --- |
| 前端 | http://localhost:7654 | MySQL | :3306 |
| API | http://localhost:8000/docs | Redis | :6379 |

API 文档直接用 FastAPI 自带的 `/docs`（实时准确），不要手写 API 文档。

## 架构

`Nginx(:7654) → Vue 3 SPA + /api/* → FastAPI(:8000) → MySQL/Redis/FileStorage(data/excel/)`

- `backend/services/workflow_executor.py`：步骤引擎，`execute_step()`（L791 起）分发 21 种步骤类型
- `backend/config/workflow_type_config.py`：20+ workflow_type 总注册表（表号→类型→目录→命名的权威源）
- `backend/services/path_resolver.py`：按 workflow_type 动态路径
- `backend/api/workflows.py`：工作流全部端点 + `_AGG_DEPENDENCY_ORDER`（L935）批量执行依赖链
- `backend/services/workflow_result_service.py`：结果落库 `workflow_results`（聚合表跨表读数通道）
- `frontend/src/views/Workflows.vue`：核心页面；`frontend/src/utils/quickUploadRules.js`：上传路由

## 1~20 号表速查（详情见 docs/table-registry.md）

| 号 | 名称 | 号 | 名称 |
| --- | --- | --- | --- |
| 1 | 并购重组 | 11 | 百日新高趋势图 |
| 2 | 股权转让 | 12 | 39日新高（**纯上传数据源**，无工作流） |
| 3 | 增发实现 | 13 | 占20日线无振幅（周报） |
| 4 | 申报并购重组 | 14 | 千亿市值周新高（周报） |
| 5 | 质押（含趋势预判列） | 15 | **编号空洞，不存在** |
| 6 | 减持叠加质押和大宗交易 | 16 | AI筛选汇总（月报） |
| 7 | 条件交集（聚合，写 stock_pools） | 17 | 当月每日新增（月报，双sheet双落库） |
| 8 | 涨幅排名（上传源，板块信号数据源） | 18 | 全部A股800亿（周报） |
| 9 | 招投标 | 19 | AI筛选20日线汇总（月报） |
| 10 | 站上20日均线趋势 | 20 | 千亿新高A列（**14 的附带输出**，固定文件名） |

标准链：`merge_excel → smart_dedup → extract_columns → match_high_price → match_ma20 → match_soe → match_sector`。

## 需求路由表（要做 X → 先读 Y）

| 需求类型 | 先读 |
| --- | --- |
| 新增/修改 N 号表工作流 | `workflow_type_config.py` + `docs/architecture-patterns.md` 第二节 checklist（6 处必改点） |
| 跨表聚合/读取他表结果 | `workflow_result_service.py` + `_AGG_DEPENDENCY_ORDER` + `condition_intersection`（executor L1962/L2356/L3441） |
| 评分/信号/方向判断类 | `sector_signal` 四件套模板（`docs/architecture-patterns.md` 第一节-2）+ `pledge_trend.py` 时序算法 |
| 上传路由/快捷上传 | `frontend/src/utils/quickUploadRules.js` + `components/QuickUploadDialog.vue` |
| 前端工作流页面 | `frontend/src/views/Workflows.vue`（含各号表说明 tooltip） |

## 按需深读索引

| 文档 | 何时读 |
| --- | --- |
| `docs/table-registry.md` | 涉及任何表号：输出路径/字段结构/数据流向/聚合顺序 |
| `docs/architecture-patterns.md` | 新需求选模式、新增表 checklist、方向判断五路信号分组 |
| `README.md` | 部署与使用（面向人） |
| `docs/研报模版.md` | AI 个股研报 prompt 模板（工作资产，与编号表无关） |

## 探索纪律（重要，省 token）

1. **先读本文件**（自动加载）→ 按需求路由表定向 Read/Grep 2~3 个文件
2. 仍有缺口才派 **1 个 medium 范围** Explore 代理，问题要窄
3. **禁止**一上来派 very thorough 代理全库扫（单次约百万级 token）
4. 提需求时点名表号（"基于 8/16/19 号表做板块方向"），可省一轮澄清+探索

## 关键逻辑

- `merge_excel`：公共文件 skiprows=1、非公共文件动态查找序号=1 行；**通用列名去重（保留首个，v0.0.6.20）**——单文件重复列（Wind 导出同名列 pandas mangle `.1`；6 号表剥离 `\n` 后同名；5 号表质押比例规整同名）会使 `merged_df[col]` 返回 DataFrame，`.dtype` 崩溃，去重位置在两个 `dfs.append` 前（executor L1094/L1053）；`smart_dedup`：按日期降序 + 证券代码 keep=first，过滤 .NQ；列映射在 `extract_columns`（如股权转让 代码→证券代码/公告日期→最新公告日）
- 跨格式匹配：`normalize_stock_code()` + `match_stock_code_flexible()`（`backend/utils/stock_code_normalizer.py`）
- 条件交集：过滤列 百日新高/20日均线/国企/一级板块，全局 AND/OR；同 `workflow_type + date_str` 唯一
- 周报 13/14/18/20：`weekly_common.py` 35 天回溯拷贝编辑（`LOOKBACK_DAYS=35`）
- JWT HS256 7 天过期；`.env` 必需 MYSQL_*/SECRET_KEY，可选 OPENAI_API_KEY/SMTP_*

## 数据目录

```
data/excel/
  2025public/ 百日新高/ 20日均线/ 国企/ 一级板块/   # 公共匹配源（match_* 步骤读取）
  {date}/                      # 日上传 + 1号表输出 + 周报输出子目录（13/14/18/20 各自 *输出/）
  {YYYY-MM}/                   # 16号表
  股权转让|增发实现|申报并购重组|质押|减持…|招投标/{date}/  # 各事件表
  条件交集/{date}/  涨幅排名/{date}/public/  当月每日新增/{YYYY年M月新增}/  本月AI筛选20日线汇总/{YYYY-MM}/
```
