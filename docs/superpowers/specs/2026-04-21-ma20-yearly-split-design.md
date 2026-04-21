# 20 日均线趋势：按最新公告日年度拆分子集

- 日期：2026-04-21
- 影响范围：`Statistics.vue`、`trend_service.py`、`workflow_executor.py::_match_sector`
- 零工作流变更、零 schema 变更

## 背景

统计分析页"站上20日均线趋势"目前以**全表**行为分子/分母采集占比。用户诉求：对 **1 并购重组 / 2 股权转让 / 9 招投标** 三类，按"最新公告日"所在年份拆出两条独立曲线——**本年（Y）** 和 **上年（Y-1）**，随自然年跨年自动推进（2027 年起变 2027 vs 2026，依此类推）。

## 术语

- **Y** = `now.year`，当前自然年
- **Y-1** = 上一自然年
- **年度父类型** = `并购重组 / 股权转让 / 招投标`（只有这三类做年度拆分）
- **年度子类型命名** = `{父类型}(YYYY)`，如 `并购重组(2026)`、`股权转让(2025)`、`招投标(2025)`

## 设计原则

1. **零 schema 迁移**：复用 `trend_statistics` 表的 `workflow_type` 字符串编码子集身份，跟质押 `质押(中大盘)/质押(小盘)` 同构
2. **零工作流侧影响**：工作流创建/编辑/执行、`workflow_type_config.py`、条件交集、目录结构全部不动
3. **复用已有模式**：双线渲染复用质押双盘、Excel 双列并排解析重构复用

## 数据模型

### 存储约定

`trend_statistics` 表不变。`(metric_type='ma20', workflow_type, date_str)` 唯一键不变。

各类型写入的 `workflow_type` 值：

| 父类型 | 写入 workflow_type 值 |
|---|---|
| 并购重组 | `并购重组(Y)` 和 `并购重组(Y-1)` 两条（条件见下） |
| 股权转让 | `股权转让(Y)` 和 `股权转让(Y-1)` 两条 |
| 招投标 | `招投标(Y)` 和 `招投标(Y-1)` 两条 |
| 增发实现 | `增发实现`（不拆分） |
| 申报并购重组 | `申报并购重组`（不拆分） |
| 减持叠加质押和大宗交易 | `减持叠加质押和大宗交易`（不拆分） |
| 质押 | `质押(中大盘)`、`质押(小盘)`（现状保留，不拆年份） |

### 历史数据处理（策略 b）

**不做迁移**。提供一次性清理脚本 `backend/scripts/cleanup_legacy_yearly_trend.py`：

```sql
DELETE FROM trend_statistics
WHERE metric_type = 'ma20'
  AND workflow_type IN ('并购重组', '股权转让', '招投标');
```

- 清理后，三类历史 ma20 统计**清零**，图表里从下一次 `_match_sector` 执行或手动录入开始重新积累
- 脚本幂等（可重复运行）；打印删除行数
- 手动执行；不放在应用启动路径

## 自动采集（`_match_sector`）

**位置**：`backend/services/workflow_executor.py::_match_sector`，现有自动采集块内（质押分支 / 整表分支之间）。

**新增年度分支**（在"非质押 else"里进一步判断年度父类型）：

```python
if self.workflow_type in ("并购重组", "股权转让", "招投标"):
    from datetime import datetime as _dt
    year_now = _dt.now().year
    # 解析最新公告日到 datetime（NaT 跳过）
    date_series = pd.to_datetime(df.get("最新公告日"), errors="coerce")
    for year in (year_now, year_now - 1):
        mask_year = date_series.dt.year == year
        sub_total = int(mask_year.sum())
        if sub_total == 0:
            continue
        sub_count = int(
            (df.loc[mask_year, "20日均线"].fillna("").astype(str).str.strip() != "").sum()
        )
        await save_trend_data(
            metric_type="ma20",
            workflow_type=f"{self.workflow_type}({year})",
            date_str=date_str or self.today,
            count=sub_count,
            total=sub_total,
            source="auto",
        )
        logger.info(
            f"自动采集MA20趋势(年度): type={self.workflow_type}({year}), "
            f"count={sub_count}, total={sub_total}"
        )
    # 不再写无后缀的记录
else:
    # 其他非质押、非年度父类型 → 维持整表采集（现状）
    ma20_count = ...
    await save_trend_data(metric_type="ma20", workflow_type=self.workflow_type or "并购重组", ...)
```

**关键点**：
- `最新公告日` 列缺失或整列不可解析：`mask_year.sum() == 0`，自动跳过该年度，不报错
- `最新公告日` 单元格解析失败（NaT）：不计入任一年份（既不在 Y 也不在 Y-1）
- Y-1 分母为 0（如数据集全是 Y 年）：跳过，只写一条 Y 记录
- 股权转让的 `最新公告日` 已由 `workflow_executor` 从 `公告日期` 映射得到（现状保留）
- 质押分支、其他类型分支（增发 / 申报 / 减持）**不改动**

## 手动录入 UI

**位置**：`Statistics.vue` 手动录入卡片 `manualForm`。

**动态字段**：当 `manualForm.workflow_type ∈ {并购重组, 股权转让, 招投标}` 时，表单追加 3 列（label 按 `now.year` 动态渲染）：

```
类型: [并购重组 ▼]    日期: [2026-04-21]
{Y} 数量: [______]    {Y} 总量: [______]      {Y} 占比: [--]
{Y-1} 数量: [______]  {Y-1} 总量: [______]    {Y-1} 占比: [--]
                                              [保存]
```

- `{Y}` 字段（2026）沿用现有 `manualForm.count / manualForm.total`
- `{Y-1}` 字段（2025）新增 `manualForm.count_prev / manualForm.total_prev`（**非必填**）
- label 动态：`` `${Y} 数量` `` / `` `${Y-1} 数量` ``
- 其他类型（增发、申报、减持、质押）：只显示原单行字段，行为不变

**下拉选项**：`INPUT_WORKFLOW_TYPES` 不变——用户看到的仍是 8 个父类型字符串，不暴露 `(YYYY)` 子类型。

**保存逻辑**（`submitManual`）：
1. 若 `workflow_type ∈ 年度父类型`：
   - 若 `count > 0 && total > 0` → 调 API 写 `类型(Y)` 一条
   - 若 `count_prev > 0 && total_prev > 0` → 再调 API 写 `类型(Y-1)` 一条
   - 都为空 → 告警"请至少填一组"
2. 否则走原分支（一条）

**提交方式**：前端循环调两次现有 `POST /api/trend/manual`，后端 API 不动。

## Excel 上传（双列并排通用化）

### 重构 `_parse_pledge_side_by_side`

抽成通用函数：

```python
def _parse_dual_columns_excel(
    file_path: str,
    left_spec: dict,    # {"workflow_type": "质押(中大盘)" or f"{父}({Y})", "header_keywords": [...], "aliases": [...]}
    right_spec: dict,
    sheet_finder_keywords: list,  # 替代现有"中大盘 + 小盘 + 日期/占比"的识别关键字
) -> List[Dict[str, Any]]:
    ...
```

- 日期列识别、`M月D日` / Excel 序列号 / datetime 兼容、`_to_ratio_float` 反算 total 的逻辑完全复用
- 双行表头 `pd.read_excel(..., header=[0,1])` 读取
- 列定位：`l0` 或 `l1` 含 `header_keywords / aliases` 任一项 → 判归左/右
- 每行输出 2 条记录（左+右），各记录带各自 `workflow_type`

**向后兼容**：质押解析改用新函数调用，功能等价。加质押解析单测防回归。

### 年度上传分发

`parse_excel_for_trend(file_path, workflow_type)` 扩展分发：

```python
if workflow_type == "质押(双列并排)":
    return _parse_dual_columns_excel(
        file_path,
        left_spec={"workflow_type": "质押(中大盘)", "header_keywords": ["中大盘"], "aliases": []},
        right_spec={"workflow_type": "质押(小盘)", "header_keywords": ["小盘"], "aliases": []},
        sheet_finder_keywords=["中大盘", "小盘"],
    )

if workflow_type.startswith("年度("):
    parent = workflow_type[len("年度("):-1]  # 例如 "并购重组"
    Y = datetime.now().year
    return _parse_dual_columns_excel(
        file_path,
        left_spec={
            "workflow_type": f"{parent}({Y})",
            "header_keywords": [str(Y)],
            "aliases": [f"{Y}至今", "本年", "今年"]
        },
        right_spec={
            "workflow_type": f"{parent}({Y-1})",
            "header_keywords": [str(Y-1)],
            "aliases": ["上年", "去年"]
        },
        sheet_finder_keywords=[str(Y), str(Y-1)],  # sheet 含本年和上年关键字
    )
# 原单列解析分支保留
```

### 前端上传下拉

`Statistics.vue` 的上传类型下拉新增 3 项（value 约定 `年度(父类型)`）：

```
- 1并购重组（并排双列：本年+上年）       value=年度(并购重组)
- 2股权转让（并排双列：本年+上年）       value=年度(股权转让)
- 9招投标（并排双列：本年+上年）         value=年度(招投标)
- 5质押（并排双列：中大盘+小盘）         value=质押(双列并排)   【现状保留】
```

**预览表格**：沿用质押双列的列（类型/日期/数量/总量/占比）。`类型` 列显示 `{父}({Y})` 和 `{父}({Y-1})`。

**入库**：现有 `confirmUpload` 调 `batch_save_trend_data`，每条记录各自独立写。无需改动。

### 提示文案

年度上传时在上传卡片下展示 `el-alert`：

> "表头两层：Row1 含 `{Y}` / `{Y-1}` 标签，Row2 含 `占20均线数量` / `占比`。每一日期会自动拆成 `{父}({Y})` 和 `{父}({Y-1})` 两条记录。"

## 图表渲染

**位置**：`Statistics.vue::renderChart(wt)`

**新增常量**：

```js
const YEARLY_PARENTS = ['并购重组', '股权转让', '招投标']
const CURRENT_YEAR = new Date().getFullYear()
```

**分组逻辑**（`grouped` 构造时）：对年度父类型，把 `trendData` 中 `workflow_type` 为 `{父}({Y})` 和 `{父}({Y-1})` 的记录分到该父类型下，并标记 `_year_label`：`"${Y}"` 或 `"${Y-1}"`。

**渲染**：`renderChart('并购重组')` 按质押双盘的实现画双线：
- 系列名称 = `"${Y}"`、`"${Y-1}"`（纯年份字符串）
- 占比为 Y 轴；数量/总量只在 tooltip 里显示
- `dualYAxis` 开关开启时：Y 系列在左轴、Y-1 在右轴
- 非年度父类型（增发 / 申报 / 减持）：保持现有单线渲染
- 质押：保持现有中大盘/小盘双线渲染

`allWorkflowTypes` 列表保持不变（仍是 8 个父类型，图表卡片一一对应）。

## 移除汇总条

`Statistics.vue` 的 `trend-summary` div（显示各类型最新占比和上下箭头的一排胶囊）整体删除，包括：
- 模板里的 `<div class="trend-summary">` 块
- `latestByType` 相关的 ref/computed（若仅被汇总条使用）
- `.trend-summary / .summary-item / .summary-ratio / .summary-type / .summary-empty` CSS

理由：信息密度低，占比数值在图表 tooltip 里已提供。

## 导出 Excel

**位置**：`trend_service.py::export_trend_excel_with_chart`

年度父类型的 sheet 结构改造（跟质押双盘 sheet 同款）：

```
日期 | {Y}数量 | {Y}总量 | {Y}占比 | {Y-1}数量 | {Y-1}总量 | {Y-1}占比
```

图表：xlsxwriter LineChart 双线，系列名 `"${Y}"` / `"${Y-1}"`。

其他类型 sheet 不变。总 sheet（中大盘 vs 小盘）不变。

## 影响面清单

| 文件 | 变动 |
|---|---|
| `backend/services/workflow_executor.py` | `_match_sector` 自动采集分支新增年度拆分 |
| `backend/services/trend_service.py` | `_parse_pledge_side_by_side` 重构为 `_parse_dual_columns_excel`；`parse_excel_for_trend` 分发 `年度(X)`；`export_trend_excel_with_chart` 年度 sheet 双线 |
| `frontend/src/views/Statistics.vue` | 手动录入字段动态扩展 / 上传下拉新增 3 项 / 图表分组双线 / **删除汇总条** / CSS 清理 |
| `backend/scripts/cleanup_legacy_yearly_trend.py` | 新增（一次性清理脚本） |
| **零改动** | `Workflows.vue` / `workflow_type_config.py` / `path_resolver.py` / 条件交集 / `_apply_filters` / 数据目录 |

## 测试计划

**后端单测**（`backend/tests/`）：
- `test_match_sector_yearly_split.py`
  - 给定 df 含最新公告日 2024/2025/2026/空/NaT 混合，断言：只写 `(2026)` 和 `(2025)` 各一条；`count/total` 与人工核对值一致；2024/空/NaT 不计入
  - `self.workflow_type = "增发实现"` 时走原整表分支，不写年度子类型
  - `self.workflow_type = "质押"` 时走现有质押分支，不受年度分支影响
- `test_dual_columns_parser.py`
  - 构造质押双列 xlsx fixture → 解析出 `质押(中大盘)` + `质押(小盘)` 两条/行
  - 构造年度双列 xlsx fixture（表头含 `2026/2025` 和 `占20均线数量/占比`）→ 解析出 `并购重组(2026)` + `并购重组(2025)` 两条/行
  - 年份别名：表头写 `2026至今` / `上年` 也能识别
  - 日期列 `M月D日` 解析、Excel 序列号解析继续工作
- `test_cleanup_legacy_yearly_trend.py`
  - 插入 `workflow_type ∈ {并购重组, 股权转让, 招投标, 质押(中大盘)}` 的记录，跑脚本后前 3 类清空、质押不动、其他 metric_type 不动

**前端手动验证**：
1. 创建/执行"并购重组"工作流 → DB 写入 `并购重组(2026)` + `并购重组(2025)` 两条；图表显示双线
2. 手动录入"并购重组"：同时填两组数字 → 保存后 DB 有两条；单填 Y 组 → 只有一条
3. 上传年度双列 Excel（示例截图的表头） → 预览显示双类型、双日期；确认入库生效
4. 非年度类型（增发/申报/减持/质押）行为完全不变
5. 汇总条已移除
6. 导出 Excel：并购/股权转让/招投标 sheet 含双线图

## 回滚计划

全部变更在 `feature/ma20-yearly-split` 分支；测试通过后合并到 main 再 deploy。
- DB 侧：清理脚本不幂等影响——若回滚，需自行重跑工作流重新采集
- 代码侧：`git revert` 合并 commit；两个解析函数互相独立，可单独回滚

## 开放问题

无。所有决策已定：
- 年度口径 = `now.year`（自然年滚动）
- 命名 = `父类型(YYYY)`
- 历史数据 = 删除不迁移（策略 b）
- 汇总条 = 整体移除
- 生效类型 = 并购重组 / 股权转让 / 招投标
