# 禁用「百日新高/20日均线」自动复制 + 修复质押「最新公告日」颜色

日期：2026-04-28

## 背景

两个独立但一起提出的小需求：

1. **禁用自动复制**：`match_high_price`（百日新高）和 `match_ma20`（20日均线）当日目录不存在时，`path_resolver.ensure_match_source_files` 会向前 30 天复制历史文件。用户希望**所有场景**都不再自动复制；其他 match step（国企 / 一级板块）保持原行为。
2. **质押「最新公告日」颜色**：`workflow_executor._finalize_pledge_output` 生成的中大盘/小盘两 sheet 里，「最新公告日」没有被标红；而统计分析页下载质押结果（`statistics_api.py`）时颜色标记正常。需要 finalize 端复用下载端的着色逻辑。

## 方案

### 一、配置驱动的 auto_copy 开关

改 `backend/config/workflow_type_config.py`：`match_sources` 的 value 支持 dict 形态。

```python
# 改前（所有 8 处相同）
"match_sources": {
    "match_high_price": "百日新高",
    "match_ma20": "20日均线",
    "match_soe": "国企",
    "match_sector": "一级板块",
},

# 改后
"match_sources": {
    "match_high_price": {"dir": "百日新高", "auto_copy": False},
    "match_ma20":       {"dir": "20日均线", "auto_copy": False},
    "match_soe":        "国企",          # 字符串 → 默认 auto_copy=True
    "match_sector":     "一级板块",
},
```

改 `backend/services/path_resolver.py`：

- 新增内部 `_resolve_source_entry(step_type) -> (dir, auto_copy)`，向后兼容字符串形态。
- `get_match_source_directory` 用 `dir`。
- `ensure_match_source_files` 在目录不存在时，若 `auto_copy=False` → 仅 `os.makedirs` + `logger.warning` 后返回，不触发 30 天回溯复制。

**复用的告警**：原有 `logger.warning(f"匹配源目录为空且30天内无历史数据可复制: ...")` 文案风格沿用，新增一条类似但文案区分的 warning：
```
匹配源目录为空且 auto_copy=False，不复制历史文件: {target_dir} (step={step_type})
```

### 二、质押「最新公告日」颜色复用下载端逻辑

**抽公共函数** `backend/services/pledge_format.py`（已存在、已含 `apply_pledge_ratio_coloring`）：

```python
def load_pledge_announcement_max_ts(current_date_str: str) -> Optional[pd.Timestamp]:
    """查 workflow_results 表中 workflow_type='质押' 且 date_str < current_date_str 的
    所有 step_type='final' 记录，解压 data_compressed，取所有行「最新公告日」的全局最大值。
    """

def apply_announcement_date_coloring(wb, max_ts) -> None:
    """给 workbook 所有 sheet 的「最新公告日」列施加红标（`ts > max_ts` 才标）。"""
```

两处调用：
- `backend/services/workflow_executor.py::_finalize_pledge_output`：把原「按 sheet 分 baseline」逻辑整体替换为 `max_ts = load_pledge_announcement_max_ts(date_str); apply_announcement_date_coloring(wb, max_ts)`。
- `backend/api/statistics_api.py`（line 139-206）：移除内联实现，改调公共函数。

**移除**：`workflow_executor._load_pledge_baseline`（不再被调用）。

**签名保持**：`_finalize_pledge_output(df, date_str, output_path, public_dir)` 的 `public_dir` 参数保留（测试大量使用），函数体内不再使用 public 扫描 baseline。

### 三、测试影响

- `tests/test_workflow_type_config_pledge.py::test_pledge_match_sources_inherit_standard`：断言映射结构；需改为断言 `dir`/`auto_copy` 形态。
- `tests/test_pledge_finalize.py`：多个用例依赖「按 public xlsx 分 sheet baseline 判红」；改用 mock `load_pledge_announcement_max_ts` 注入 `max_ts`。
- `tests/test_pledge_dedup_and_sync.py`：`_sync_pledge_final_to_public` 行为不变，无需改。
- 新增 `tests/test_path_resolver_no_auto_copy.py`：断言 `auto_copy=False` 的 step 不复制历史文件（即便历史目录存在）。

### 四、落地顺序

1. 添加 `pledge_format.py::load_pledge_announcement_max_ts` + `apply_announcement_date_coloring`（+ 新测试）
2. 改 `workflow_executor._finalize_pledge_output` 用新函数；删 `_load_pledge_baseline`
3. 改 `statistics_api.py` 用新函数
4. 改 `workflow_type_config.py` 的 match_sources 结构
5. 改 `path_resolver._resolve_source_entry` + `ensure_match_source_files`
6. 改 / 新增测试
7. 全测试 → `./deploy.sh build && ./deploy.sh restart`
