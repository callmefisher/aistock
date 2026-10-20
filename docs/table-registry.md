# 表号注册表（1~20 号表权威对照）

> 最后验证版本：v0.0.6.10（2026-10-20）。权威源：`backend/config/workflow_type_config.py`（类型/命名/目录）、`frontend/src/utils/quickUploadRules.js`（上传路由）。
> **维护纪律**：新增/修改 workflow_type 的 commit 必须同步更新本文件。

## 总览

| 号 | 名称 | workflow_type | 类别 | 核心步骤 | 实现文件 |
|---|---|---|---|---|---|
| 1 | 并购重组 | `并购重组`（空串 `""` 等价，见 `get_type_config` 兜底） | 事件 | 标准链 | executor 内置 |
| 2 | 股权转让 | `股权转让` | 事件 | 标准链 | executor 内置 |
| 3 | 增发实现 | `增发实现` | 事件 | 标准链 | executor 内置 |
| 4 | 申报并购重组 | `申报并购重组` | 事件 | 标准链 | executor 内置 |
| 5 | 质押 | `质押` | 事件+风险 | 标准链 + `pledge_trend_analysis` | executor + `pledge_trend.py` |
| 6 | 减持叠加质押和大宗交易 | `减持叠加质押和大宗交易` | 事件 | 标准链 | executor 内置 |
| 7 | 条件交集 | `条件交集` | 聚合 | `condition_intersection` | executor L1962/L2356 |
| 8 | 涨幅排名 | `涨幅排名` | 上传源 | `merge_excel` + `ranking_sort` | executor 内置 |
| 9 | 招投标 | `招投标` | 事件 | 标准链 | executor 内置 |
| 10 | 站上20日均线趋势 | `导出20日均线趋势` | 趋势 | `export_ma20_trend` | executor 内置 |
| 11 | 百日新高趋势图 | `百日新高总趋势` | 趋势 | `export_high_price_trend` | executor 内置 |
| 12 | 39日新高 | **无工作流，纯上传数据源** | 数据源 | — | 被 7/18 号表读取 |
| 13 | 占20日线无振幅 | `本周20日线新高` | 周报 | `weekly_ma20_close_high` | `weekly_ma20_close_high.py` |
| 14 | 千亿市值周新高 | `本周总市值千亿新高` | 周报 | `weekly_mv1000_high` | `weekly_mv1000_high.py` |
| 15 | — | **编号空洞，不存在** | — | — | — |
| 16 | AI筛选汇总 | `本月AI筛选汇总` | 月报 | `monthly_ai_summary` | `monthly_ai_summary.py` |
| 17 | 当月每日新增 | `当月每日新增` | 月报 | `monthly_daily_new` | executor 内置 |
| 18 | 全部A股800亿 | `全部A股总市值大于800亿` | 周报 | `all_a_800` | `all_a_800.py` |
| 19 | AI筛选20日线汇总 | `本月AI筛选20日线汇总` | 月报 | `monthly_ai_ma20_summary` | `monthly_ai_ma20_summary.py` |
| 20 | 千亿新高A列 | （14 号表附带输出，无独立类型） | 附带 | `weekly_mv1000_high` 末段 | `weekly_mv1000_high.py` |

标准链 = `merge_excel → smart_dedup → extract_columns → match_high_price → match_ma20 → match_soe → match_sector`。每步中间产物：`total_1.xlsx` → `deduped.xlsx` → `output_2.xlsx` → `output_3/4/5.xlsx`，最终文件覆盖 `output_template` 命名。

## 输出位置速查

| 号 | 输出路径（相对 `data/excel/`） | 文件名模板 |
|---|---|---|
| 1 | `{date}/` | `1并购重组{date}.xlsx` |
| 2 | `股权转让/{date}/` | `2股权转让{date}.xlsx` |
| 3 | `增发实现/{date}/` | `3增发实现{date}.xlsx` |
| 4 | `申报并购重组/{date}/` | `4申报并购重组{date}.xlsx` |
| 5 | `质押/{date}/` | `5质押{date}.xlsx` |
| 6 | `减持叠加质押和大宗交易/{date}/` | `6减持叠加质押和大宗交易{date}.xlsx` |
| 7 | `条件交集/{date}/` | `7条件交集{date}.xlsx` + `…百日新高证券代码.xlsx` + `…站上20日线证券代码.xlsx` |
| 8 | `涨幅排名/{date}/public/`（上传即源，无输出） | 上传名 `8、板块涨跌幅排名{mmdd}.xlsx` |
| 9 | `招投标/{date}/` | `9招投标{date}.xlsx` |
| 10 | `导出20日均线趋势/{date}/` | `10站上20日均线趋势{date}.xlsx` |
| 11 | `百日新高总趋势/{date}/` | `11百日新高趋势图{date}.xlsx` |
| 12 | `{date}/39日新高/`（上传） | 例 `12 39日新高0831.xlsx` |
| 13 | `{date}/本周20日收盘价新高输出/` | `13 占20日线无振幅{mmdd}.xlsx` |
| 14 | `{date}/本周总市值千亿新高输出/` | `14 总市值大于1000亿 本周最高价格大于上周最高价格{mmdd}.xlsx` |
| 16 | `{YYYY-MM}/` | `16 {m}月AI筛选汇总{mmdd}.xlsx`（月份不补零、MMDD 补零） |
| 17 | `当月每日新增/{YYYY年M月新增}/` | `17 {m}月新增{mmdd}.xlsx` |
| 18 | `{date}/全部A股800亿输出/` | `18 全部A股总市值大于800亿{mmdd}.xlsx` |
| 19 | `本月AI筛选20日线汇总/{YYYY-MM}/` | `19 {m}月AI筛选20日线汇总{mmdd}.xlsx` |
| 20 | `{date}/20号表本周总市值千亿新高A列/` | `20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx`（**固定名**） |

## 结构要点与数据流向

**事件表（1/2/3/4/6/9）**：列 = 证券代码/证券简称/最新公告日 + 四个 match 标记列（百日新高/站上20日线/国央企/所属板块）。源列映射各不相同（如股权转让：代码→证券代码、公告日期→最新公告日）。

**5 质押**：双 sheet（中大盘/小盘）；前 7 列同事件表 + 按日质押比例列（红绿着色）+ `持续递增（一年内）/持续递减（一年内）/质押异动` 预判列（算法见 `pledge_trend.py`）。

**7 条件交集**：读全部事件表当日 `workflow_results(step_type='final')`，按 `filter_columns`（百日新高/20日均线/国企/一级板块）非空 AND/OR 过滤（"百日新高并行20日均线"= OR 特例），按 `default_type_order` 合并去重，`资本运作行为` 顿号拼接（质押细分中大盘/小盘）。双 sheet；Sheet2 交集写 `stock_pools` 表。**唯一性约束**：同 `workflow_type + date_str` 全局一个。

**8 涨幅排名**：板块名称/今日涨跌幅/月初涨跌幅/年初涨跌幅 + 逐日列 + 升序排序结果列 + `迄今为止排进前5(次数)`。是 `sector_signal_service.py`（板块信号两榜）唯一数据源。

**10/11 趋势**：日期/数量/占比 折线图（xlsxwriter 出图）。

**12 39日新高**：仅"股票代码/证券代码"列被读取：→ 7 号表"39日新高"标记列、18 号表 `"{M}/{D}
39日新高"` 列。

**13/14/18/20 周报**：`weekly_common.py` 35 天回溯——拷贝 35 天内已有输出编辑而非重生成。14 号表 Sheet1"筛选结果"不动 + 逐周追加 MMDD sheet；20 号表 = 当日 MMDD sheet 的 A 列拷贝（代码降序，固定文件名）。

**17 当月每日新增**：单文件双 sheet："当月每日新增"（百日新高 J 列新增，落库 `step_type='final'`）/"20日线"（K 列新增，落库 `final_ma20`；当前 `EXPORT_MDN_MA20_SHEET=False` 屏蔽导出但 DB 仍写）。

**16/19 AI筛选汇总**：结构同（参数化复用）：Sheet1 一级/二级板块 × 日期累计双表 + 彩色折线图；后续 MMDD sheet（证券代码+板块，降序）。数据链：17 号表 final → 16 号表；17 号表 final_ma20 → 19 号表（DB 优先读取）。

**聚合执行顺序**（`backend/api/workflows.py` `_AGG_DEPENDENCY_ORDER`，批量一键执行时严格串行）：
条件交集(0) → 当月每日新增(1) → 本月AI筛选汇总(2) → 本月AI筛选20日线汇总(3) → 本周20日线新高(4) → 本周总市值千亿新高(5) → 全部A股总市值大于800亿(6)；未登记的聚合类型（导出20日均线趋势/百日新高总趋势）最后执行。

**落库**：`workflow_results` 表（唯一键 `workflow_id+date_str+step_type`），字段含 `row_count/columns_json/data_compressed(zlib)/preview_json(前50行)`；普通表存 `final`，17 号表另存 `final_ma20`。读取通道：`workflow_result_service.py`。
