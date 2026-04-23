# 百日新高总趋势 — 设计文档

> 创建于 2026-04-23

## 背景

现有"导出20日均线趋势"工作流 + 统计分析"站上20日均线趋势" tab 已稳定运行。用户希望新增一个结构完全对称的"百日新高总趋势"通道：
- 工作流类型统计每日 `data/excel/{date}/百日新高/` 的有效股票代码行数，随时间绘制折线图。
- 统计分析开辟同名 tab，支持查看/手录/Excel 导入/导出，数据格式与工作流完全一致。
- 一键执行时排在所有其他工作流之后。

横坐标为日期，纵坐标为**数量**（不再是比例）。

## 范围

- 新增工作流类型 `百日新高总趋势`，单步骤 `export_high_price_trend`。
- 新增 `trend_statistics` metric_type `high_price`，workflow_type 固定 `百日新高总趋势`。
- 新增 `trend_service.count_high_price_rows`、复用 `parse_excel_for_trend`/`export_trend_excel_with_chart`（加 metric_type 分支）。
- 前端 `Workflows.vue` 新增类型与步骤 UI；`Statistics.vue` 新增第 4 个 tab。
- 导出文件名统一 `11百日新高趋势图{date}.xlsx`。

## 架构

```
Workflows.vue              Statistics.vue
   │                           │
   │ POST /workflows/{id}/run  │ GET /statistics/trend/trend-data  (metric=high_price)
   │                           │ POST /statistics/trend/trend-data (手录)
   │                           │ POST /statistics/trend/trend-data/upload (导入 Excel)
   │                           │ GET /statistics/trend/trend-data/export
   ↓                           ↓
WorkflowExecutor          trend_api.py
   _export_high_price_trend      │
      │                          │
      ├── count_high_price_rows ─┤
      ├── save_trend_data        │
      ├── get_trend_data        ─┤
      └── export_trend_excel_with_chart(metric_type='high_price')
                                  │
                                  ↓
                         trend_statistics 表
```

## 组件

### 后端

**1. `backend/config/workflow_type_config.py`**

新增：

```python
"百日新高总趋势": {
    "display_name": "百日新高总趋势",
    "base_subdir": "百日新高总趋势",
    "is_aggregation": True,
    "is_export_only": True,
    "directories": {
        "upload_date": "百日新高总趋势/{date}",
        "public": "",
    },
    "naming": {
        "output_template": "11百日新高趋势图{date}.xlsx",
    },
    "match_sources": {},
    "allowed_steps": ["export_high_price_trend"],
},
```

**2. `backend/services/trend_service.py`**

- 新增 `count_high_price_rows(base_dir: str, date_str: str) -> int`
  - 读 `{base_dir}/{date_str}/百日新高/*.xlsx`
  - 遍历每个 xlsx 的每个可见 sheet；在第 1 行查找含 `证券代码 | 股票代码 | 代码` (归一后: `replace('\n','').replace(' ','').strip().lower()` 等价比对) 的列 index
  - 抽出该列所有非空单元格 (str 转后 strip 非空)，加入全局 set
  - return len(set)
  - 识别失败的 sheet log warning 跳过；整目录无 xlsx 或全部识别失败 → return 0

- `parse_excel_for_trend(file_path, workflow_type, metric_type='ma20')`
  - 加一个可选参数 `metric_type`；保持原 `workflow_type` 签名（ma20 路径不破坏）
  - 当 `metric_type == 'high_price'`:
    - 归一列名：`日期|date|数据日期` → `日期`；`数量|count|行数|站上百日新高数量|百日新高数量` → `数量`
    - 必须同时存在 `日期` 和 `数量` 列
    - 按行遍历：日期空/数量空/数量 NaN 跳过；parse date 支持 Excel 序列号(30000~60000)、`M月D日`就近归因、通用 `pd.to_datetime`
    - emit `{workflow_type: '百日新高总趋势', date_str, count, total: 0, ratio: 0}`
  - 否则走原 ma20 逻辑不变

- `export_trend_excel_with_chart(data, file_path, single_type=None, metric_type='ma20')`
  - 加可选 `metric_type` 参数
  - `metric_type == 'high_price'` 分支：
    - sheet 名 `百日新高总趋势`
    - 单类型、单系列（不走 type_groups 多块、不走质押并排、不走年度并排）
    - 表格标题 `【11百日新高总趋势】`
    - 表头 `日期 | 数量 | 完整日期`
    - chart 颜色 `#67C23A`（区别于 ma20 的 `#409EFF`）
    - Y 轴名 `数量`，`num_format='0'`
    - X 轴间隔抽稀逻辑完全复用（>15 点 → `interval_unit = n // 15`，字体 9 rotation -45）
    - chart 标题 `11百日新高总趋势`
  - 抽公共内部函数 `_render_single_line_block(wb, ws, items, sheet_name, table_title, chart_title, y_axis_name, y_num_format, color, headers, start_row)` 给 ma20 的普通类型和 high_price 共用。质押并排、年度并排保持原 block 函数不动（结构差异大）。

**3. `backend/services/workflow_executor.py`**

- 在 `execute_step` 的 step type 分发 (`elif step_type == "export_ma20_trend":` 之后) 加：
  ```python
  elif step_type == "export_high_price_trend":
      return await self._export_high_price_trend(step_config, date_str)
  ```

- 新增方法 `async def _export_high_price_trend(self, config: Dict, date_str: Optional[str])`:
  1. 解析 preset/range (复用 ma20 的逻辑：`date_preset`, `date_range_start`, `date_range_end`；非 custom 时以 date_str 为锚点重算)
  2. `count = count_high_price_rows(self.base_dir, date_str)`
  3. `if count > 0: await save_trend_data('high_price', '百日新高总趋势', date_str, count, total=0, source='auto')`
  4. `data = await get_trend_data(metric_type='high_price', start_date=..., end_date=...)`
  5. `output_filename = config.get("output_filename") or f"11百日新高趋势图{date_str}.xlsx"`
  6. `output_dir = self._get_daily_dir_for_type(date_str, '百日新高总趋势')` —— 使用 type_config 的 directories.upload_date 解析到 `{base}/百日新高总趋势/{date}/`（若没有现成 helper 则直接拼 `os.path.join(self.base_dir, '百日新高总趋势', date_str)`）
  7. `export_trend_excel_with_chart(data, output_path, metric_type='high_price')`
  8. 返回 `{success, message, data: data[:100], rows: len(data), file_path}`

- `save_trend_data` 目前的 ratio 计算 `round(count/total, 4) if total > 0 else 0.0` 对 total=0 是安全的（返回 0.0），不需改动。

**4. `backend/api/trend_api.py`**

- `TrendDataInput.metric_type` 默认保持 `'ma20'`；前端传 `'high_price'` 即可。
- `BatchInput.metric_type` 同上。
- `upload_trend_excel` 的 `parse_excel_for_trend(tmp_path, workflow_type)` 改为 `parse_excel_for_trend(tmp_path, workflow_type, metric_type=metric_type)`；Form 新增 `metric_type: str = Form('ma20')`。
- `export_trend_data`：当 `metric_type == 'high_price'`，filename 改为 `f"11百日新高趋势图{end_date or '--'}.xlsx"`；调用 `export_trend_excel_with_chart(data, file_path, metric_type=metric_type)`。

**5. `backend/services/trend_service.py::get_trend_data`**

- 现有 `WHERE metric_type = :metric_type AND workflow_type NOT IN ('条件交集', '导出20日均线趋势')` 不需改动，因 metric_type 过滤已足够隔离 ma20 vs high_price。

### 前端

**6. `frontend/src/views/Workflows.vue`**

- `AGGREGATION_TYPES` 加 `'百日新高总趋势'`（使其跟 `'导出20日均线趋势'` 一样被 `["条件交集", "导出20日均线趋势", "百日新高总趋势"]` 识别为聚合类，执行前检查数据可用性的旧逻辑若依赖此数组须包括在内）。
- 工作流类型下拉 `<el-option>` 加新项。
- 步骤 type 映射加 `export_high_price_trend: 'warning'` 和 `'导出百日新高趋势Excel'`。
- 工作流 type watch/init 分支：`else if (newType === '百日新高总趋势')` → 初始化单步骤 `{type: 'export_high_price_trend', config: {date_preset: '1m', date_range_start, date_range_end}}`（与 ma20 骨架一致）。
- 步骤展示区加 `v-if="step.type === 'export_high_price_trend'"` 分支，UI 跟 `export_ma20_trend` 完全一致（日期 preset + custom range 选择）。
- 保存前重算 preset 范围的逻辑对 `export_high_price_trend` 也生效（加一行 `|| step.type === 'export_high_price_trend'`）。

**7. `frontend/src/views/Statistics.vue`**

- 新增 tab `<el-tab-pane label="百日新高总趋势" name="high_price_trend">`，放在 "站上20日均线趋势" tab 后、"板块涨幅分析" tab 前。
- 结构克隆 ma20 tab 但单一化：
  - 顶部工具条：日期区间快捷（本月/上月/本年）+ 自定义 range + 「导出」按钮（无双Y轴开关）
  - 图表区：单张 ECharts 卡片，标题 "11百日新高总趋势"，单系列绿线 #67C23A，Y 轴为整数数量，X 轴日期
  - 数据管理：
    - 手动录入：仅 `日期` + `数量` 两字段
    - Excel 上传：workflow_type 常量 `'百日新高总趋势'`，无子类型选项；提示文案 "两列格式：日期 + 数量"
    - 预览表：列 `日期 / 数量`（无总量/占比）
  - 已录入数据表：列 `日期 / 数量 / 来源 / 操作`（无总量、占比列）
- 所有 API 请求都传 `metric_type: 'high_price'`。
- 导出按钮下载 `/statistics/trend/trend-data/export?metric_type=high_price&start_date=...&end_date=...`，下载文件名 `11百日新高趋势图{end}.xlsx`（前端 hint，实际以后端 Content-Disposition 为准）。

## 数据流

### 工作流执行（一次）

1. 用户在 Workflows 页选 `百日新高总趋势` + `date_str`，点击执行。
2. `_export_high_price_trend` 被调用：
   - 扫 `data/excel/{date}/百日新高/*.xlsx` → `count`
   - 若 count>0：写 trend_statistics (ON DUPLICATE KEY UPDATE → 幂等)
   - 按 preset/range 拉历史
   - 走 `export_trend_excel_with_chart(metric_type='high_price')` 生成 `data/excel/百日新高总趋势/{date}/11百日新高趋势图{date}.xlsx`
3. 前端下载该文件。

### 统计分析

- 打开 tab → `GET /statistics/trend/trend-data?metric_type=high_price&start_date=...&end_date=...` → ECharts 渲图。
- 手录一条 → `POST /statistics/trend/trend-data` (metric_type=high_price, workflow_type='百日新高总趋势')。
- 导入 Excel → `POST /statistics/trend/trend-data/upload` with `metric_type=high_price, workflow_type='百日新高总趋势', file=...` → 后端 `parse_excel_for_trend(...,metric_type='high_price')` 预览 → 用户确认 → `POST /statistics/trend/trend-data/batch`。
- 导出 → `GET /statistics/trend/trend-data/export?metric_type=high_price&...` → `export_trend_excel_with_chart(metric_type='high_price')`。

### 列名识别核心（`count_high_price_rows`）

```python
CODE_KEYS = {'证券代码', '股票代码', '代码'}
def _norm(s): return str(s).replace('\n','').replace(' ','').strip().lower()
NORM_KEYS = {_norm(k) for k in CODE_KEYS}

def find_code_column(header_row):
    for idx, cell in enumerate(header_row):
        if cell is None: continue
        if _norm(cell) in NORM_KEYS:
            return idx
    return None
```

sheet 无代码列 → warning，跳过此 sheet；文件打不开 → warning，跳过此文件；目录不存在 → 返回 0。

## 错误处理

- **源目录不存在** → count=0，不入库，继续按历史出图；日志 `[百日新高总趋势] 目录不存在 {path}`。
- **DB 写入失败** → `save_trend_data` 返 False，log error，仍继续出图。
- **`get_trend_data` 返空** → `export_trend_excel_with_chart` 写 "暂无数据" 占位单元格（已有兜底）。
- **count=0** → 不入库，图只反映已有历史；日志 `[百日新高总趋势] {date} count=0 已跳过入库`。
- **文件打开失败** → openpyxl 异常被捕获，文件跳过，计数不中断。

## 幂等性

- 同 `(metric_type, workflow_type, date_str)` 重复执行 → `ON DUPLICATE KEY UPDATE` 覆盖 count。
- 同目录输出 xlsx 被覆盖写。

## 测试计划

### 单元测试（pytest，`backend/tests/`）

**test_count_high_price_rows.py**

- `test_标准列_证券代码`：5 行单列 → 5
- `test_列名_股票代码`：等价识别
- `test_列名_代码`：等价识别（带换行/空白）
- `test_多文件去重`：两文件含相同代码 → 算 1
- `test_多sheet`：同一文件两 sheet 不同代码 → 并集计数
- `test_空目录`：return 0 不 raise
- `test_无代码列`：warning + return 0
- `test_实测文件`：`data/excel/2026-04-22/百日新高/百日新高0422.xlsx` 验证实际 count 数字（预期 287，作为实际期望值固化）

**test_parse_excel_for_trend_high_price.py**

- `test_两列标准格式`：日期(序列号) + 数量 → 正确 N 条
- `test_空数量行跳过`：None/NaN 行不出现
- `test_日期字符串`：`M月D日` 归因
- `test_11_0422样例`：`/Users/xiayanji/Desktop/11_0422.xlsx` → 排除 5 个空行后的条数（25 行 - 1 表头 - 5 空 = 19）

**test_export_trend_excel_high_price.py**

- `test_high_price_分支`：5 条数据 → 输出文件存在，sheet 名 `百日新高总趋势`，表头 `日期/数量/完整日期`，单 chart
- `test_空数据`：空 list → "暂无数据"
- `test_X轴间隔`：20 条 → `interval_unit` 被设

**test_export_high_price_trend_step.py**

- Mock `count_high_price_rows`→287、`save_trend_data`、`get_trend_data`→5 条
- 断言返回 `{success: True, file_path: '.../百日新高总趋势/{date}/11百日新高趋势图{date}.xlsx'}`
- `count=0` 时不调 `save_trend_data` 仍出图

**test_workflow_type_config_new.py**

- `get_type_config('百日新高总趋势')` 字段正确
- `get_available_types()` 含新类型

### 手工验收

1. `./deploy.sh build && ./deploy.sh restart`
2. Workflows 页 → 创建 `百日新高总趋势` + `2026-04-22` → 执行 → 下载 → Excel 打开：
   - 表头 `日期 / 数量 / 完整日期`，单绿线，Y 轴整数，最后一行 count=287
3. Statistics 页 → 新 tab → 查看（至少 1 条自动写入的记录）→ 手录 2026-04-21=280 → 保存 → 图更新 → 上传 `/Users/xiayanji/Desktop/11_0422.xlsx` → 预览 → 确认入库 → 导出
4. Workflows 页 → 多工作流一键执行（含新类型）→ 新类型应最末执行

### 回归

- MA20 趋势 tab 仍正常（writer 抽公共后）
- 条件交集仍正常
- `get_trend_data(metric_type='ma20')` 结果不含 `high_price` 记录

## 后续非目标

- 不做趋势预测/异常检测。
- 不做周末/节假日补齐（空日期就是空日期）。
- 不在一次执行中扫历史所有目录自动补全 count（历史数据靠 Excel 导入补全）。
