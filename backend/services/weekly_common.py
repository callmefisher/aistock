"""本周类工作流（13/14/18号表）公共逻辑（独立文件，供三个工作流实现复用）。

三个工作流共享的规则：
1. 目标文件解析（35天回溯，含数据日期当日）：
   - 数据日期目录下已有文件 → 直接在该文件上编辑（优先默认名，其次最新修改时间的文件）；
   - 数据日期目录为空 → 向前回溯最多35个日期（含当日共35个），取最近一个有文件的日期，
     拷贝其最新文件到数据日期目录并重命名为默认名，只在新副本上编辑（老文件不动）；
   - 35日内均无文件 → 全新生成默认名文件。
2. 公共数据源文件定位：{base_dir}/{date}/{sub_dir}/ 下最新修改时间的 Excel；
3. 全部A股行业列映射：表头含指定标记（如「[行业类别]全部」）的列 → 证券代码 → 值，
   mtime 缓存（与 monthly_ai_summary.load_all_a_sector_map 同一套缓存策略）。

效率要点：工作簿单次加载单次保存；缓存 mtime 失效。
"""

import os
import glob
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from utils.stock_code_normalizer import normalize_stock_code

logger = logging.getLogger(__name__)

# 目标文件回溯扫描天数（含数据日期当日，共 LOOKBACK_DAYS 个日期）
LOOKBACK_DAYS = 35


# ======================================================================
# 日期工具
# ======================================================================

def scan_back_dates(date_str: str, days: int = LOOKBACK_DAYS) -> List[str]:
    """从 date_str（含）起向前生成 days 个日期串（YYYY-MM-DD），从近到远。"""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return [date_str] if date_str else []
    return [(d - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def mmdd_of(date_str: str) -> str:
    """'2026-10-15' → '1015'"""
    return date_str[5:7] + date_str[8:10]


# ======================================================================
# 文件定位
# ======================================================================

def list_excel_files(dir_path: str) -> List[str]:
    """目录下的 Excel 文件名列表（跳过 Office 锁文件 ~$，按文件名排序保证稳定）。"""
    if not os.path.isdir(dir_path):
        return []
    out = []
    for ext in ("*.xlsx", "*.xls"):
        for fp in glob.glob(os.path.join(dir_path, ext)):
            name = os.path.basename(fp)
            if name.startswith("~"):
                continue
            out.append(name)
    return sorted(out)


def latest_file_by_mtime(dir_path: str, filenames: List[str]) -> Optional[str]:
    """按修改时间取最新文件，返回完整路径。"""
    if not filenames:
        return None
    return max(
        (os.path.join(dir_path, f) for f in filenames),
        key=lambda p: os.path.getmtime(p),
    )


def find_public_source_file(base_dir: str, date_str: str, sub_dir: str) -> Optional[str]:
    """公共数据源：{base_dir}/{date_str}/{sub_dir}/ 下最新修改时间的 Excel 路径（无则 None）。"""
    dir_path = os.path.join(base_dir, date_str, sub_dir)
    names = list_excel_files(dir_path)
    return latest_file_by_mtime(dir_path, names)


def is_readable_xlsx(path: str) -> bool:
    """验证 Excel 文件可读（损坏/占位文件返回 False，用于目标文件解析降级）。"""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(path, read_only=True)
        wb.close()
        return True
    except Exception as e:
        logger.warning(f"[weekly] 文件不可读(跳过): {path}, {e}")
        return False


def resolve_daily_output_file(base_dir: str, date_str: str, out_subdir: str,
                              default_name: str, log_tag: str = "") -> Tuple[str, str]:
    """本周类工作流目标文件解析（35天回溯规则，含数据日期当日）。

    统一采用「拷贝 + 当前数据日期命名」语义（老文件一律不动，只在新文件上编辑）：
    - 数据日期目录下已有文件：
      * 有默认名文件且可读 → 直接编辑该文件（同日重复执行的同名强制覆盖更新）；
      * 默认名文件损坏 → 警告并跳过（继续找其他候选，不因坏文件阻断工作流）；
      * 其他可读文件 → 拷贝最新一个并重命名为默认名，在新副本上编辑；
    - 数据日期目录无可读文件 → 从近到远回溯 LOOKBACK_DAYS-1 个历史日期，
      拷贝最近一个可读文件到数据日期目录、重命名为默认名；
    - 35日内均无可读文件 → 全新生成（路径=数据日期目录/默认名）。

    返回 (目标文件路径, 模式)，模式 ∈ {"reuse", "copy", "new"}。
    """
    import shutil

    tag = log_tag or "weekly"
    out_dir = os.path.join(base_dir, date_str, out_subdir)
    names = list_excel_files(out_dir)

    def _copy_as_default(src: str) -> str:
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, default_name)
        shutil.copyfile(src, dst)
        return dst

    # ---- 数据日期目录 ----
    if default_name in names:
        p = os.path.join(out_dir, default_name)
        if is_readable_xlsx(p):
            logger.info(f"[{tag}] 数据日期目录已有同名可读文件，直接编辑: {default_name}")
            return p, "reuse"
        logger.warning(f"[{tag}] 数据日期目录同名文件损坏，跳过: {p}")

    others = [os.path.join(out_dir, n) for n in names if n != default_name]
    for src in sorted(others, key=lambda p: os.path.getmtime(p), reverse=True):
        if is_readable_xlsx(src):
            dst = _copy_as_default(src)
            logger.info(f"[{tag}] 数据日期目录其他文件({os.path.basename(src)})拷贝重命名为 {default_name}，在新副本上编辑")
            return dst, "copy"
        logger.warning(f"[{tag}] 数据日期目录文件损坏，跳过: {src}")

    # ---- 向前回溯（不含当日，当日目录已确认无可读文件）----
    for back_date in scan_back_dates(date_str)[1:]:
        back_dir = os.path.join(base_dir, back_date, out_subdir)
        back_names = [os.path.join(back_dir, n) for n in list_excel_files(back_dir)]
        for src in sorted(back_names, key=lambda p: os.path.getmtime(p), reverse=True):
            if is_readable_xlsx(src):
                dst = _copy_as_default(src)
                logger.info(f"[{tag}] 回溯到 {back_date}，拷贝 {os.path.basename(src)} → {default_name}，在新副本上编辑")
                return dst, "copy"
            logger.warning(f"[{tag}] 回溯 {back_date} 文件损坏，跳过: {src}")

    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, default_name), "new"


# ======================================================================
# 全部A股 行业列映射（通用标记版，mtime 缓存）
# ======================================================================

# marker → {dir_path: (目录mtime, {证券代码: 值})}；每个 marker 仅缓存全部A股目录1份，不会膨胀
_all_a_column_cache: Dict[str, Dict[str, Tuple[float, Dict[str, str]]]] = {}


def invalidate_all_a_column_cache():
    """清除全部A股行业列缓存（上传/删除文件后由API层调用）。"""
    _all_a_column_cache.clear()
    logger.info("已清除全部A股行业列缓存 (all)")


def load_all_a_column_map(base_dir: str, marker: str) -> Dict[str, str]:
    """读取 {base_dir}/全部A股/ 下文件中「表头含 marker 的列」的 证券代码 → 列值 映射。

    全部A股源文件表头为多行文本单元格（含换行），如：
        "所属行业名称\\n[行业标准]申万行业(2021)\\n[行业类别]全部\\n[截止日期]最新"
    按 marker（如 "[行业类别]全部"）定位行业列；证券代码列按含「代码」定位。
    mtime 缓存（目录下文件增删/替换必变，缓存精准失效）。
    """
    import pandas as pd

    dir_path = os.path.join(base_dir, "全部A股")
    mtime = 0.0
    if os.path.isdir(dir_path):
        mtimes = [os.path.getmtime(f) for f in glob.glob(os.path.join(dir_path, "*.xls*"))]
        mtime = max(mtimes) if mtimes else 0.0

    marker_cache = _all_a_column_cache.setdefault(marker, {})
    cached = marker_cache.get(dir_path)
    if cached and cached[0] == mtime:
        return cached[1]

    col_map: Dict[str, str] = {}
    if os.path.isdir(dir_path):
        for fp in sorted(glob.glob(os.path.join(dir_path, "*.xls*"))):
            try:
                src_df = pd.read_excel(fp, dtype=str)
            except Exception as e:
                logger.warning(f"[全部A股-{marker}] 读取失败 {fp}: {e}")
                continue
            if len(src_df.columns) == 0:
                continue
            col = next((c for c in src_df.columns if marker in str(c)), None)
            code_col = next((c for c in src_df.columns if "代码" in str(c)), None)
            if col is None or code_col is None:
                logger.warning(f"[全部A股-{marker}] 未定位到代码列或含「{marker}」的列: {fp}")
                continue
            for code_val, val in zip(src_df[code_col], src_df[col]):
                nc = normalize_stock_code(code_val)
                if not nc:
                    continue
                v = str(val).strip() if pd.notna(val) else ""
                # 双键存储（normalize键 + 纯数字键）：全部A股源代码常带 .SZ/.SH 后缀，
                # 而查询方（如18号表）代码多为纯数字，单键会 miss（板块为空的根因）
                col_map[nc] = v
                if "." in nc:
                    col_map.setdefault(nc.split(".", 1)[0], v)

    marker_cache[dir_path] = (mtime, col_map)
    logger.info(f"[全部A股-{marker}] 加载并缓存 {len(col_map)} 只股票映射 (mtime={mtime})")
    return col_map


# ======================================================================
# 表格读写工具（openpyxl 值级复制，保持单元格原值）
# ======================================================================

def read_sheet_rows(path: str, sheet_name: Optional[str] = None) -> List[List]:
    """读取指定 sheet 的全部行（值），sheet_name 为 None 时优先「筛选结果」否则首个 sheet。

    返回行列表（含表头行）；文件无该 sheet 或损坏不可读时返回空列表（由调用方按无数据处理）。"""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        logger.warning(f"[weekly] 数据源文件不可读: {path}, {e}")
        return []
    try:
        if sheet_name is None:
            sheet_name = "筛选结果" if "筛选结果" in wb.sheetnames else wb.sheetnames[0]
        if sheet_name not in wb.sheetnames:
            return []
        ws = wb[sheet_name]
        rows: List[List] = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
        return rows
    finally:
        wb.close()


def write_rows_to_sheet(ws, rows: List[List]):
    """将行列表（含表头）逐格写入 sheet（值级复制，不覆盖已有内容时由调用方新建 sheet）。"""
    for row in rows:
        ws.append([("" if v is None else v) for v in row])
