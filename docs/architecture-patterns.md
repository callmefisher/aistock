# 架构模式与信号地图

> 最后验证版本：v0.0.6.19（2026-10-23）。本文件回答两个问题：**新需求该套用哪个现有模式**、**1~20 号表能提供哪五路信号**。修改相关代码时同步更新。

## 一、可复用模式清单（新需求先在这里选型）

### 1. 标准链工作流（事件表模式）

适用：新增一个"上传 Excel → 清洗 → 打标记 → 输出 N 号表"的表。
步骤链：`merge_excel → smart_dedup → extract_columns → match_high_price → match_ma20 → match_soe → match_sector`（质押额外加 `pledge_trend_analysis`）。
改动点集中在配置（见 `docs/table-registry.md` 维护纪律），executor 内置步骤零改动。

### 2. 加权评分框架（sector_signal 四件套）——做"评分/信号/方向判断"类需求的模板

| 文件 | 职责 |
|---|---|
| `backend/config/sector_signal_config.py` | 权重（`WEIGHTS_STRONG`/`WEIGHTS_REVERSAL`）、窗口、阈值，全部环境变量可调参 |
| `backend/services/sector_signal_service.py` | 排名→百分位分、硬门槛过滤、min-max 归一化、子分+总分计算 |
| `backend/models/sector_signal_model.py` | `sector_signal` 表：一天一行，JSON 列存全量分+Top30+权重快照 |
| `backend/api/sector_signal_api.py` | `GET /api/v1/sector-signal` + `POST /recompute` |

关键设计：权重快照随结果入 DB（可追溯当时用的什么参数）；评分=子分加权合成 + 硬门槛（不满足直接出局）。**前端页面尚未做**（无任何页面调用该 API）。做方向判断/组合评分时从这里抄结构。

### 3. 聚合工作流模式（读他表结果再加工）

适用：输出依赖其他表产物的新表（如 7/13/14/16/17/18/19 号表）。
三要素：`is_aggregation: True` + 单步 `allowed_steps` + 在 `backend/api/workflows.py` `_AGG_DEPENDENCY_ORDER`（~L935）登记执行优先级。
跨表读数通道：`workflow_result_service.py` 读 `workflow_results` 表（`step_type='final'`/`'final_ma20'`），不直接读别人目录下的 xlsx。

### 4. 跨表 AND/OR 组合过滤（condition_intersection）

适用：按多条件组合筛选股票池。
位置：`workflow_executor.py` `_condition_intersection`(L1962)/`_condition_intersection_parallel`(L2356)/`_apply_filters`(L3441)。
过滤列与默认条件配置化（`filter_columns`/`default_filters`），"百日新高并行20日均线"是 OR 特例；结果写 `stock_pools` 表。

### 5. 时序方向算法（pledge_trend）

适用：对任何"数量/占比随日期变化"的序列判断上行/下行。
位置：`backend/services/pledge_trend.py`，三种算法可选：`mann_kendall`（默认，Z/p 检验）/`monthly_downsample`（月末单调+反转阈值）/`linear_regression`（R² 阈值），小样本严格单调兜底。方向判断类需求直接复用。

### 6. 周报 35 天回溯模式（weekly_common）

适用：每周追加一个 sheet 而非重建文件。
位置：`backend/services/weekly_common.py`（`LOOKBACK_DAYS=35`）——拷贝 35 天内已有输出、追加编辑、损坏文件跳过。13/14/18/20 号表共用。

### 7. xlsx 第三方导入器兼容性标准化（_write_table20_package，20号表 Choice 兼容）

适用：工作流输出的 xlsx 要导入 Choice 等严格解析器（Excel/WPS 宽容，打开正常不代表规范）。
位置：`backend/services/weekly_mv1000_high.py` `_write_table20_package()`——**直接构建标准 xlsx 包**（不经 openpyxl 序列化，无需事后修补），styles/theme 部件用 `backend/config/table20_{styles,theme}_template.xml` 模板（提取自 Choice 实测可导入的 WPS 文件）。
为什么不能直接用 openpyxl 输出——openpyxl 3.1 原生输出 5 处不规范（曾致 Choice 导入失败，逐项实测确认）：
① 除 theme 外所有部件无 `<?xml?>` 声明；② `[Content_Types].xml` 排 zip 末条目（OPC 要求首条目）；
③ 字符串只写 inlineStr 且无 sharedStrings.xml（需 `t="s"` + 共享字符串表）；
④ worksheet 关系 Target 用包绝对路径 `/xl/...`（**Choice 按"基目录+Target"拼接解析，直接失败**，须相对路径）；
⑤ 空 `<workbookProtection/>`/`<definedNames/>` 元素。
新表输出若需第三方导入，复用 `_write_table20_package` 思路；排查此类问题：`unzip -l` + 逐部件 diff 对比"手动重存后正常"的文件。

## 二、新增 N 号表工作流 checklist（6 处必改点）

1. `backend/config/workflow_type_config.py`：注册类型（display_name/directories/naming/allowed_steps）
2. `backend/services/`：新建步骤实现（若新步骤）+ `workflow_executor.py` `execute_step()`（L791 起）加分发分支
3. `backend/api/workflows.py`：聚合类需登记 `_AGG_DEPENDENCY_ORDER`
4. `frontend/src/utils/quickUploadRules.js`：上传路由（`PREFIX_TO_TYPE` 数字前缀 / `SUBDIR_KEYWORDS` 关键字）
5. `frontend/src/views/Workflows.vue`：类型展示与说明 tooltip
6. `backend/tests/`：行为测试（周报类参照 `test_weekly_workflows.py`，1000+ 行，测试即规格）

另：`data/versions` 版本号 +1；更新 `docs/table-registry.md`。

## 三、五路信号分组（方向判断需求的数据底座）

1~20 号表按信号性质分五路（15 空洞、12 是数据源）：

| 路 | 表号 | 可提取的方向性信息 |
|---|---|---|
| 市场宽度/趋势 | 10、11、13、17 | 站上20日线占比、百日新高数量、周20日线新高数、月每日新增——时序，套 pledge_trend 算法 |
| 板块动能 | 8、16、19 | 板块涨跌幅排名时序（→ sector_signal 两榜）、AI 筛选按板块累计变化 |
| 大票健康度 | 14、18、20 | 千亿/800 亿市值周新高数量、39 日新高占比 |
| 事件/资本运作热度 | 1、2、3、4、6、9 | 并购重组/股权转让等事件数量时序（市场活跃度风向标） |
| 风险与池子 | 5、7、12 | 质押递增/递减计数、条件交集池大小变化、39 日新高名单 |

组合式方向判断的天然分层 = 五路各算子方向（归一化打分）→ 按 sector_signal 模式加权/规则合成总方向。
