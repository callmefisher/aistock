# 质押工作流设计（Pledge Workflow）

- 日期：2026-04-20
- 状态：设计确认，待实施
- 作者：brainstorming（xiayanji × Claude）

## 1. 目标

在现有选股池自动化系统中新增工作流类型 `质押`，复用全部已有步骤链（合并 / 智能去重 / 提取列 / 百日新高 / 20 日均线 / 国企 / 一级板块），并针对质押数据特点做 6 处特化：

1. 合并阶段支持多文件 × 多 Sheet，产出统一的"来源"列（中大盘 / 小盘）。
2. 源文件可能缺失"序号"列，需要自动适配表头。
3. 源文件的"证券名称" 视同 "证券简称"。
4. 源文件中前缀含 "股权质押公告日期" 的列视同 "最新公告日"。
5. 新增可选步骤「质押异动和趋势」：从东方财富 datacenter-web 拉取该股过去 1 年质押公告明细，用 Mann-Kendall / 月度下采样 / 线性回归三种可选算法判定"持续递增/递减"，并按当日累计质押比例差分类"质押异动"。
6. 条件交集工作流遇到质押类型时，"资本运作行为"按行级"来源"字段细分为"质押中大盘 / 质押小盘"。

默认最终输出文件名 `5质押{date}.xlsx`；统计分析界面显示 `5质押` 前缀；默认类型顺序为 并购重组 → 股权转让 → 增发实现 → 申报并购重组 → 减持叠加质押和大宗交易 → **质押** → 招投标。

## 2. 非目标

- 不支持"质押"类型的实时在线查询（仅当日批量工作流场景）。
- 不在本次引入 Tushare/Wind 等付费数据源；东财直连 + AkShare 降级已能满足精度与可用性。
- 不重构现有工作流步骤链；所有变更通过类型分支实现，保持其他类型零回归。

## 3. 架构总览

```
[data/excel/质押/{date}/*.xlsx(多文件×多Sheet)]
          │
   merge_excel (质押分支: 多Sheet遍历 + 来源派生 + 证券名称/股权质押公告日期映射)
          │
   smart_dedup  →  extract_columns (保留"来源")
          │
   match_high_price → match_ma20 → match_soe → match_sector
          │                                         │
          │                    (最终输出 5质押{date}.xlsx, 含"来源"列)
          │                                         │
          └──→ pledge_trend_analysis (可选) ────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
   PledgeDataSource        pledge_trend.py (纯算法)
   东财直连 (主)             Mann-Kendall / 月度 / 线性
   AkShare (降级)            当日异动分类
   Redis 7天缓存             返回 Y/空 + 异动文本
         │
   最终输出再次覆盖为 5质押{date}.xlsx（新增 3 列）
```

条件交集读取各工作流的 `workflow_results.data_compressed`，其中质押类型的 JSON 自然包含"来源"列，按行派生"资本运作行为"= "质押中大盘" 或 "质押小盘"。

## 4. 配置变更（Section 1）

`backend/config/workflow_type_config.py` 新增：

```python
"质押": {
    "display_name": "质押",
    "base_subdir": "质押",
    "directories": {
        "upload_date": "质押/{date}",
        "public": "质押/public",
    },
    "naming": {
        "output_template": "5质押{date}.xlsx",
        "merge_output": "total_1.xlsx",
        "dedup_output": "deduped.xlsx",
        "extract_output": "output_2.xlsx",
        "match_high_price_output": "output_3.xlsx",
        "match_ma20_output": "output_4.xlsx",
        "match_soe_output": "output_5.xlsx",
    },
    "match_sources": {
        "match_high_price": "百日新高",
        "match_ma20": "20日均线",
        "match_soe": "国企",
        "match_sector": "一级板块",
    },
    "allowed_steps": [
        "merge_excel", "smart_dedup", "extract_columns",
        "match_high_price", "match_ma20", "match_soe", "match_sector",
        "pledge_trend_analysis",
    ],
}
```

`default_type_order`（条件交集）追加 `"质押"`，位置在 `减持叠加质押和大宗交易` 之后、`招投标` 之前：

```python
"default_type_order": [
    "并购重组", "股权转让", "增发实现",
    "申报并购重组", "减持叠加质押和大宗交易",
    "质押",
    "招投标",
]
```

## 5. 合并步骤特化（Section 2）

### 5.1 多文件 × 多 Sheet 合并

`_merge_excel` 内 `self.workflow_type == "质押"` 分支改用 `pd.read_excel(filepath, sheet_name=None)` 读所有 Sheet；每个 Sheet 单独走 `_detect_header_and_parse`，合并前为每行注入 `"来源"` 列。

```python
if self.workflow_type == "质押":
    sheet_map = pd.read_excel(filepath, sheet_name=None)
    for sheet_name, df_sheet in sheet_map.items():
        if df_sheet is None or len(df_sheet) == 0:
            continue
        df = self._detect_header_and_parse(df_sheet, known_col_names, f"{filepath}#{sheet_name}")
        df["来源"] = self._derive_pledge_source(sheet_name)
        df["_source_file"] = filename
        dfs.append(df)
    continue  # 此文件所有 Sheet 已处理
```

### 5.2 来源列派生规则

```python
def _derive_pledge_source(self, sheet_name: str) -> str:
    """Sheet 名以 '中大盘' 开头 → '中大盘'；否则 → '小盘'。"""
    return "中大盘" if str(sheet_name).strip().startswith("中大盘") else "小盘"
```

### 5.3 无序号列自动适配

`_detect_header_and_parse` 在"列名已正确 + 查序号行"分支之后，追加"无序号列"退化分支：以含 `证券代码/证券名称/证券简称/股权质押公告日期` 字段的行视作表头。

```python
if not seq_col:
    for idx in range(min(10, len(df_all))):
        row_vals = [str(v).strip() for v in df_all.iloc[idx] if pd.notna(v)]
        if any(any(k in v for k in
                   ["证券代码","证券名称","证券简称","股权质押公告日期"])
               for v in row_vals):
            header_row = df_all.iloc[idx]
            df = df_all.iloc[idx+1:].copy()
            df.columns = [str(h).strip() if pd.notna(h) else f"col_{i}"
                          for i, h in enumerate(header_row)]
            return df
```

合并后如无"序号"列，沿用现有 `_merge_excel` 末段 `insert(0, "序号", range(1, N+1))` 逻辑自动生成。

### 5.4 列名映射

在 `_merge_excel` 内 `self.workflow_type == "质押"` 分支（在 concat 之后）追加：

```python
# 通用字符清洗（同减持叠加质押和大宗交易）
for col in merged_df.columns:
    if merged_df[col].dtype == object:
        mask = merged_df[col].notna()
        merged_df.loc[mask, col] = (
            merged_df.loc[mask, col].astype(str)
            .str.replace('\u3000', ' ', regex=False)
            .str.replace(r'[\x00-\x1f\x7f-\x9f]', '', regex=True)
            .str.strip()
        )

# 证券名称 → 证券简称
if "证券简称" not in merged_df.columns and "证券名称" in merged_df.columns:
    merged_df = merged_df.rename(columns={"证券名称": "证券简称"})

# 前缀含 "股权质押公告日期" → 最新公告日
if "最新公告日" not in merged_df.columns:
    candidates = [c for c in merged_df.columns
                  if isinstance(c, str) and "股权质押公告日期" in c]
    if candidates:
        primary = candidates[0]
        for extra in candidates[1:]:
            merged_df[primary] = merged_df[primary].fillna(merged_df[extra])
            merged_df = merged_df.drop(columns=[extra])
        merged_df = merged_df.rename(columns={primary: "最新公告日"})
```

### 5.5 target_cols 白名单扩展

```python
if self.workflow_type == "质押":
    target_cols += ["来源"]
    target_cols += [c for c in df.columns
                    if isinstance(c, str) and "股权质押公告日期" in c]
```

### 5.6 extract_columns 保留来源

仅在 `workflow_type == "质押"` 时，默认提取列由 `[序号, 证券代码, 证券简称, 最新公告日]` 扩展为 `[序号, 证券代码, 证券简称, 最新公告日, 来源]`。

## 6. 新步骤 `pledge_trend_analysis`（Section 3）

### 6.1 模块划分

```
backend/services/pledge_data_source.py   # 数据源层（东财直连 + AkShare 降级 + Redis 缓存 + 反爬）
backend/services/pledge_trend.py         # 纯算法层（MK / 月度 / 线性 + 异动分类，无 I/O）
backend/services/workflow_executor.py    # 编排：_pledge_trend_analysis 方法
```

### 6.2 PledgeDataSource

```python
class PledgeDataSource:
    URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    REFERER = "https://data.eastmoney.com/gpzy/pledgeDetail.aspx"
    UA_POOL = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ... Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ... Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ... Edg/120.0.0.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ... Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ... Firefox/121.0",
    ]
    CACHE_TTL = 7 * 86400
    SOURCE_DOWN_TTL = 30 * 60
    MIN_INTERVAL = 1.0
    MAX_INTERVAL = 1.8
    MAX_CONSECUTIVE_FAILURES = 5

    def get_history(self, symbol: str, anchor_date: str,
                    window_days: int = 365) -> tuple[list[dict], str]:
        """返回 (records, source_name); source_name ∈ {eastmoney, cache, akshare, empty}."""
```

行为要点：
- **缓存键** `pledge:detail:{symbol}:{anchor_date}`，7 天 TTL；anchor 每日变化，老 key 自动 miss。
- **Source-down 标记** `pledge:source:down` 30 分钟 TTL；东财连续 5 次失败写入，期间直接走降级。
- **节流** `time.sleep(max(1.0 + random(0, 0.8) - elapsed, 0))`，每请求 UA 池随机挑一个，固定 Referer。
- **降级** 东财失败 → 调用 akshare `stock_gpzy_pledge_ratio_detail_em()`（已验证可用，60 条 002768 数据一致），按股票代码过滤后标准化为相同字段。
- **标准化字段** 无论哪个源，统一输出 `{证券代码, 公告日期, 股东名称, 是否控股股东, 质押股数, 占总股本比例, 累计质押比例, 前次累计质押比例, 累计变化, 质押开始日期, 解押日期, 状态}`。

### 6.3 pledge_trend.py（纯函数）

```python
def compute_trend(records: list[dict], anchor_date: str,
                  trend_algo: str = "mann_kendall",
                  mk_pvalue: float = 0.05,
                  b_max_reversals: int = 2,
                  c_min_r2: float = 0.7,
                  event_no_change: float = 0.5,
                  event_large: float = 3.0) -> dict[str, str]:
    """
    输入：已按 公告日期 升序的 records；锚点日期。
    输出：{"持续递增（一年内）": "Y"/"",
          "持续递减（一年内）": "Y"/"",
          "质押异动": "小幅转增/小幅转减/大幅激增/大幅骤减/本次质押趋势无变化/"(空)}
    """
```

#### 趋势算法

- **Mann-Kendall（默认）**：纯 Python 实现（约 20 行，`math.erf` 算标准正态 CDF p 值），`p < mk_pvalue` 且 `Z > 0` → 递增；`Z < 0` → 递减；样本 < 4 返空。
- **月度下采样**：按 `公告日期` 月末聚合（`累计质押比例` 月末值，**不前向填充**），统计相邻点方向反转次数 ≤ `b_max_reversals` 且首末差显著 → up/down。
- **线性回归**：`numpy.polyfit(degree=1)` 算斜率；手算 R² = `1 - SS_res/SS_tot`；`R² ≥ c_min_r2` 且斜率显著非零 → up/down。

#### 异动分类

```python
def _detect_event(records, anchor_date, no_change_th, large_th):
    today_rows = [r for r in records if r["公告日期"] == anchor_date]
    if not today_rows:
        return ""  # 空
    delta = max(r["累计质押比例"] for r in today_rows) \
          - min(r["前次累计质押比例"] for r in today_rows)
    if abs(delta) < no_change_th: return "本次质押趋势无变化"
    if delta > 0:
        return "大幅激增" if delta >= large_th else "小幅转增"
    return "大幅骤减" if abs(delta) >= large_th else "小幅转减"
```

默认阈值：`no_change=0.5 pct`，`large=3.0 pct`（UI 可改）。

### 6.4 步骤执行器 `_pledge_trend_analysis`

```python
async def _pledge_trend_analysis(self, config, df, date_str):
    # 1. 锚点严格校验
    if df is None or "证券代码" not in df.columns:
        return {"success": False, "message": "需要包含'证券代码'列的输入"}
    if "最新公告日" not in df.columns:
        return {"success": False, "message":
            "步骤失败：输入缺少'最新公告日'列（或'股权质押公告日期'未映射）"}
    missing = df[df["最新公告日"].isna() | (df["最新公告日"].astype(str).str.strip() == "")]
    if len(missing) > 0:
        sample = missing.head(5)[["证券代码","证券简称"]].to_dict("records")
        return {"success": False, "message":
            f"步骤失败：{len(missing)}行缺少'最新公告日'锚点，无法执行。示例: {sample}"}

    # 2. 读取配置
    trend_algo       = config.get("trend_algo", "mann_kendall")
    mk_p             = float(config.get("mk_pvalue", 0.05))
    b_rev            = int(config.get("b_max_reversals", 2))
    c_r2             = float(config.get("c_min_r2", 0.7))
    event_no_change  = float(config.get("event_no_change_threshold", 0.5))
    event_large      = float(config.get("event_large_threshold", 3.0))
    window_days      = int(config.get("window_days", 365))

    # 3. 逐股处理（每股 1 条日志）
    ds = PledgeDataSource(redis_client=get_redis(), akshare_fallback=True)
    df = df.copy()
    df["持续递增（一年内）"] = ""
    df["持续递减（一年内）"] = ""
    df["质押异动"] = ""
    stats = {"total": len(df), "ok": 0, "empty": 0, "fail": 0,
             "by_source": {"eastmoney": 0, "cache": 0, "akshare": 0, "empty": 0},
             "by_result": {k: 0 for k in
                 ["持续递增", "持续递减", "无趋势",
                  "小幅转增", "小幅转减", "大幅激增", "大幅骤减",
                  "本次质押趋势无变化", "空"]}}
    fail_samples = []

    for idx, row in df.iterrows():
        symbol = normalize_stock_code(row["证券代码"])
        anchor = str(row["最新公告日"]).strip()
        try:
            records, source = ds.get_history(symbol, anchor, window_days)
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
            result = compute_trend(records, anchor, trend_algo, mk_p, b_rev, c_r2,
                                    event_no_change, event_large)
            df.at[idx, "持续递增（一年内）"] = result["持续递增（一年内）"]
            df.at[idx, "持续递减（一年内）"] = result["持续递减（一年内）"]
            df.at[idx, "质押异动"] = result["质押异动"]
            # 统计
            if records: stats["ok"] += 1
            else:       stats["empty"] += 1
            if result["持续递增（一年内）"] == "Y": stats["by_result"]["持续递增"] += 1
            elif result["持续递减（一年内）"] == "Y": stats["by_result"]["持续递减"] += 1
            else: stats["by_result"]["无趋势"] += 1
            event = result["质押异动"] or "空"
            stats["by_result"][event] = stats["by_result"].get(event, 0) + 1

            logger.info(
                f"[质押异动趋势] {idx+1}/{len(df)} {symbol} {row.get('证券简称','')} "
                f"锚点={anchor} 源={source} 历史{len(records)}条 → "
                f"递增={result['持续递增（一年内）'] or '-'} "
                f"递减={result['持续递减（一年内）'] or '-'} "
                f"异动={result['质押异动'] or '-'}"
            )
        except Exception as e:
            stats["fail"] += 1
            if len(fail_samples) < 10:
                fail_samples.append({"symbol": symbol, "error": str(e)[:100]})
            logger.warning(f"[质押异动趋势] {symbol} 失败: {e}")

    # 4. 覆盖最终输出（使用 match_sector 的文件名 5质押{date}.xlsx）
    output_filename = self.resolver.get_output_filename("match_sector", date_str)
    output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
    df.to_excel(output_path, index=False)
    auto_adjust_excel_width(output_path)

    # 5. 触发缓存清理兜底
    try:
        cleanup_expired_pledge_cache(get_redis(), max_age_days=370)
    except Exception as e:
        logger.warning(f"[质押缓存清理] 失败（不影响主流程）: {e}")

    summary = (f"质押异动趋势: 共{stats['total']}只, "
               f"成功{stats['ok']}, 无历史{stats['empty']}, 失败{stats['fail']} | "
               f"源: 东财{stats['by_source']['eastmoney']}, "
               f"缓存{stats['by_source']['cache']}, "
               f"降级AkShare{stats['by_source']['akshare']}, "
               f"空{stats['by_source']['empty']}")
    logger.info(f"[质押异动趋势] {summary}")
    return {
        "success": True,
        "message": summary,
        "stats": stats,
        "fail_samples": fail_samples,
        "file_path": output_path,
        "rows": len(df),
        "_df": df,
    }
```

注册到 `execute_step` 分发器：
```python
elif step_type == "pledge_trend_analysis":
    return await self._pledge_trend_analysis(step_config, input_data, date_str)
```

## 7. 条件交集特化（Section 4）

`_condition_intersection` 内按行派生 `资本运作行为`：

```python
warnings_list = []

if wtype == "质押":
    if "来源" in df.columns:
        source_series = df["来源"].fillna("").astype(str).str.strip()
        missing_mask = ~source_series.isin(["中大盘", "小盘"])
        missing_count = int(missing_mask.sum())
        if missing_count > 0:
            sample = df.loc[missing_mask, "证券代码"].head(5).tolist() \
                     if "证券代码" in df.columns else []
            warnings_list.append(
                f"质押类型 {missing_count}/{len(df)} 行'来源'字段缺失或非法，"
                f"已兜底为'质押小盘'。示例: {sample}")
            logger.warning(f"[条件交集] {warnings_list[-1]}")
        extracted["资本运作行为"] = source_series.apply(
            lambda s: "质押中大盘" if s == "中大盘" else "质押小盘")
    else:
        warnings_list.append(f"质押类型 final 数据完全缺少'来源'列，全部归入'质押小盘'")
        logger.warning(f"[条件交集] {warnings_list[-1]}")
        extracted["资本运作行为"] = "质押小盘"
else:
    display_name = WORKFLOW_TYPE_CONFIG.get(wtype, {}).get("display_name", wtype)
    extracted["资本运作行为"] = display_name
```

返回值里增加 `"warnings": warnings_list`，供前端渲染黄色警示区。

`INTERSECTION_SOURCE_COLUMNS` / `INTERSECTION_DISPLAY_COLUMNS` 不变；Sheet1 与 Sheet2 (选股池) 均使用细分后的"资本运作行为"。

`save_workflow_result` 无需改：它用 `pd.read_excel(file_path)` 原样读最终 Excel 全列（"来源"自然包含），DB 的 `data_compressed` 一并保留。

## 8. 前端变更（Section 5）

### 8.1 Workflows.vue

- **步骤类型枚举**追加 `{ value: "pledge_trend_analysis", label: "质押异动和趋势" }`，仅在 `workflow_type === "质押"` 时可选。
- **pledge_trend_analysis 配置面板**（仅显示当前选中算法的参数，异动阈值始终显示）：
  - 趋势算法：`mann_kendall` (默认) / `monthly_downsample` / `linear_regression`
  - MK p 阈值（默认 0.05）
  - 月度反转数（默认 2）
  - 线性回归 R²（默认 0.7）
  - 异动无变化阈值 `|Δ| <`（默认 0.5 pct）
  - 异动大幅阈值 `|Δ| ≥`（默认 3.0 pct）
  - 历史窗口（默认 365 天）
- **执行反馈卡片** (`v-if="step.type === 'pledge_trend_analysis' && result.stats"`)：展示总数 / 成功 / 无历史 / 失败 / 数据源分布 / 判定结果分布 / 可展开的失败样本列表。
- **条件交集警告区** (`v-if="result.warnings?.length"`)：黄底折叠列表。
- **DEFAULT_TYPE_ORDER** 数组追加 `"质押"` 于 `减持叠加质押和大宗交易` 之后、`招投标` 之前。

### 8.2 Statistics.vue

```javascript
// TYPE_ORDER
{ key: '质押', display: '5质押' },   // 位置：'4申报并购重组' 之后、'6减持叠加质押和大宗交易' 之前

// ALL_WORKFLOW_TYPES
['并购重组', '股权转让', '增发实现', '申报并购重组',
 '质押',                                          // ← 新
 '减持叠加质押和大宗交易', '招投标']
```

### 8.3 最终输出文件名

由 `match_sector` 步骤的 `output_filename` 输入框控制，默认由 `PathResolver._generate_final_output_name` 根据 `output_template = "5质押{date}.xlsx"` 自动生成。

**需要修正 `PathResolver.get_output_filename`**：当前 `match_sector` 分支直接返回 `_generate_final_output_name()`，**忽略了 `user_specified` 参数**，导致 UI 上填写的最终文件名不生效。修正后：

```python
def get_output_filename(self, step_type, date_str=None, user_specified=None):
    if step_type == "match_sector":
        if user_specified and user_specified.strip():
            return user_specified.strip()
        return self._generate_final_output_name(date_str)
    # ... 其余不变
```

此修正对所有类型（并购重组/股权转让/...）都生效，但由于现有工作流并未使用 `user_specified`，不会产生行为回归。`_pledge_trend_analysis` 步骤读取最终输出路径时也要保持一致：优先取 `step_config["output_filename"]`（若用户在 `match_sector` 填过），否则走 PathResolver。

## 9. 数据与缓存（Section 6）

### 9.1 无新建数据库表

质押结果走现有 `workflow_results` 表；`save_workflow_result` 逻辑不变。

### 9.2 Redis 缓存三层淘汰

- **Key 设计**：`pledge:detail:{symbol}:{anchor_date}`，TTL 7 天。anchor 每次公告都变，老 key 自动 miss。
- **步骤后清理**：`_pledge_trend_analysis` 成功/失败路径末尾都调 `cleanup_expired_pledge_cache(max_age_days=370)`。
- **每日定时清理**（apscheduler，已在依赖）：凌晨 03:00 跑兜底清理。

```python
def cleanup_expired_pledge_cache(redis_client, max_age_days: int = 370) -> int:
    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    deleted, cursor = 0, 0
    while True:
        cursor, keys = redis_client.scan(cursor, match="pledge:detail:*", count=500)
        for key in keys:
            k = key.decode() if isinstance(key, bytes) else key
            parts = k.rsplit(":", 1)
            if len(parts) == 2 and parts[1] < cutoff:
                redis_client.delete(key)
                deleted += 1
        if cursor == 0: break
    logger.info(f"[质押缓存清理] 删除 anchor 早于 {cutoff} 的 key: {deleted}")
    return deleted
```

### 9.3 依赖

- `akshare==1.18.54` 已在。
- 不引入 `scipy`；用 `numpy.polyfit` 手写 R²。Mann-Kendall 纯 Python 实现。
- `requests` 已在。`redis==5.0.1` 已在 requirements，但项目目前**没有**实际的 Redis 客户端单例。

### 9.3.1 新建 Redis 客户端单例

项目现有缓存全部是模块级 Python dict（`_match_source_cache` / `_public_file_cache`），尚未使用 Redis 客户端。本次实施需新建 `backend/core/redis_client.py`：

```python
import redis
from core.config import settings

_client = None

def get_redis() -> redis.Redis:
    """返回进程级单例同步 Redis 客户端（decode_responses=True）。"""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
```

若连接失败，`PledgeDataSource` 应降级为"无缓存"模式（每次都请求东财），不阻断主流程。

### 9.4 目录

```
backend/core/
  redis_client.py           [新]  get_redis() 单例
backend/services/
  pledge_data_source.py     [新]
  pledge_trend.py           [新]
  pledge_cache_cleanup.py   [新]  cleanup_expired_pledge_cache()
  workflow_executor.py      [改]
backend/config/
  workflow_type_config.py   [改]
backend/main.py             [改]  启动时注册 apscheduler 03:00 清理 job

data/excel/质押/{date}/     [新，日上传]
data/excel/质押/public/     [新，预留]

frontend/src/views/
  Workflows.vue             [改]
  Statistics.vue            [改]
```

## 10. 测试计划（44 个用例）

全部单元测试用 mock（`unittest.mock` + `fakeredis`），不调真实东财接口；真实接口手工用 002768.SZ 做回归验证。

| 文件 | 用例数 | 覆盖对象 |
|---|---|---|
| `test_pledge_data_source.py` | 8 | 东财成功 / 东财 4xx / 东财超时 / 连续 5 次失败设 source_down / AkShare 降级成功 / AkShare 也失败 / 缓存命中 / UA 轮换 |
| `test_pledge_trend.py` | 12 | MK 强递增 / MK 强递减 / MK 无趋势 / MK 样本 < 4 / 月度允许反转 / 月度反转超限 / 线性 R² 达标 / 线性 R² 不达 / 异动小幅转增 / 异动大幅激增 / 异动大幅骤减 / 异动无变化 |
| `test_merge_excel_pledge.py` | 6 | 单文件单 Sheet / 多文件 / 多 Sheet / Sheet "中大盘XX" → 中大盘 / 其他 Sheet → 小盘 / 无序号列 / 证券名称映射 / 股权质押公告日期映射（拆成 7 个也可） |
| `test_pledge_trend_step.py` | 7 | 锚点缺失报错 / 正常流程 / 3 列写入 / Y 值标记 / 数据源分布统计 / fail_samples 收集 / summary 含警告 |
| `test_condition_intersection_pledge.py` | 4 | 来源=中大盘 → 质押中大盘 / 来源=小盘 → 质押小盘 / 来源缺失 → 质押小盘+warning / warnings 冒泡 |
| `test_pledge_cache_cleanup.py` | 4 | 清理早于 cutoff / 保留 cutoff 之后 / SCAN 分批不遗漏 / 空 Redis 不报错 |
| `test_workflow_type_config_pledge.py` | 3 | 类型注册存在 / default_type_order 含质押 / PathResolver 输出 `5质押{date}.xlsx` |

**手工回归**：用 002768.SZ 跑一次完整质押工作流（mock 上传一个多 Sheet 文件，锚点 2026-04-14），验证最终 Excel 含 3 列，`持续递减（一年内）=Y`、`质押异动=小幅转减`（对应东财实测：累计比例 17.74 → 8.14 一年内递减，当日 Δ = 8.14 - 9.78 = -1.64 pct，属小幅转减）。

## 11. 实施阶段（Section 7）

### 阶段 1 — 配置与目录（0 风险）
1. `workflow_type_config.py` 注册 "质押"
2. 前端 `TYPE_ORDER` / `ALL_WORKFLOW_TYPES` / `DEFAULT_TYPE_ORDER` 追加
3. 创建 `data/excel/质押/public/`
- 测试：`test_workflow_type_config_pledge.py`
- 验收：UI 能选中质押，条件交集默认顺序含质押

### 阶段 2 — 合并特化（中风险）
1. `_detect_header_and_parse` 增加无序号列分支
2. `_merge_excel` 增加质押分支（多 Sheet / 来源 / 列映射 / target_cols）
3. `_extract_columns` 保留"来源"
- 测试：`test_merge_excel_pledge.py`
- 验收：手动上传 2 个多 Sheet 文件，前 3 步产出含"来源"列，中大盘 sheet → 中大盘

### 阶段 3 — 数据源 + 趋势算法（高风险，核心）
1. 新建 `pledge_data_source.py`
2. 新建 `pledge_trend.py`
3. 新增 `_pledge_trend_analysis` 并注册到 `execute_step`
4. `cleanup_expired_pledge_cache` + apscheduler 03:00 定时任务
- 测试：`test_pledge_data_source.py` + `test_pledge_trend.py` + `test_pledge_trend_step.py` + `test_pledge_cache_cleanup.py`
- 手工回归：002768.SZ
- 验收：异动步骤能跑通，3 列正确，stats/fail_samples 结构完整

### 阶段 4 — 条件交集 + 前端反馈（中低风险）
1. `_condition_intersection` 质押分支 + warnings 冒泡
2. `Workflows.vue` 步骤类型 / 配置面板 / 反馈卡片 / warnings 区
3. `Statistics.vue` TYPE_ORDER
- 测试：`test_condition_intersection_pledge.py`
- 验收：同时存在多类型 final 数据时，条件交集里质押行"资本运作行为"细分正确

## 12. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 东财改 reportName / 字段名 | 低 | 高 | 降级 AkShare；监控连续失败率告警 |
| 东财短时反爬 | 低 | 中 | UA 池 + 1.0-1.8s 抖动节流 + 连续 5 次失败设 `source:down` 30 分钟冷却 + 降级 AkShare |
| Redis 未启动 | 低 | 中 | 缓存层失败不阻断，直接走数据源 |
| 多 Sheet 合并内存膨胀 | 低 | 低 | 现有 target_cols 列过滤提前裁剪 |
| 手算 R² 数值精度 | 极低 | 极低 | numpy.polyfit + 手算 1 - SS_res/SS_tot，精度 1e-12 |
| 锚点日期格式不统一 | 中 | 中 | 统一 normalize 为 `YYYY-MM-DD`；缺失则整步骤报错 |
| final 数据缺"来源" | 中 | 低 | 兜底"质押小盘"+ warnings 冒泡+日志 |
| 日志每股一条刷屏 | 中 | 低 | 实际 < 1000 股可接受 |

## 13. 验收标准

功能：
- 质押工作流能正常创建；目录结构正确
- 多文件 × 多 Sheet 合并产出"来源"列
- 无序号列源文件能自动识别
- 证券名称 / 股权质押公告日期 能正确映射
- 异动步骤 3 列：Y / "" / 异动文本
- 条件交集里质押行"资本运作行为"= "质押中大盘" 或 "质押小盘"
- 统计分析显示 `5质押`
- 最终输出默认文件名 `5质押{date}.xlsx`，UI 可改

质量：
- 44 个单元测试全部通过
- 002768.SZ 手工回归：`持续递减=Y / 质押异动=小幅转减`
- 前端卡片能显示 stats / warnings / fail_samples

运维：
- Redis：7 天 TTL + 每日 03:00 定时 + 步骤末尾清理
- 反爬：UA 池 + 抖动 + 连续 5 次失败 30 分钟冷却 + 降级
- 日志：每股 1 条 + 步骤级 summary
- CLAUDE.md 经验教训追加

构建：
- `./deploy.sh build && ./deploy.sh restart` 成功
- `cd backend && python -m pytest tests/ -v` 通过
- `cd frontend && npm test` 通过

## 14. 深度代码 Review（强制）

所有阶段实施完成、测试通过、服务部署成功后，**必须**触发一次深度代码 review，不可跳过。Review 聚焦以下维度：

### 14.1 Review 范围

- 新增文件：`pledge_data_source.py` / `pledge_trend.py` / `pledge_cache_cleanup.py` / `redis_client.py` / 全部新测试文件
- 修改文件：`workflow_executor.py`（_merge_excel/_detect_header_and_parse/_pledge_trend_analysis/_condition_intersection）、`workflow_type_config.py`、`path_resolver.py`、`main.py`、`Workflows.vue`、`Statistics.vue`

### 14.2 Review 清单

**安全**
- 无硬编码密钥
- Redis 键无用户输入拼接注入
- 东财响应 JSON 的字段读取有异常兜底（避免 KeyError / NoneType 崩溃工作流）
- 外部 HTTP 调用有超时和重试上限

**正确性**
- Mann-Kendall 实现与 NIST 参考结果一致（用一组已知值对比）
- 月度下采样不做 forward-fill（与 spec 一致）
- 异动 Δ 取 `max(ACCUM) - min(PRE_ACCUM)` 与 spec 一致
- 来源派生 `startswith("中大盘")` 与 spec 一致
- 锚点缺失时**整步骤失败**（不降级不跳过）
- 缓存 key 用 `{symbol}:{anchor_date}`，不同锚点 key 独立

**边界**
- 空 DataFrame / 单股 / 单笔公告 / 所有公告同日 / 1 年内 < 4 条记录 / 历史中有负数累计比例（脏数据）
- 东财返回 `result=null`（测试中贵州茅台的情况）
- Redis 未启动 / 连接断开

**性能**
- 无 `O(N²)` 误用；MK 内部的 `O(n²)` 是算法本身
- 每股调用有节流；不并发打穿东财
- 日志不会在每股 1 条时压垮磁盘（对 < 1000 股，约 1MB 级别，OK）

**一致性（与 spec）**
- 4 处类型顺序数组与 spec 完全一致
- 三列字段名为 `持续递增（一年内）` / `持续递减（一年内）` / `质押异动`（含中文括号）
- 异动 5 种文本完全一致：`小幅转增` / `小幅转减` / `大幅激增` / `大幅骤减` / `本次质押趋势无变化`
- 资本运作行为映射 `质押中大盘` / `质押小盘` 字串一致

**工程质量**
- 无死代码 / 注释的 TODO 遗留
- 日志级别合理（INFO 进度 / WARNING 单股失败 / ERROR 步骤级异常）
- 错误信息用户友好（能用于排查）
- 单元测试独立、确定性、不依赖网络

### 14.3 Review 流程

1. 实施 Agent 完成所有阶段后，回报"实施完成"
2. 用户触发 `/review` 或调用 `code-reviewer` agent 做第一轮自动扫描
3. 再由用户人工 review 上面 14.2 清单里的关键正确性点（尤其 MK 算法和来源派生）
4. 发现的问题分级：CRITICAL 立即修；MAJOR 必修；MINOR 记录到经验教训
5. Review 通过后，更新 `CLAUDE.md` 经验教训，本次交付才算完成
