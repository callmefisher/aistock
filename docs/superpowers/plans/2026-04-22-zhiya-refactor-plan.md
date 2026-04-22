# 质押工作流输出重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `workflow_type == "质押"` 的最终输出重构为：两 sheet（中大盘{date}/小盘{date}）+ 固定前 7 列 + 原始剩余列 + 质押比例相邻红绿对比 + 最新公告日首次出现绿标，并同步到 public 目录。

**Architecture:** 在 `WorkflowExecutor` 中新增 `_extract_columns_pledge`（保留全列）和 `_finalize_pledge_output`（列重排+分 sheet+条件格式+绿标），由 `api/workflows.py::run_workflow` 在最后一步结束后显式调用一次 `executor.finalize_pledge_if_needed()`。中间步骤不带样式，样式只在 finalize 一次性施加，避免被 openpyxl 中间写入清除。

**Tech Stack:** Python 3.14 / FastAPI / pandas / openpyxl / pytest / SQLAlchemy / MySQL

**关联文档:** `docs/superpowers/specs/2026-04-22-zhiya-refactor-design.md`

---

## 文件结构

**新增 / 修改**：

| 文件 | 角色 |
|---|---|
| `backend/services/workflow_executor.py` | 修改：`_derive_pledge_source` 签名 / 新增 `_extract_columns_pledge` / 新增 `_finalize_pledge_output` / 新增 `finalize_pledge_if_needed` / 移除 `_match_sector` 和 `_pledge_trend_analysis` 里重复的 `_sync_pledge_final_to_public` 调用 |
| `backend/api/workflows.py` | 修改：在 `run_workflow` 循环结束后调用 `executor.finalize_pledge_if_needed()` |
| `backend/tests/test_pledge_finalize.py` | 新增：覆盖 `_finalize_pledge_output` 列重排、分 sheet、着色、绿标 |
| `backend/tests/test_pledge_extract_columns.py` | 新增：覆盖 `_extract_columns_pledge` 保留全列行为 |
| `backend/tests/test_derive_pledge_source.py` | 新增：覆盖 `_derive_pledge_source(file_name, sheet_name)` 新签名 |

**锚点（用于快速定位）**：
- `_derive_pledge_source`：`workflow_executor.py:180`
- `_sync_pledge_final_to_public`：`workflow_executor.py:184`
- `_extract_columns`：`workflow_executor.py:924`
- `_match_sector` 末尾 sync 调用：`workflow_executor.py:1288`
- `_pledge_trend_analysis` 末尾 sync 调用：`workflow_executor.py:2371`
- `_merge_excel` 里 `_derive_pledge_source` 调用点：`workflow_executor.py:512`
- `run_workflow` 循环：`backend/api/workflows.py:445-472`

---

## Task 1: `_derive_pledge_source` 改签名（文件名优先，sheet 名兼容）

**Files:**
- Modify: `backend/services/workflow_executor.py:180-182`
- Modify: `backend/services/workflow_executor.py:512` (调用点)
- Test: `backend/tests/test_derive_pledge_source.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_derive_pledge_source.py`:

```python
import pytest
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    return WorkflowExecutor(base_dir="/tmp", workflow_type="质押")


class TestDerivePledgeSource:
    def test_file_name_big(self, executor):
        assert executor._derive_pledge_source("中大盘20260420.xlsx", "Sheet1") == "中大盘"

    def test_file_name_small(self, executor):
        assert executor._derive_pledge_source("小盘20260420.xlsx", "任意") == "小盘"

    def test_file_name_both_missing_sheet_big(self, executor):
        assert executor._derive_pledge_source("pledge.xlsx", "中大盘20260420") == "中大盘"

    def test_file_name_both_missing_sheet_unknown(self, executor):
        assert executor._derive_pledge_source("pledge.xlsx", "Sheet1") == "小盘"

    def test_file_name_wins_over_sheet(self, executor):
        assert executor._derive_pledge_source("中大盘.xlsx", "小盘20260420") == "中大盘"

    def test_empty_args(self, executor):
        assert executor._derive_pledge_source("", "") == "小盘"

    def test_none_args(self, executor):
        assert executor._derive_pledge_source(None, None) == "小盘"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_derive_pledge_source.py -v
```

预期：全部失败（签名只接一个参数），`TypeError: _derive_pledge_source() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: 修改 `_derive_pledge_source` 签名**

替换 `backend/services/workflow_executor.py:180-182`：

```python
    def _derive_pledge_source(self, file_name: str, sheet_name: str) -> str:
        """质押类型来源识别：文件名优先（含"中大盘"/"小盘"），sheet 名兼容回退。"""
        fn = str(file_name or "")
        if "中大盘" in fn:
            return "中大盘"
        if "小盘" in fn:
            return "小盘"
        sn = str(sheet_name or "")
        if sn.startswith("中大盘"):
            return "中大盘"
        return "小盘"
```

- [ ] **Step 4: 更新调用点 `workflow_executor.py:512`**

当前代码：
```python
df_parsed["来源"] = self._derive_pledge_source(sheet_name)
```

先用 grep 找上下文确认变量名：
```bash
grep -n "for sheet_name\|file_path\|xlsx_file" backend/services/workflow_executor.py | awk -F: '$2 >= 440 && $2 <= 520' | head -20
```

改为（用 Read 找到包含"for sheet_name"循环所在的外层变量，假定是 `file_path`；若实际是 `xlsx_file` 则替换）：
```python
df_parsed["来源"] = self._derive_pledge_source(os.path.basename(file_path), sheet_name)
```

**验证方法**：搜索所有 `_derive_pledge_source(` 调用：
```bash
grep -n "_derive_pledge_source(" backend/services/workflow_executor.py
```
应该只有定义和一个调用点。

- [ ] **Step 5: 运行单元测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_derive_pledge_source.py -v
```

预期：7 个测试全部 PASS

- [ ] **Step 6: 运行 merge_excel 相关已有测试防回归**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_merge_excel_pledge.py -v
```

预期：已有测试全部 PASS（可能需要根据已有测试调用 `_derive_pledge_source` 的形式作小补丁；若现有测试直接调用了单参数版本，这个测试文件里也要改签名调用）

- [ ] **Step 7: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/tests/test_derive_pledge_source.py backend/tests/test_merge_excel_pledge.py && git commit -m "refactor(pledge): _derive_pledge_source 文件名优先识别来源"
```

---

## Task 2: `_extract_columns_pledge` 保留全列

**Files:**
- Modify: `backend/services/workflow_executor.py:924` (入口分支)
- Modify: `backend/services/workflow_executor.py` (新增 `_extract_columns_pledge` 方法)
- Test: `backend/tests/test_pledge_extract_columns.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_pledge_extract_columns.py`:

```python
import os
import tempfile
import pandas as pd
import pytest
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    with tempfile.TemporaryDirectory() as base:
        ex = WorkflowExecutor(base_dir=base, workflow_type="质押")
        yield ex


def _make_df(tmpdir, **cols):
    df = pd.DataFrame(cols)
    path = os.path.join(tmpdir, "input.xlsx")
    df.to_excel(path, index=False)
    return df, path


class TestExtractColumnsPledge:
    @pytest.mark.asyncio
    async def test_keeps_all_original_columns(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.12],
            "额外列A": ["foo"],
        })
        result = await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert set(df.columns) <= set(out_df.columns)
        assert "额外列A" in out_df.columns
        assert "质押比例-20260118" in out_df.columns

    @pytest.mark.asyncio
    async def test_maps_pledge_date_to_latest_announce(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "来源": ["中大盘"],
            "股权质押公告日期-20260420": ["2026-04-20"],
        })
        result = await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert "最新公告日" in out_df.columns
        assert out_df.iloc[0]["最新公告日"] == "2026-04-20"
        # 原列仍保留
        assert "股权质押公告日期-20260420" in out_df.columns

    @pytest.mark.asyncio
    async def test_maps_name_to_abbreviation(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "名称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["小盘"],
        })
        result = await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        assert "证券简称" in out_df.columns
        assert out_df.iloc[0]["证券简称"] == "平安银行"

    @pytest.mark.asyncio
    async def test_fills_missing_required_cols_with_empty(self, executor, tmp_path):
        df = pd.DataFrame({"证券代码": ["000001.SZ"]})
        result = await executor._extract_columns_pledge(df.copy(), str(tmp_path / "out.xlsx"))
        out_df = pd.read_excel(str(tmp_path / "out.xlsx"))
        for col in ("证券代码", "证券简称", "最新公告日", "来源"):
            assert col in out_df.columns
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_extract_columns.py -v
```

预期：`AttributeError: 'WorkflowExecutor' object has no attribute '_extract_columns_pledge'`

- [ ] **Step 3: 新增 `_extract_columns_pledge` 方法**

在 `workflow_executor.py` 的 `_extract_columns` 方法定义正上方（约 L923 前）插入：

```python
    async def _extract_columns_pledge(self, df: pd.DataFrame, output_path: str) -> Dict[str, Any]:
        """质押类型的 extract_columns：保留全部原始列，补齐必须列。

        - 不做白名单过滤
        - 保证 证券代码/证券简称/最新公告日/来源 四列存在（缺则补空列或从别名映射）
        - 最新公告日：缺失时找前缀含"股权质押公告日期"的第一列复制值（不删原列）
        - 证券简称：缺失时尝试 名称 / 证券名称
        - 不追加 持续递增/递减/质押异动（由 pledge_trend_analysis 负责）
        - 写出无样式 xlsx
        """
        if df is None:
            df = pd.DataFrame()
        df = df.copy()

        # 证券代码 兜底
        if "证券代码" not in df.columns:
            df["证券代码"] = ""

        # 证券简称 映射/兜底
        if "证券简称" not in df.columns:
            for alias in ("名称", "证券名称"):
                if alias in df.columns:
                    df["证券简称"] = df[alias]
                    break
            else:
                df["证券简称"] = ""

        # 最新公告日 映射/兜底
        if "最新公告日" not in df.columns:
            pledge_date_cols = [c for c in df.columns if "股权质押公告日期" in str(c)]
            if pledge_date_cols:
                df["最新公告日"] = df[pledge_date_cols[0]]
            else:
                df["最新公告日"] = ""

        # 来源 兜底（merge_excel 阶段应已注入；此处仅防御）
        if "来源" not in df.columns:
            df["来源"] = "小盘"

        df.to_excel(output_path, index=False)
        return {
            "success": True,
            "message": f"质押 extract_columns 完成，保留 {len(df.columns)} 列",
            "data": {"output_path": output_path, "row_count": len(df)},
            "_df": df,
        }
```

- [ ] **Step 4: 在 `_extract_columns` 入口加类型分支**

Read `workflow_executor.py:924` 附近 10 行，定位函数签名后的第一行 try/入口，在最前面插入分支（注意 output_path 的获取方式要和原函数一致——很可能是 `self.resolver.get_output_filename("extract_columns", date_str)` 或类似；Step 4 里先 Read 现有函数头部 40 行以得到具体 output_path 构造方式，然后加分支）。

先 Read 确认：
```
Read workflow_executor.py lines 924-970
```

定位 output_path 构造后，在 `try:` 之后、原业务逻辑之前插入：

```python
        if self.workflow_type == "质押":
            # 重构：质押分支保留全列，不走白名单过滤
            # output_path 必须和原函数构造方式一致（见下方原代码）
            daily_dir = self.resolver.get_daily_dir(date_str)
            output_name = self.resolver.get_output_filename("extract_columns", date_str) or "output_2.xlsx"
            output_path = os.path.join(daily_dir, output_name)
            return await self._extract_columns_pledge(df if df is not None else pd.DataFrame(), output_path)
```

**⚠️ 执行时注意**：上述 `daily_dir` / `output_name` 变量构造必须和 `_extract_columns` 原代码第一段保持一致。若原代码用的是 `self.resolver.get_upload_directory` 或其他 API，按原代码照抄。

- [ ] **Step 5: 运行单元测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_extract_columns.py -v
```

预期：4 个测试全部 PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/tests/test_pledge_extract_columns.py && git commit -m "feat(pledge): extract_columns 质押分支保留全列"
```

---

## Task 3: `_finalize_pledge_output` 列重排 + 分 sheet（不含样式）

**Files:**
- Modify: `backend/services/workflow_executor.py` (新增 `_finalize_pledge_output` + 辅助函数)
- Test: `backend/tests/test_pledge_finalize.py`

- [ ] **Step 1: 写失败测试（列重排 + 分 sheet）**

创建 `backend/tests/test_pledge_finalize.py`:

```python
import os
import tempfile
import pandas as pd
import pytest
from openpyxl import load_workbook
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    with tempfile.TemporaryDirectory() as base:
        ex = WorkflowExecutor(base_dir=base, workflow_type="质押")
        yield ex


class TestFinalizeLayout:
    def test_column_order_with_all_prefix_cols(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "百日新高": ["是"],
            "站上20日线": ["是"],
            "国央企": ["是"],
            "所属板块": ["金融"],
            "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.12],
            "额外列": ["foo"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        assert wb.sheetnames == ["中大盘20260420", "小盘20260420"]
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        # 首列是序号
        assert header[0] == "序号"
        # 固定前 7 列（序号之后）
        assert header[1:8] == ["证券代码", "证券简称", "最新公告日", "百日新高", "站上20日线", "国央企", "所属板块"]
        # 来源被丢弃
        assert "来源" not in header
        # 额外列保留
        assert "额外列" in header
        assert "质押比例-20260118" in header

    def test_split_by_source(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ", "000002.SZ"],
            "证券简称": ["平安银行", "万科A"],
            "最新公告日": ["2026-04-20", "2026-04-20"],
            "来源": ["中大盘", "小盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        big = wb["中大盘20260420"]
        small = wb["小盘20260420"]
        # 中大盘 1 行 + 表头
        assert big.max_row == 2
        assert big.cell(2, 2).value == "000001.SZ"
        # 小盘 1 行 + 表头
        assert small.max_row == 2
        assert small.cell(2, 2).value == "000002.SZ"

    def test_empty_source_keeps_header_only(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        small = wb["小盘20260420"]
        # 只表头
        assert small.max_row == 1

    def test_missing_prefix_cols_filled_empty(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        # 缺失的匹配列仍以空列占位
        assert "百日新高" in header
        assert "站上20日线" in header
        assert "国央企" in header
        assert "所属板块" in header

    def test_drops_original_xuhao(self, executor, tmp_path):
        df = pd.DataFrame({
            "序号": [99],
            "证券代码": ["000001.SZ"],
            "证券简称": ["平安银行"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
        })
        output_path = tmp_path / "5质押20260420.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        # 序号列是重排后的 1 起递增，不应有 99
        assert ws.cell(2, 1).value == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py -v -k "TestFinalizeLayout"
```

预期：`AttributeError: ... '_finalize_pledge_output'`

- [ ] **Step 3: 实现 `_finalize_pledge_output`（只含布局，不含样式和 baseline）**

在 `workflow_executor.py` 的 `_sync_pledge_final_to_public` 定义之后（约 L220）插入：

```python
    _PLEDGE_FIXED_PREFIX_COLS = (
        "证券代码", "证券简称", "最新公告日",
        "百日新高", "站上20日线", "国央企", "所属板块",
    )

    def _reorder_pledge_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """按固定前 7 列 + 原始剩余列（源序、去重）返回新 DataFrame。
        丢弃 来源 / 序号 列；缺失的前 7 列补空列。
        """
        df = df.copy()
        # 前 7 列保证存在（缺则空）
        for col in self._PLEDGE_FIXED_PREFIX_COLS:
            if col not in df.columns:
                df[col] = ""
        # 识别要丢弃的列
        drop_cols = {"来源", "序号"}
        # 剩余列：原始列序，不在前 7、不在 drop 集合
        prefix = list(self._PLEDGE_FIXED_PREFIX_COLS)
        rest = [c for c in df.columns if c not in prefix and c not in drop_cols]
        return df[prefix + rest]

    def _finalize_pledge_output(
        self,
        df: pd.DataFrame,
        date_str: str,
        output_path: str,
        public_dir: str,
    ) -> None:
        """质押最终输出：列重排 + 分 sheet + 样式（Task 4/5/6 分步加入）。

        当前版本（Task 3）：仅列重排 + 分 sheet，无条件格式、无绿标。
        """
        from openpyxl import Workbook

        if df is None:
            df = pd.DataFrame()
        # 分 sheet 前先拆（需要来源列）
        src_col = df["来源"] if "来源" in df.columns else pd.Series(["小盘"] * len(df))
        df_big = df[src_col == "中大盘"].copy()
        df_small = df[src_col != "中大盘"].copy()

        # 列重排（此阶段 来源 会被丢弃）
        df_big = self._reorder_pledge_columns(df_big)
        df_small = self._reorder_pledge_columns(df_small)

        wb = Workbook()
        wb.remove(wb.active)
        for sheet_name, sub_df in (
            (f"中大盘{date_str}", df_big),
            (f"小盘{date_str}", df_small),
        ):
            ws = wb.create_sheet(sheet_name)
            header = ["序号"] + list(sub_df.columns)
            ws.append(header)
            for i, (_, row) in enumerate(sub_df.iterrows(), start=1):
                ws.append([i] + [row[c] for c in sub_df.columns])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        logger.info(f"[质押 finalize] 已写出 {output_path}")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestFinalizeLayout -v
```

预期：5 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/tests/test_pledge_finalize.py && git commit -m "feat(pledge): _finalize_pledge_output 列重排+分 sheet"
```

---

## Task 4: 质押比例相邻红绿条件格式

**Files:**
- Modify: `backend/services/workflow_executor.py` (扩充 `_finalize_pledge_output`)
- Test: `backend/tests/test_pledge_finalize.py` (新增测试类)

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_pledge_finalize.py` 末尾追加：

```python
RED_COLOR = "FFC00000"
GREEN_COLOR = "FFC6EFCE"


def _get_fill(ws, row, col):
    c = ws.cell(row, col)
    if c.fill and c.fill.start_color:
        return (c.fill.start_color.rgb or "").upper()
    return ""


class TestPledgeRatioColoring:
    def test_ratio_increase_red(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"],
            "证券简称": ["A"],
            "最新公告日": ["2026-04-20"],
            "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.15],  # 右 > 左 → 红
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert RED_COLOR in _get_fill(ws, 2, col_right)

    def test_ratio_decrease_green(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.15],
            "质押比例-20260304": [0.10],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_right)

    def test_ratio_equal_no_color(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.10],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        fill = _get_fill(ws, 2, col_right)
        assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_either_empty_skipped(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ", "000002.SZ"],
            "证券简称": ["A", "B"],
            "最新公告日": ["2026-04-20", "2026-04-20"],
            "来源": ["中大盘", "中大盘"],
            "质押比例-20260118": [None, 0.10],
            "质押比例-20260304": [0.15, None],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        for row in (2, 3):
            fill = _get_fill(ws, row, col_right)
            assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_leftmost_never_colored(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": [0.10],
            "质押比例-20260304": [0.15],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_left = header.index("质押比例-20260118") + 1
        fill = _get_fill(ws, 2, col_left)
        assert RED_COLOR not in fill and GREEN_COLOR not in fill

    def test_ratio_with_percent_string(self, executor, tmp_path):
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
            "质押比例-20260118": ["10.0%"],
            "质押比例-20260304": ["15.0%"],
        })
        output_path = tmp_path / "out.xlsx"
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_right = header.index("质押比例-20260304") + 1
        assert RED_COLOR in _get_fill(ws, 2, col_right)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestPledgeRatioColoring -v
```

预期：全部失败（颜色未施加）

- [ ] **Step 3: 在 `_finalize_pledge_output` 中加入着色逻辑**

修改 `_finalize_pledge_output`，在 `wb.save(output_path)` **之前**插入着色代码块。先在文件顶部 import 区域（当前已有 `from openpyxl.styles import PatternFill` 的位置附近；若没有，在 `_finalize_pledge_output` 内部 import）加 `PatternFill`。

将 `_finalize_pledge_output` 末尾替换为：

```python
        # --- Task 4: 质押比例相邻红绿 ---
        from openpyxl.styles import PatternFill
        red_fill = PatternFill(start_color="FFC00000", end_color="FFC00000", fill_type="solid")
        green_fill = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")

        def _to_float(val):
            if val is None:
                return None
            try:
                s = str(val).strip().replace("%", "")
                if s == "" or s.lower() == "nan":
                    return None
                return float(s)
            except (ValueError, TypeError):
                return None

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            header = [c.value for c in ws[1]]
            ratio_col_idx = [i + 1 for i, h in enumerate(header) if str(h or "").startswith("质押比例")]
            if len(ratio_col_idx) < 2:
                continue
            for row in range(2, ws.max_row + 1):
                for k in range(1, len(ratio_col_idx)):
                    right = ws.cell(row, ratio_col_idx[k])
                    left = ws.cell(row, ratio_col_idx[k - 1])
                    a = _to_float(right.value)
                    b = _to_float(left.value)
                    if a is None or b is None:
                        continue
                    if a > b:
                        right.fill = red_fill
                    elif a < b:
                        right.fill = green_fill

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        logger.info(f"[质押 finalize] 已写出 {output_path}")
```

**注意**：原 Task 3 里已有的 `os.makedirs` + `wb.save` + `logger.info` 三行要先删除，合并到上面代码块末尾，避免重复。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestPledgeRatioColoring -v
```

预期：6 个测试全部 PASS

- [ ] **Step 5: 运行 Task 3 的布局测试防回归**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestFinalizeLayout -v
```

预期：5 个测试全部仍 PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/tests/test_pledge_finalize.py && git commit -m "feat(pledge): 质押比例相邻红绿条件格式"
```

---

## Task 5: Baseline 基准 + 最新公告日首次出现绿标

**Files:**
- Modify: `backend/services/workflow_executor.py` (新增 `_load_pledge_baseline` + 在 `_finalize_pledge_output` 加绿标)
- Test: `backend/tests/test_pledge_finalize.py` (新增测试类)

- [ ] **Step 1: 写失败测试**

在 `tests/test_pledge_finalize.py` 末尾追加：

```python
class TestPledgeFirstAppearance:
    def _write_public_baseline(self, public_dir, code, date_val, date_str):
        """写一份历史 public 文件，含某代码的某公告日。"""
        from openpyxl import Workbook
        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet(f"中大盘{date_str}")
        ws.append(["序号", "证券代码", "证券简称", "最新公告日"])
        ws.append([1, code, "A", date_val])
        ws2 = wb.create_sheet(f"小盘{date_str}")
        ws2.append(["序号", "证券代码", "证券简称", "最新公告日"])
        wb.save(str(public_dir / f"5质押{date_str}.xlsx"))

    def test_new_code_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        # public 空
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_date)

    def test_existing_code_newer_date_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        self._write_public_baseline(public_dir, "000001.SZ", "2026-03-01", "20260301")
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260420", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260420"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        assert GREEN_COLOR in _get_fill(ws, 2, col_date)

    def test_existing_code_same_or_older_not_green(self, executor, tmp_path):
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        self._write_public_baseline(public_dir, "000001.SZ", "2026-04-20", "20260420")
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        output_path = tmp_path / "out.xlsx"
        # 写入前把 output 路径放到别处，避免覆盖读入自己
        executor._finalize_pledge_output(df, "20260421", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["中大盘20260421"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        fill = _get_fill(ws, 2, col_date)
        assert GREEN_COLOR not in fill

    def test_baseline_merges_both_sheets(self, executor, tmp_path):
        """基准合并：新文件小盘行的代码，若在 public 中大盘 sheet 出现过，也算已见过。"""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        # 在公开文件的中大盘 sheet 写入 000002.SZ @ 2026-04-20
        from openpyxl import Workbook
        wb_pub = Workbook()
        wb_pub.remove(wb_pub.active)
        ws_big = wb_pub.create_sheet("中大盘20260301")
        ws_big.append(["序号", "证券代码", "证券简称", "最新公告日"])
        ws_big.append([1, "000002.SZ", "B", "2026-04-20"])
        ws_small = wb_pub.create_sheet("小盘20260301")
        ws_small.append(["序号", "证券代码", "证券简称", "最新公告日"])
        wb_pub.save(str(public_dir / "5质押20260301.xlsx"))
        # 新文件：小盘 sheet 里有 000002.SZ @ 2026-04-20（同日期，不该绿）
        df = pd.DataFrame({
            "证券代码": ["000002.SZ"], "证券简称": ["B"],
            "最新公告日": ["2026-04-20"], "来源": ["小盘"],
        })
        output_path = tmp_path / "out.xlsx"
        executor._finalize_pledge_output(df, "20260421", str(output_path), str(public_dir))
        wb = load_workbook(str(output_path))
        ws = wb["小盘20260421"]
        header = [c.value for c in ws[1]]
        col_date = header.index("最新公告日") + 1
        fill = _get_fill(ws, 2, col_date)
        assert GREEN_COLOR not in fill
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestPledgeFirstAppearance -v
```

预期：全部失败（无基准读取 + 绿标）

- [ ] **Step 3: 实现 `_load_pledge_baseline` 方法**

在 `workflow_executor.py` 的 `_reorder_pledge_columns` 之后插入：

```python
    def _load_pledge_baseline(self, public_dir: str) -> Dict[str, Any]:
        """读 public 目录所有 xlsx + stock_pools 表，构建 baseline。

        返回 {normalize_stock_code(证券代码): 已见过的最大日期(pd.Timestamp)}
        失败时返回空 dict，不抛。
        """
        baseline: Dict[str, Any] = {}
        # 1) 读 public 目录所有 xlsx
        try:
            if public_dir and os.path.isdir(public_dir):
                from openpyxl import load_workbook as _lwb
                for fname in os.listdir(public_dir):
                    if not fname.lower().endswith(".xlsx"):
                        continue
                    fpath = os.path.join(public_dir, fname)
                    try:
                        wb = _lwb(fpath, read_only=True, data_only=True)
                        for sheet_name in wb.sheetnames:
                            ws = wb[sheet_name]
                            rows = ws.iter_rows(values_only=True)
                            try:
                                header = next(rows)
                            except StopIteration:
                                continue
                            header = [str(h) if h is not None else "" for h in header]
                            # 找 证券代码 + 所有日期列
                            code_idx = None
                            date_idxs = []
                            for i, h in enumerate(header):
                                if h == "证券代码":
                                    code_idx = i
                                elif h == "最新公告日" or "股权质押公告日期" in h:
                                    date_idxs.append(i)
                            if code_idx is None or not date_idxs:
                                continue
                            for row in rows:
                                if not row:
                                    continue
                                code = row[code_idx] if code_idx < len(row) else None
                                if not code:
                                    continue
                                nc = normalize_stock_code(str(code).strip())
                                if not nc:
                                    continue
                                for di in date_idxs:
                                    if di >= len(row):
                                        continue
                                    dv = row[di]
                                    if dv is None or dv == "":
                                        continue
                                    try:
                                        ts = pd.to_datetime(dv, errors="coerce")
                                        if pd.isna(ts):
                                            continue
                                    except Exception:
                                        continue
                                    prev = baseline.get(nc)
                                    if prev is None or ts > prev:
                                        baseline[nc] = ts
                        wb.close()
                    except Exception as e:
                        logger.warning(f"[质押 baseline] 读取 public 文件失败 {fname}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"[质押 baseline] 扫描 public 目录失败: {e}")

        # 2) 读 stock_pools 表
        try:
            from core.database import SessionLocal
            from models.models import StockPool
            db = SessionLocal()
            try:
                rows = db.query(StockPool).filter(StockPool.is_active == 1).all()
                for pool in rows:
                    codes = pool.stock_codes or []
                    pub_date = getattr(pool, "announcement_date", None) or getattr(pool, "pool_date", None)
                    if not pub_date:
                        continue
                    try:
                        ts = pd.to_datetime(pub_date, errors="coerce")
                        if pd.isna(ts):
                            continue
                    except Exception:
                        continue
                    for c in codes:
                        nc = normalize_stock_code(str(c).strip())
                        if not nc:
                            continue
                        prev = baseline.get(nc)
                        if prev is None or ts > prev:
                            baseline[nc] = ts
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[质押 baseline] 读取 stock_pools 失败: {e}")

        logger.info(f"[质押 baseline] 构建完成，共 {len(baseline)} 条代码")
        return baseline
```

**注意**：`stock_pools` 表的字段名可能不是 `stock_codes` / `announcement_date`——实施时先 `grep -n "class StockPool" backend/models/models.py` 确认字段，按实际字段名替换。若字段不存在，保留 try/except 的容错，让 baseline 至少能从 public 文件读到。

- [ ] **Step 4: 在 `_finalize_pledge_output` 中调用 baseline + 绿标施加**

修改 `_finalize_pledge_output`，在**构建 wb 之前**加载 baseline，在**着色质押比例之后、save 之前**施加绿标：

```python
    def _finalize_pledge_output(
        self,
        df: pd.DataFrame,
        date_str: str,
        output_path: str,
        public_dir: str,
    ) -> None:
        """质押最终输出：列重排 + 分 sheet + 条件格式 + 首次出现绿标。"""
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill

        if df is None:
            df = pd.DataFrame()

        # Baseline：写之前读
        baseline = self._load_pledge_baseline(public_dir)

        src_col = df["来源"] if "来源" in df.columns else pd.Series(["小盘"] * len(df))
        df_big = df[src_col == "中大盘"].copy()
        df_small = df[src_col != "中大盘"].copy()
        df_big = self._reorder_pledge_columns(df_big)
        df_small = self._reorder_pledge_columns(df_small)

        wb = Workbook()
        wb.remove(wb.active)
        for sheet_name, sub_df in (
            (f"中大盘{date_str}", df_big),
            (f"小盘{date_str}", df_small),
        ):
            ws = wb.create_sheet(sheet_name)
            header = ["序号"] + list(sub_df.columns)
            ws.append(header)
            for i, (_, row) in enumerate(sub_df.iterrows(), start=1):
                ws.append([i] + [row[c] for c in sub_df.columns])

        red_fill = PatternFill(start_color="FFC00000", end_color="FFC00000", fill_type="solid")
        green_fill = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")

        def _to_float(val):
            if val is None:
                return None
            try:
                s = str(val).strip().replace("%", "")
                if s == "" or s.lower() == "nan":
                    return None
                return float(s)
            except (ValueError, TypeError):
                return None

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            header = [c.value for c in ws[1]]
            # 4.1 质押比例相邻红绿
            ratio_col_idx = [i + 1 for i, h in enumerate(header) if str(h or "").startswith("质押比例")]
            if len(ratio_col_idx) >= 2:
                for row in range(2, ws.max_row + 1):
                    for k in range(1, len(ratio_col_idx)):
                        right = ws.cell(row, ratio_col_idx[k])
                        left = ws.cell(row, ratio_col_idx[k - 1])
                        a = _to_float(right.value)
                        b = _to_float(left.value)
                        if a is None or b is None:
                            continue
                        if a > b:
                            right.fill = red_fill
                        elif a < b:
                            right.fill = green_fill

            # 4.2 最新公告日首次出现绿标
            if "证券代码" in header and "最新公告日" in header:
                code_col = header.index("证券代码") + 1
                date_col = header.index("最新公告日") + 1
                for row in range(2, ws.max_row + 1):
                    code_val = ws.cell(row, code_col).value
                    date_val = ws.cell(row, date_col).value
                    if not code_val or not date_val:
                        continue
                    nc = normalize_stock_code(str(code_val).strip())
                    if not nc:
                        continue
                    try:
                        ts = pd.to_datetime(date_val, errors="coerce")
                        if pd.isna(ts):
                            continue
                    except Exception:
                        continue
                    prev = baseline.get(nc)
                    if prev is None or ts > prev:
                        ws.cell(row, date_col).fill = green_fill

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wb.save(output_path)
        logger.info(f"[质押 finalize] 已写出 {output_path}")
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py -v
```

预期：Layout (5) + RatioColoring (6) + FirstAppearance (4) = 15 个全 PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/tests/test_pledge_finalize.py && git commit -m "feat(pledge): 首次出现绿标 + baseline 从 public/stock_pools 构建"
```

---

## Task 6: `finalize_pledge_if_needed` 对外方法 + run_workflow 挂载 + 移除重复 sync

**Files:**
- Modify: `backend/services/workflow_executor.py` (新增对外方法、移除 L1288 和 L2371 的 sync 调用)
- Modify: `backend/api/workflows.py` (在 run_workflow 循环后调用)

- [ ] **Step 1: 写失败集成测试**

在 `backend/tests/test_pledge_finalize.py` 追加：

```python
class TestFinalizePledgeIfNeeded:
    @pytest.mark.asyncio
    async def test_non_pledge_noop(self, tmp_path):
        ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="并购重组")
        # 即使 last output 存在也不应处理
        result = ex.finalize_pledge_if_needed(
            last_output_path=str(tmp_path / "nonexistent.xlsx"),
            date_str="20260420",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_pledge_runs_finalize_and_syncs(self, tmp_path, monkeypatch):
        ex = WorkflowExecutor(base_dir=str(tmp_path), workflow_type="质押")
        # 构造一个 last output（extract_columns 或 match_sector 可能写出的文件）
        daily_dir = tmp_path / "data" / "excel" / "质押" / "20260420"
        daily_dir.mkdir(parents=True)
        public_dir = tmp_path / "data" / "excel" / "质押" / "public"
        public_dir.mkdir(parents=True)
        df = pd.DataFrame({
            "证券代码": ["000001.SZ"], "证券简称": ["A"],
            "最新公告日": ["2026-04-20"], "来源": ["中大盘"],
        })
        last_output = daily_dir / "output_5.xlsx"
        df.to_excel(str(last_output), index=False)

        # monkeypatch resolver 以返回可控路径
        monkeypatch.setattr(ex.resolver, "get_daily_dir", lambda d=None: str(daily_dir))
        monkeypatch.setattr(ex.resolver, "get_public_directory", lambda d=None: str(public_dir))

        result = ex.finalize_pledge_if_needed(
            last_output_path=str(last_output),
            date_str="20260420",
        )
        assert result is True
        final = daily_dir / "5质押20260420.xlsx"
        assert final.exists()
        # public 同步
        assert (public_dir / "5质押20260420.xlsx").exists()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py::TestFinalizePledgeIfNeeded -v
```

预期：`AttributeError: 'WorkflowExecutor' object has no attribute 'finalize_pledge_if_needed'`

- [ ] **Step 3: 新增 `finalize_pledge_if_needed`**

在 `workflow_executor.py` 的 `_load_pledge_baseline` 之后插入：

```python
    def finalize_pledge_if_needed(
        self,
        last_output_path: Optional[str],
        date_str: Optional[str] = None,
    ) -> bool:
        """质押工作流 run_workflow 循环末尾调用一次。

        - 非质押类型：立即 return False
        - 读 last_output_path 为 DataFrame → 走 finalize → 同步 public
        - 失败仅 warning，不抛
        """
        if self.workflow_type != "质押":
            return False
        if not last_output_path or not os.path.exists(last_output_path):
            logger.warning(f"[质押 finalize] last output 不存在，跳过: {last_output_path}")
            return False
        try:
            df = pd.read_excel(last_output_path)
            daily_dir = self.resolver.get_daily_dir(date_str)
            public_dir = self.resolver.get_public_directory(date_str)
            output_name = f"5质押{date_str}.xlsx"
            output_path = os.path.join(daily_dir, output_name)
            self._finalize_pledge_output(df, date_str, output_path, public_dir)
            self._sync_pledge_final_to_public(output_path, date_str)
            return True
        except Exception as e:
            logger.error(f"[质押 finalize] 失败: {e}")
            return False
```

- [ ] **Step 4: 移除 `_match_sector` 末尾的重复 sync（L1288）**

Read `workflow_executor.py:1280-1295` 确认上下文，删除形如：
```python
            self._sync_pledge_final_to_public(output_path, date_str)
```
的单行（只删除这一行，保留其他逻辑）。

- [ ] **Step 5: 移除 `_pledge_trend_analysis` 末尾的重复 sync（L2371）**

同理，Read `workflow_executor.py:2365-2380` 确认，删除 `self._sync_pledge_final_to_public(output_path, date_str)` 单行。

- [ ] **Step 6: 在 `run_workflow` 循环后挂载调用**

Read `backend/api/workflows.py:445-510` 确认当前循环结束位置。在循环 `for i, step in enumerate(steps):` 结束之后、`if full_success:` 或类似的成功判断之前插入：

```python
        # 质押工作流 finalize：重排列 / 分 sheet / 条件格式 / 同步 public
        try:
            last_output = None
            if last_exec_result:
                data = last_exec_result.get("data") or {}
                last_output = data.get("output_path")
            if last_output:
                executor.finalize_pledge_if_needed(last_output, output_date_str)
        except Exception as _e:
            logger.warning(f"[质押 finalize] run_workflow 末尾调用失败: {_e}")
```

**注意**：`last_exec_result` 变量是现有循环用的（参考 workflows.py:445-472 片段里的 `last_exec_result = exec_result`）。`output_path` 的具体 key 要 Read 已有 `exec_result["data"]` 结构确认——若是 `"output_path"` 以外的 key，按实际改。

- [ ] **Step 7: 运行所有测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/test_pledge_finalize.py tests/test_pledge_extract_columns.py tests/test_derive_pledge_source.py tests/test_merge_excel_pledge.py tests/test_pledge_dedup_and_sync.py -v
```

预期：全部 PASS

- [ ] **Step 8: Commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add backend/services/workflow_executor.py backend/api/workflows.py backend/tests/test_pledge_finalize.py && git commit -m "feat(pledge): finalize_pledge_if_needed 由 run_workflow 末尾统一触发；移除两处重复 sync"
```

---

## Task 7: 集成回归 + 部署验证

**Files:** 无代码变更，仅运行和人工验证

- [ ] **Step 1: 跑全部后端测试**

```bash
cd /Users/xiayanji/qbox/aistock/backend && python -m pytest tests/ -v 2>&1 | tail -50
```

预期：绿色全 pass；若有红色：定位回归，修复。

- [ ] **Step 2: 部署**

```bash
cd /Users/xiayanji/qbox/aistock && ./deploy.sh build && ./deploy.sh restart
```

- [ ] **Step 3: 准备测试数据**

在 `data/excel/质押/20260422/` 下放两个 xlsx：
- `中大盘20260422.xlsx`（含 证券代码/证券简称/股权质押公告日期-20260304/质押比例-20260304/质押比例-20260420 等列，至少 3 行）
- `小盘20260422.xlsx`（同结构，至少 3 行）

在 `data/excel/质押/public/` 下保留一份历史 `5质押20260320.xlsx`（若没有，跳过，baseline 为空→全绿）。

- [ ] **Step 4: 前端触发质押工作流（date=20260422，全选步骤）**

用浏览器访问 `http://localhost:7654`，选 20260422，跑质押工作流。

- [ ] **Step 5: 检查输出文件**

打开 `data/excel/质押/20260422/5质押20260422.xlsx`：
- [ ] 有两个 sheet：`中大盘20260422` / `小盘20260422`
- [ ] 首列是 `序号`，前 7 列固定为 证券代码/证券简称/最新公告日/百日新高/站上20日线/国央企/所属板块
- [ ] 无 `来源` 列
- [ ] 有若干 `质押比例-*` 列，相邻两两对比的右侧单元格有红/绿底色（抽 1-2 行人工核对）
- [ ] 首次出现股票的 `最新公告日` 单元格为浅绿底

打开 `data/excel/质押/public/`：
- [ ] 里面只有 `5质押20260422.xlsx` 一个文件（老文件被清理）

- [ ] **Step 6: 确认不影响"站上20日均线趋势"统计**

- 打开统计分析页 → 站上20日均线趋势 → 图表加载正常
- 若有"上传"按钮，尝试上传新的 `5质押20260422.xlsx`（workflow_type=质押(双列并排)），确认两条子类型记录入库

- [ ] **Step 6.5: 第 2 次运行同一工作流验证（重要幂等性 + baseline 回读测试）**

这一步检测"上次运行写入 public 的文件能否被下次运行正确读作 baseline，以及重复运行不产生数据合并/绿标异常"。

1. 不改任何输入文件，再次在 UI 上触发同一个 `20260422` 质押工作流
2. 等待执行完毕后，重新打开 `data/excel/质押/20260422/5质押20260422.xlsx`：
   - [ ] 两 sheet 依然存在，数据行数与第 1 次相同（无合并重复、无丢失）
   - [ ] **原来首次出现绿标的最新公告日单元格现在应该不再绿**（因为第 1 次写 public 后，这些公告日已成为 baseline）
   - [ ] 质押比例红/绿对比与第 1 次一致（着色逻辑不依赖 baseline）
   - [ ] `data/excel/质押/public/` 仍然只有 `5质押20260422.xlsx` 一个文件（未叠加）
3. 若某行绿标仍在 → 说明 baseline 回读逻辑有 bug（可能 `_load_pledge_baseline` 没扫到公共文件或日期解析失败），排查 logs `[质押 baseline]` warning

- [ ] **Step 7: 更新 codebase.md / CLAUDE.md 经验教训**

在 `CLAUDE.md` 的 "经验教训" 末尾追加：

```
6. 质押工作流 final 输出样式（条件格式 + 绿标）必须仅在 `_finalize_pledge_output` 一次性施加；中间步骤如 match_* 的 `to_excel` 会清除 openpyxl 样式，所以早期施加的样式会消失。final 调用统一由 `api/workflows.py::run_workflow` 循环末尾的 `executor.finalize_pledge_if_needed` 触发，避免多步末尾重复 sync。
```

- [ ] **Step 8: 最终 commit**

```bash
cd /Users/xiayanji/qbox/aistock && git add CLAUDE.md && git commit -m "docs: 质押 finalize 经验教训"
```

---

## 执行总览

| Task | 产物 | 测试文件 |
|---|---|---|
| 1 | `_derive_pledge_source(file_name, sheet_name)` | test_derive_pledge_source.py |
| 2 | `_extract_columns_pledge` | test_pledge_extract_columns.py |
| 3 | `_finalize_pledge_output` 布局 | test_pledge_finalize.py (Layout) |
| 4 | 质押比例红绿条件格式 | test_pledge_finalize.py (Ratio) |
| 5 | Baseline + 最新公告日绿标 | test_pledge_finalize.py (FirstAppearance) |
| 6 | `finalize_pledge_if_needed` + run_workflow 挂载 + 移除两处重复 sync | test_pledge_finalize.py (IfNeeded) |
| 7 | 集成回归 + 部署 | 人工验证 |

**总计新增测试**：22 个（7 + 4 + 5 + 6 + 4 + 2 = 28，但 IfNeeded 有 2 个集成 + 约 26 单元）

**回滚策略**：每个 Task 一个 commit；出问题时 `git revert <sha>` 粒度回退。
