# 质押工作流输出重构设计

- 日期：2026-04-22
- 状态：设计确认，待实施
- 作者：brainstorming（xiayanji × Claude）
- 关联：`2026-04-20-pledge-workflow-design.md`（原质押工作流，本文档在其基础上做输出侧重构）

## 1. 目标

重构 `工作流类型 == 质押` 的最终输出结构与样式，具体 8 项需求：

1. `extract_columns` 步骤在质押分支下**保留所有原始列**（不再做白名单过滤）
2. 最终输出列序固定为：`证券代码 → 证券简称 → 最新公告日 → 百日新高 → 站上20日线 → 国央企 → 所属板块 →` 原始剩余列（源序，去重）
3. 去除 `来源` 列输出，改为 **sheet 路由信号**：`中大盘{date}` 放 Sheet1，`小盘{date}` 放 Sheet2，date 格式 `YYYYMMDD`
4. 前缀含 `质押比例` 的列两两相邻对比：右侧 A 列 > 左侧 B 列 → A 单元格红底；A < B → A 绿底；相等/任一为空 → 不着色
5. 最终输出 2 个 sheet（空的也保留），上传到 `/data/excel/质押/public/` 并清理旧文件（沿用现有逻辑）
6. 新文件某行的 `最新公告日` 若 > public 里该 `证券代码` 历史最大日期（或该股在 public 未出现）→ 该行 `最新公告日` 单元格绿底
7. `pledge_trend_analysis`（质押异动和趋势）步骤**保留为可选**，用户不勾选就不触发
8. 其余步骤（`merge_excel / smart_dedup / match_*`）逻辑复用，不做重构

## 2. 非目标

- 不动其他 6 种工作流类型
- 不动前端 UI 步骤勾选逻辑
- 不动 `pool_xlsx_importer.py` / `pool_cache.py`（条件交集专用）
- 不新增步骤类型
- 不改现有 `match_*` 步骤的核心逻辑

## 3. 关键决策（来自澄清问答）

| 决策点 | 结论 |
|---|---|
| 首次出现基准范围 | public 目录现存文件 + `stock_pools` 表 `is_active=1` 历史 |
| 判定键 | 仅 `证券代码`；新文件 `最新公告日 >` public 里该股历史最大日期 → 首次出现 |
| 质押比例空值处理 | 任一侧为空 → 跳过，不着色 |
| 质押比例列顺序 | 保持源表自然列序，相邻两两比对 |
| "原始剩余列"含义 | 排除前 7 列已覆盖的，不重复 |
| 中大盘/小盘 sheet | 固定 2 sheet，空的保留表头 |
| Public 基准按 sheet 分 | 合并一个基准；写入端仍严格按来源分 sheet |
| 文件来源识别 | 文件名优先（含 "中大盘" / "小盘"），sheet 名兼容回退 |
| Public 文件位置 | 由上次运行自动同步到 `质押/public/`，无需每次手动上传 |

## 4. 架构总览

```
上传：data/excel/质押/{date}/  ←  中大盘*.xlsx + 小盘*.xlsx
public：data/excel/质押/public/5质押{上期date}.xlsx  ←  上次运行自动同步

步骤链（全部可选，用户前端选）：
  merge_excel → smart_dedup → extract_columns (质押分支: 保留全列)
              → match_high_price / match_ma20 / match_soe / match_sector
              → pledge_trend_analysis (可选)
              → [最后一步末尾] _maybe_finalize_pledge()
                  └─ _finalize_pledge_output():
                       · 读 public + stock_pools 构建 baseline dict
                       · 列重排（7 前缀 + 原始剩余）
                       · 按 来源 拆 Sheet1/Sheet2（丢弃 来源 列）
                       · 质押比例条件格式（红/绿）
                       · 最新公告日首次出现绿标
                       · 写出 5质押{date}.xlsx
                       · _sync_pledge_final_to_public() 同步 public
```

**核心原则**：样式只在 `_finalize_pledge_output` 最后一次写入时施加。中间步骤的 `to_excel` 不带样式，避免被 openpyxl 清除。

## 5. 详细设计

### 5.1 `_derive_pledge_source(file_name, sheet_name)` 改签名

```python
def _derive_pledge_source(file_name: str, sheet_name: str) -> str:
    fn = str(file_name or "")
    if "中大盘" in fn: return "中大盘"
    if "小盘" in fn: return "小盘"
    sn = str(sheet_name or "")
    if sn.startswith("中大盘"): return "中大盘"
    return "小盘"
```

调用点：`_merge_excel` 传入 `file_path.stem` 和 `sheet_name`。

### 5.2 `_extract_columns_pledge`（新增）

触发：`_extract_columns` 开头判定 `workflow_type == "质押"` → 走该分支。

行为：
- 读入整个 DataFrame，**保留所有原始列**
- 保证以下 4 列存在（缺则补空列）：`证券代码`、`证券简称`、`最新公告日`、`来源`
  - `最新公告日` 缺失时：找前缀含 `股权质押公告日期` 的**第一个**列，**复制**其值为新列（不删除原列）
  - `证券简称` 缺失时：尝试从 `名称` / `证券名称` 复制
- 不再追加 `持续递增/递减/质押异动` 三列（由 `pledge_trend_analysis` 负责）
- 写出 `output_2.xlsx`，无样式

### 5.3 `_finalize_pledge_output(df, date_str, output_path, public_dir)`（新增）

#### 5.3.1 列重排

**固定前缀 7 列**（按此序）：
```
证券代码, 证券简称, 最新公告日, 百日新高, 站上20日线, 国央企, 所属板块
```

缺失列补空列占位（如用户未选对应 match_* 步骤）。

**剩余列**：原始 DataFrame 其他列按**源序**追加，排除：
- 已在前 7 列覆盖的（证券代码 / 证券简称 / 最新公告日 / 映射源的 "股权质押公告日期" 首列）
- `来源` 列（丢弃）
- `序号` 列（若存在；最终重排序号）

**序号**：每个 sheet 最左添加 `序号` 列（1 起递增）。

#### 5.3.2 分 Sheet

- `df_big = df[df.来源 == "中大盘"]`，写入 `Sheet1 = 中大盘{date}`
- `df_small = df[df.来源 != "中大盘"]`，写入 `Sheet2 = 小盘{date}`
- 空 DataFrame 仍写表头
- 写入后丢弃 `来源` 列

#### 5.3.3 Public 基准字典

**读取时机**：`_finalize_pledge_output` 最开始，写出之前（避免读到自己）。

**数据源**（合并为一个字典）：
1. `public_dir` 下现存 xlsx 所有 sheet 所有行：遍历列，提取 `最新公告日` + 所有前缀含 `股权质押公告日期` 的列值，与 `证券代码` 组合
2. `stock_pools` 表 `is_active=1` 的 `(证券代码, 公告日期)` 记录

**结构**：
```python
baseline: dict[str, datetime.date] = {normalize_stock_code(证券代码): 最大历史日期}
```

**判定**（新文件某行 code, pub_date）：
- `code not in baseline` → 首次出现 → 绿
- `code in baseline and pub_date > baseline[code]` → 首次出现 → 绿
- 否则 → 不绿

#### 5.3.4 质押比例条件格式

**识别**：所有列名前缀含 `质押比例` 的列，按源序取索引列表 `ratio_cols`。

**算法**（每行独立）：
```
for i in range(1, len(ratio_cols)):
    A = to_float(row[ratio_cols[i]])
    B = to_float(row[ratio_cols[i-1]])
    if A is None or B is None: continue
    if A > B: 单元格[ratio_cols[i]] 填红
    elif A < B: 单元格[ratio_cols[i]] 填绿
    # A == B 不处理
```

- `to_float`：`pd.to_numeric(str(x).replace('%',''), errors='coerce')`，NaN → None
- 只给 A（右侧）着色；B（最左列）永远不着色
- `ratio_cols[0]` 永远不着色

#### 5.3.5 最新公告日绿标

对每行，若 5.3.3 判定首次出现 → 该行 `最新公告日` 单元格绿底。两个 sheet 各自按行施加（基准合并，但着色按行独立）。

#### 5.3.6 颜色常量

沿用现有：
- 红：`PatternFill(start_color="FFC00000", end_color="FFC00000", fill_type="solid")`（深红，同 `_ranking_sort`）
- 绿：`PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")`（浅绿，同 `_condition_intersection`）

#### 5.3.7 写文件流程

1. 构建 baseline
2. 列重排 → 拆 df_big/df_small
3. `openpyxl.Workbook()` 写两 sheet（表头 + 数据）
4. 遍历每行施加 5.3.4 + 5.3.5 样式
5. 保存到 `output_path`
6. 调用 `_sync_pledge_final_to_public(output_path)`

### 5.4 `_maybe_finalize_pledge(context, current_step_name)`（新增 helper）

```python
def _maybe_finalize_pledge(self, context, current_step_name):
    if context.workflow_type != "质押": return
    if current_step_name != context.step_names[-1]: return
    df = pd.read_excel(context.last_output_path)
    output_path = context.data_dir / f"5质押{context.date_str}.xlsx"
    self._finalize_pledge_output(df, context.date_str, output_path, context.public_dir)
    self._sync_pledge_final_to_public(output_path)
```

**挂载点**（每处末尾一行）：
- `_extract_columns`
- `_smart_dedup`
- `_match_high_price / _match_ma20 / _match_soe / _match_sector`
- `_pledge_trend_analysis`

**移除**：
- `_match_sector` 现有的 `_sync_pledge_final_to_public` 直接调用（L1288 附近）
- `_pledge_trend_analysis` 现有的 `_sync_pledge_final_to_public` 直接调用（L2371 附近）

## 6. 兼容性与边界

| 场景 | 行为 |
|---|---|
| 首次冷启动，public 空 | `baseline = {}`，所有行 `最新公告日` 绿标 |
| 某 sheet 无数据 | 仍写该 sheet，仅表头，保证 2 sheet 恒定 |
| 质押比例只有 1 列 | 不着色（无左邻） |
| 质押比例值含 "%" | `to_float` 剥离后解析 |
| 质押比例值无法解析 | 视为 None，跳过 |
| 用户只选部分 match_* | 缺失列补空列，列序不变 |
| 用户只选前 3 步 | `_extract_columns` 末尾触发 finalize |
| `match_*` 读取更宽的 DataFrame | 已核实为列追加逻辑，无白名单假设，兼容 |
| `来源` 字段缺失 | 按 sheet 名回退；仍无 → 默认 "小盘" |

### 6.1 对"站上20日均线趋势"统计分析的影响

**结论**：不影响图表与导出（它们完全依赖 DB 表 `trend_statistics`，不读质押 xlsx 文件结构）。

**唯一接触点**：`backend/services/trend_service.py` 的 `_parse_pledge_side_by_side`（L289-298）会在用户上传质押 xlsx 到"趋势统计"时解析双 sheet。新设计的 sheet 命名为 `中大盘{date}` / `小盘{date}`，该解析器**以 sheet 名前缀 "中大盘" / "小盘" 识别**，新命名兼容，无需改动。

**实施约束**：Sheet1 命名必须以 `中大盘` 开头，Sheet2 必须以 `小盘` 开头（即使当期无数据也沿用此命名，保持解析器兼容）。

## 7. 测试点（TDD 阶段覆盖）

**单元测试**：
1. `_derive_pledge_source`：文件名含"中大盘"/"小盘"/都不含 → 正确来源
2. `_finalize_pledge_output` 列重排：7 前缀列顺序；原始列去重保留；`来源/序号` 丢弃
3. 质押比例着色：A>B 红、A<B 绿、A=B 空、任一空跳过、单列不处理
4. Public baseline：新代码绿、老代码新日期绿、老代码老日期不绿、public 空全绿
5. 分 sheet：中大盘空仅表头、小盘空仅表头、两边有数据正确分配
6. `_maybe_finalize_pledge`：最后一步触发、非最后一步 return、非质押 return

**集成测试**：
7. 完整管线（2 上传文件 + 全步骤 → 文件结构 + 样式正确）
8. Public 有上期文件 → 绿标数量正确
9. 极简管线（仅 merge+dedup+extract）→ 仍能出最终文件

## 8. 实施顺序

1. 修改 `_derive_pledge_source` 签名及调用点
2. 新增 `_extract_columns_pledge` + 在 `_extract_columns` 入口加类型分支
3. 新增 `_finalize_pledge_output`（列重排 + 分 sheet + baseline + 着色）
4. 新增 `_maybe_finalize_pledge` helper
5. 在 8 处步骤末尾挂载 helper
6. 移除 `match_sector` 和 `pledge_trend_analysis` 末尾的重复 public sync
7. 补单元测试 + 集成测试
8. `./deploy.sh build && ./deploy.sh restart`，真实数据回归

## 9. 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| `_finalize_pledge_output` 读 public 失败 | 中 | try/except，失败时 baseline 空，记 warning 日志，不阻断输出 |
| 列名编码/空白字符差异导致匹配失败 | 中 | 所有前缀匹配用 `.strip()` + `str()` 防御 |
| 样式写入性能（大表 × 多质押比例列） | 低 | 单次运行 stock 数 < 1000，openpyxl 可承受 |
| 重复 public sync 移除漏一处 | 中 | grep `_sync_pledge_final_to_public` 全部调用点，最后仅保留 helper 内一处 |
