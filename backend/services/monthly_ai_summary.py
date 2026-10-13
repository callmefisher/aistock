"""本月AI筛选汇总工作流实现（独立文件，避免 workflow_executor.py 过大难维护）。

数据流：
1. 从 DB(workflow_results「当月每日新增」final，首sheet=当月每日新增) 读取数据日期当日证券代码，
   Excel(data/excel/当月每日新增/{YYYY}年{M}月新增/*{MMDD}*.xlsx 首sheet) 兜底；
2. 用「全部A股」目录文件(data/excel/全部A股/)的申万1级/2级行业列匹配 一级板块/二级板块；
3. 输出到 data/excel/{YYYY-MM}/16 {M}月AI筛选汇总{MMDD}.xlsx：
   - 目录为空→新建；有同名→直接填充；非空无同名→复制最新日期文件为新名（按文件名日期选最新）；
   - Sheet1：一级板块/二级板块 × 日期 两张统计表 + 两张彩色折线图（表头宋体14桔黄底，数据宋体11，黑边框），
     数值 = 从首列起的「当日新增」累计和（10月8日新增3、10月9日新增0、10月10日新增1 → 各列 3、3、4），
     累计为0时单元格留空；增量更新——已有日期列内容/板块行序保持原样不动，当日新板块追加表尾，
     当日日期列已存在则仅刷新该列（= 前列累计 + 当日新增），否则新增一列；图表按新表尺寸重建；
   - 日期sheet（MMDD命名，如 1012）：证券代码 + 一级板块 + 二级板块，按数据日期强制覆盖，
     最新日期sheet排在Sheet1之后（降序：Sheet1, 1012, 1009, ...）。

本模块另承载两类共享只读源缓存（mtime失效，上传/删除后主动失效）：
- 39日新高：date_str → 证券代码集合（仅"股票代码/证券代码"列），仅保留最近2天，供条件交集"39日新高"标记列使用；
- 全部A股板块映射：全局仅1份，不会膨胀。

另：「本月AI筛选20日线汇总」(monthly_ai_ma20_summary.py) 复用本模块的
load_all_a_sector_map / _update_summary_sheet / _reorder_sheets / _resolve_output_path（参数化前缀与关键字）。

效率要点：全部A股/39日新高读取带缓存；匹配用向量化 isin；工作簿单次加载单次保存；
聚合直接遍历内存中sheet的 values_only 行；样式对象复用（openpyxl样式为不可变共享对象）。
"""

import os
import re
import glob
import json
import zlib
import shutil
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from utils.stock_code_normalizer import normalize_stock_code

logger = logging.getLogger(__name__)

# ======================================================================
# 缓存（模块级）与失效函数（上传/删除文件后由API层调用）
# ======================================================================

# 39日新高源缓存：date_str → (目录mtime, 证券代码集合)；仅保留最近2个日期，避免无限膨胀
_high39_cache: Dict[str, Tuple[float, Set[str]]] = {}
_HIGH39_CACHE_MAX_DATES = 2
# 全部A股板块缓存：dir_path → (目录mtime, {证券代码: (一级板块, 二级板块)})；全局仅1份不会膨胀
_all_a_sector_cache: Dict[str, Tuple[float, Dict[str, Tuple[str, str]]]] = {}


def invalidate_39day_high_cache(dir_path: str = None):
    """清除39日新高源缓存。缓存最多2个日期键且有mtime校验兜底，全清代价可忽略。"""
    _high39_cache.clear()
    logger.info(f"已清除39日新高缓存 ({dir_path or 'all'})")


def invalidate_all_a_cache(dir_path: str = None):
    """清除全部A股板块缓存（全局仅1份）。"""
    if dir_path:
        keys_to_remove = [k for k in _all_a_sector_cache if k.startswith(dir_path)]
        for k in keys_to_remove:
            del _all_a_sector_cache[k]
        logger.info(f"已清除全部A股板块缓存: {dir_path}")
    else:
        _all_a_sector_cache.clear()
        logger.info("已清除所有全部A股板块缓存")


def _get_dir_mtime(dir_path: str) -> float:
    """目录下所有Excel文件的最大修改时间（文件增删/替换都会变，作为缓存精准失效依据）"""
    if not os.path.isdir(dir_path):
        return 0.0
    mtimes = [os.path.getmtime(f) for f in glob.glob(os.path.join(dir_path, "*.xls*"))]
    return max(mtimes) if mtimes else 0.0


# ======================================================================
# 39日新高 / 全部A股 只读源加载（带缓存）
# ======================================================================

def load_39day_high_codes(base_dir: str, date_str: str) -> Set[str]:
    """读取 {base_dir}/{date_str}/39日新高/ 下全部文件的证券代码集合。

    匹配规则：只用证券代码去匹配源文件「股票代码」列或「证券代码」列（其他列不参与）。
    缓存：按日期键 + 目录mtime双保险失效；仅保留最近2个日期，防止无限膨胀。
    """
    dir_path = os.path.join(base_dir, date_str, "39日新高")
    mtime = _get_dir_mtime(dir_path)
    cached = _high39_cache.get(date_str)
    if cached and cached[0] == mtime:
        return cached[1]

    codes: Set[str] = set()
    if os.path.isdir(dir_path):
        for fp in sorted(glob.glob(os.path.join(dir_path, "*.xls*"))):
            try:
                src_df = pd.read_excel(fp, dtype=str)
            except Exception as e:
                logger.warning(f"[39日新高] 读取失败 {fp}: {e}")
                continue
            # 只认「股票代码」列或「证券代码」列（要求：仅用证券代码匹配这两列）
            code_col = next((c for c in ("股票代码", "证券代码") if c in src_df.columns), None)
            if code_col is None:
                logger.warning(f"[39日新高] 未找到股票代码/证券代码列(列={list(src_df.columns)[:6]}): {fp}")
                continue
            for v in src_df[code_col]:
                nc = normalize_stock_code(v)
                if nc:
                    codes.add(nc)
                    if "." in nc:  # 纯数字键兜底（如 000009 ↔ 000009.SZ）
                        codes.add(nc.split(".", 1)[0])

    _high39_cache[date_str] = (mtime, codes)
    # 容量控制：仅保留最近2个日期（日期串字典序=时间序）
    if len(_high39_cache) > _HIGH39_CACHE_MAX_DATES:
        for k in sorted(_high39_cache)[:-_HIGH39_CACHE_MAX_DATES]:
            _high39_cache.pop(k, None)
    logger.info(f"[39日新高] {date_str}: 加载{len(codes)}个代码键 (mtime={mtime})")
    return codes


def load_all_a_sector_map(base_dir: str) -> Dict[str, Tuple[str, str]]:
    """读取 {base_dir}/全部A股/ 下文件的 证券代码 → (一级板块, 二级板块) 映射。

    源文件表头为多行文本单元格（含换行），形如：
        "所属行业名称\\n[行业标准]申万行业(2021)\\n[行业类别]1级\\n[截止日期]最新"
    按表头含 [行业类别]1级 / [行业类别]2级 定位板块列；证券代码列按含「代码」定位。
    mtime缓存，全局仅1份（上传时目录先清空只留最新文件，目录mtime必变，缓存精准失效）。
    """
    dir_path = os.path.join(base_dir, "全部A股")
    mtime = _get_dir_mtime(dir_path)
    cached = _all_a_sector_cache.get(dir_path)
    if cached and cached[0] == mtime:
        return cached[1]

    sector_map: Dict[str, Tuple[str, str]] = {}
    if os.path.isdir(dir_path):
        for fp in sorted(glob.glob(os.path.join(dir_path, "*.xls*"))):
            try:
                src_df = pd.read_excel(fp, dtype=str)
            except Exception as e:
                logger.warning(f"[全部A股] 读取失败 {fp}: {e}")
                continue
            if len(src_df.columns) == 0:
                continue

            def _find_col(marker: str) -> Optional[str]:
                for c in src_df.columns:
                    if marker in str(c):
                        return c
                return None

            l1_col = _find_col("[行业类别]1级")
            l2_col = _find_col("[行业类别]2级")
            code_col = next((c for c in src_df.columns if "代码" in str(c)), None)
            if code_col is None or (l1_col is None and l2_col is None):
                logger.warning(f"[全部A股] 未定位到代码列或1/2级板块列(列={list(src_df.columns)[:8]}): {fp}")
                continue

            l1_series = src_df[l1_col] if l1_col is not None else pd.Series([""] * len(src_df))
            l2_series = src_df[l2_col] if l2_col is not None else pd.Series([""] * len(src_df))
            for code_val, l1_val, l2_val in zip(src_df[code_col], l1_series, l2_series):
                nc = normalize_stock_code(code_val)
                if not nc:
                    continue
                sector_map[nc] = (
                    str(l1_val).strip() if pd.notna(l1_val) else "",
                    str(l2_val).strip() if pd.notna(l2_val) else "",
                )

    _all_a_sector_cache[dir_path] = (mtime, sector_map)
    logger.info(f"[全部A股] 加载并缓存 {len(sector_map)} 只股票板块映射 (mtime={mtime})")
    return sector_map


# ======================================================================
# 「当月每日新增」当日数据读取（DB优先，Excel兜底）
# ======================================================================

async def _load_daily_new_codes(base_dir: str, date_str: str) -> Optional[List[str]]:
    """读取数据日期当日的「当月每日新增」首个sheet（当月每日新增）证券代码。

    返回：None=完全无数据；[]=当日为空（合法，输出空sheet）；否则代码列表（去重保序）。
    """
    records = await _load_daily_new_records_from_db(date_str)
    if records is None:
        records = _read_daily_new_records_from_excel(base_dir, date_str)
    if records is None:
        return None

    codes: List[str] = []
    seen: Set[str] = set()
    for r in records:
        if not isinstance(r, dict):
            continue
        raw = str(r.get("证券代码") or "").strip()
        nc = normalize_stock_code(raw)
        if not nc or nc in seen:
            continue
        seen.add(nc)
        codes.append(raw)
    return codes


async def _load_daily_new_records_from_db(date_str: str) -> Optional[List[dict]]:
    from core.database import AsyncSessionLocal
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT data_compressed FROM workflow_results
                    WHERE workflow_type = '当月每日新增' AND step_type = 'final' AND date_str = :d
                    ORDER BY id DESC LIMIT 1
                """),
                {"d": date_str},
            )
            row = result.fetchone()
            if not row or not row[0]:
                return None
            try:
                records = json.loads(zlib.decompress(row[0]).decode("utf-8"))
            except Exception as e:
                logger.warning(f"[本月AI筛选汇总] DB记录解压失败({date_str}): {e}")
                return None
            return records if isinstance(records, list) else None
    except Exception as e:
        logger.warning(f"[本月AI筛选汇总] DB查询当月每日新增失败({date_str}): {e}")
        return None


def _read_daily_new_records_from_excel(base_dir: str, date_str: str) -> Optional[List[dict]]:
    """Excel兜底：data/excel/当月每日新增/{YYYY}年{M}月新增/ 下含 {MMDD} 的xlsx首sheet"""
    try:
        mmdd = date_str[5:7] + date_str[8:10]
        month_dir = os.path.join(base_dir, "当月每日新增", f"{date_str[:4]}年{int(date_str[5:7])}月新增")
        if not os.path.isdir(month_dir):
            return None
        candidates = [f for f in os.listdir(month_dir) if f.endswith(".xlsx") and mmdd in f and not f.startswith("~")]
        if not candidates:
            return None
        path = max(candidates, key=lambda f: os.path.getmtime(os.path.join(month_dir, f)))
        df = pd.read_excel(os.path.join(month_dir, path), sheet_name=0, dtype=str)
        if "证券代码" not in df.columns:
            return None
        return df.to_dict("records")
    except Exception as e:
        logger.warning(f"[本月AI筛选汇总] Excel兜底读取失败({date_str}): {e}")
        return None


# ======================================================================
# 主步骤：本月AI筛选汇总
# ======================================================================

# 折线图调色板（循环使用，颜色区分不同板块）
_CHART_LINE_COLORS = [
    "4472C4", "ED7D31", "A5A5A5", "FFC000", "5B9BD5", "70AD47",
    "264478", "9E480E", "636363", "997300", "255E91", "43682B",
    "C00000", "7030A0", "00B0F0", "00B050",
]
# Sheet1 样式（不可变共享对象，openpyxl允许复用，避免每格重建开销）
_HEADER_FONT = Font(name="宋体", size=14)
_DATA_FONT = Font(name="宋体", size=11)
_ORANGE_FILL = PatternFill(fill_type="solid", start_color="FFFFC000", end_color="FFFFC000")  # 桔黄色
_THIN_BLACK = Side(style="thin", color="FF000000")
_BORDER_ALL = Border(left=_THIN_BLACK, right=_THIN_BLACK, top=_THIN_BLACK, bottom=_THIN_BLACK)
_CENTER = Alignment(horizontal="center", vertical="center")

_DATE_SHEET_RE = re.compile(r"^\d{4}$")  # 日期sheet命名：MMDD，如 1009
# 输出文件名中的日期在 _resolve_output_path 内按 keyword 动态解析（16...AI筛选汇总1009 → 1009）


async def execute_monthly_ai_summary(executor, config: Dict[str, Any], date_str: Optional[str] = None) -> Dict[str, Any]:
    """本月AI筛选汇总主步骤（step_type: monthly_ai_summary）。

    executor: WorkflowExecutor 实例（使用其 base_dir / today）
    """
    date_str = (config.get("date_str") or "").strip() or date_str or executor.today
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str or ""):
        return {"success": False, "message": f"数据日期格式错误: {date_str}（需YYYY-MM-DD）"}

    mmdd = date_str[5:7] + date_str[8:10]
    month_int = int(date_str[5:7])
    month_root = date_str[:7]  # 如 2026-10

    # 1) 当日「当月每日新增」数据（只要首sheet）
    codes = await _load_daily_new_codes(executor.base_dir, date_str)
    if codes is None:
        return {
            "success": False,
            "message": f"数据日期({date_str})无「当月每日新增」数据（DB与Excel均未找到），请先执行「当月每日新增」工作流",
        }

    # 2) 全部A股板块映射（缓存）
    warnings: List[str] = []
    try:
        sector_map = load_all_a_sector_map(executor.base_dir)
    except Exception as e:
        sector_map = {}
        logger.warning(f"[本月AI筛选汇总] 读取全部A股失败: {e}")
    if not sector_map:
        warnings.append("未找到 data/excel/全部A股/ 有效文件，「一级板块/二级板块」列将为空")

    # 3) 日期sheet行：证券代码 + 一级板块 + 二级板块（向量化匹配）
    if sector_map and codes:
        norm_series = pd.Series([normalize_stock_code(c) for c in codes], dtype=object)
        l1_series = norm_series.map(lambda nc: sector_map.get(nc, ("", ""))[0])
        l2_series = norm_series.map(lambda nc: sector_map.get(nc, ("", ""))[1])
        rows = list(zip(codes, l1_series.tolist(), l2_series.tolist()))
        matched_l1 = int((l1_series != "").sum())
        matched_l2 = int((l2_series != "").sum())
    else:
        rows = [(c, "", "") for c in codes]
        matched_l1 = matched_l2 = 0

    # 4) 目标文件：目录为空→新建；有同名→直接填充；非空无同名→复制最新日期文件为新名
    out_dir = os.path.join(executor.base_dir, month_root)
    os.makedirs(out_dir, exist_ok=True)
    default_name = f"16 {month_int}月AI筛选汇总{mmdd}.xlsx"
    output_filename = (config.get("output_filename") or "").strip() or default_name
    output_filename = output_filename.replace("{date}", date_str).replace("{mmdd}", mmdd)
    if not output_filename.endswith(".xlsx"):
        output_filename += ".xlsx"
    target_path, path_mode = _resolve_output_path(out_dir, output_filename)

    # 5) 打开/创建工作簿 → 强制覆盖日期sheet → 增量更新Sheet1 → 重排 → 保存
    file_existed = path_mode != "new"
    wb = load_workbook(target_path) if file_existed else Workbook()
    try:
        if not file_existed and wb.sheetnames == ["Sheet"]:
            wb.remove(wb.active)  # 移除默认空sheet，稍后由 Sheet1/日期sheet 重建

        # 日期sheet（强制覆盖同名）
        if mmdd in wb.sheetnames:
            del wb[mmdd]
        ws_date = wb.create_sheet(mmdd)
        ws_date.append(["证券代码", "一级板块", "二级板块"])
        for row in rows:
            ws_date.append(list(row))
        ws_date.column_dimensions["A"].width = 14
        ws_date.column_dimensions["B"].width = 18
        ws_date.column_dimensions["C"].width = 18
        ws_date.freeze_panes = "A2"

        # Sheet1 增量更新（已有列内容/行序保持，新板块追加，当日列追加或刷新，图表重建）
        _update_summary_sheet(wb, mmdd)

        # 重排：Sheet1, 日期sheet降序(1012, 1009, 1008...), 其他
        _reorder_sheets(wb)

        wb.save(target_path)
    except Exception as e:
        logger.error(f"[本月AI筛选汇总] 写入失败 {target_path}: {e}")
        return {"success": False, "message": f"生成Excel失败: {e}"}

    logger.info(f"[本月AI筛选汇总] 输出 {target_path} (sheet {mmdd}: {len(rows)}行, 模式={path_mode})")

    mode_label = {"new": "新建", "reuse": "复用已有", "copy": "基于最新文件复制为"}[path_mode]
    message = (
        f"本月AI筛选汇总完成: 数据日期{date_str}，sheet「{mmdd}」{len(rows)}个证券代码，"
        f"一级板块匹配{matched_l1}个/二级板块匹配{matched_l2}个，"
        f"{mode_label}文件 {os.path.basename(target_path)}"
    )
    if warnings:
        message += "；" + "；".join(warnings)

    # 预览数据（日期sheet内容）
    from services.workflow_executor import clean_df_for_json  # 延迟导入避免循环依赖
    preview_df = pd.DataFrame(rows, columns=["证券代码", "一级板块", "二级板块"])
    return {
        "success": True,
        "message": message,
        "data": clean_df_for_json(preview_df),
        "columns": ["证券代码", "一级板块", "二级板块"],
        "rows": len(rows),
        "file_path": target_path,
        "warnings": warnings,
        "_df": preview_df,
    }


def _resolve_output_path(out_dir: str, default_name: str, prefix: str = "16",
                         keyword: str = "AI筛选汇总", log_tag: str = "本月AI筛选汇总") -> Tuple[str, str]:
    """目标文件解析（确认后的规则）：
    - 目录为空 → 全新创建 default_name；
    - 目录已有同名文件 → 直接在该文件上填充（不新建）；
    - 目录非空但无同名 → 复制「最新日期」的已有文件为 default_name，在副本上填充
      （例：目录下有 0305/0306/0307，则复制 0307 为新数据日期文件名）。
      最新日期按文件名中 keyword（如「AI筛选汇总」）后的4位数字判断，解析失败按 mtime 兜底。
    prefix/keyword 供「本月AI筛选20日线汇总」复用（19 / AI筛选20日线汇总）。
    返回 (目标路径, 模式)，模式 ∈ {"new", "reuse", "copy"}。"""
    candidates = [
        f for f in os.listdir(out_dir)
        if f.endswith(".xlsx") and f.startswith(prefix) and keyword in f and not f.startswith("~")
    ] if os.path.isdir(out_dir) else []
    if not candidates:
        return os.path.join(out_dir, default_name), "new"
    if default_name in candidates:
        return os.path.join(out_dir, default_name), "reuse"

    date_re = re.compile(keyword + r"(\d{4})")

    def _name_date(f: str) -> str:
        m = date_re.search(f)
        return m.group(1) if m else ""

    named = [(f, _name_date(f)) for f in candidates]
    with_date = [t for t in named if t[1]]
    if with_date:
        latest = max(with_date, key=lambda t: t[1])[0]
    else:
        latest = max(candidates, key=lambda f: os.path.getmtime(os.path.join(out_dir, f)))
    src = os.path.join(out_dir, latest)
    dst = os.path.join(out_dir, default_name)
    shutil.copyfile(src, dst)
    logger.info(f"[{log_tag}] 目录无同名文件，已复制最新文件 {latest} → {default_name}")
    return dst, "copy"


def _date_label(mmdd: str) -> str:
    """1008 → 10月8日"""
    return f"{int(mmdd[:2])}月{int(mmdd[2:])}日"


def _aggregate_one_sheet(ws) -> Tuple[Dict[str, int], Dict[str, int]]:
    """单个日期sheet → (一级板块→数量, 二级板块→数量)。dict保序=板块首次出现顺序。
    兼容空sheet：仅表头或无数据行时为空dict，不报错。"""
    l1: Dict[str, int] = {}
    l2: Dict[str, int] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        l1v = str(row[1]).strip() if len(row) > 1 and row[1] is not None and str(row[1]) != "nan" else ""
        l2v = str(row[2]).strip() if len(row) > 2 and row[2] is not None and str(row[2]) != "nan" else ""
        if l1v:
            l1[l1v] = l1.get(l1v, 0) + 1
        if l2v:
            l2[l2v] = l2.get(l2v, 0) + 1
    return l1, l2


def _collect_date_sheet_stats(wb) -> Tuple[List[str], List[Tuple[str, list]], List[Tuple[str, list]]]:
    """聚合所有 MMDD 日期sheet → (升序日期列表, 一级板块行, 二级板块行)。
    板块行 = (板块名, [各日期计数])，板块顺序=首次出现顺序。
    计数含义：某板块在该日期sheet中出现的证券代码行数。"""
    date_sheets = [ws for ws in wb.worksheets if _DATE_SHEET_RE.match(ws.title)]
    date_sheets.sort(key=lambda ws: (int(ws.title[:2]), int(ws.title[2:])))  # 升序（从低到高）
    dates = [ws.title for ws in date_sheets]

    l1_per: Dict[str, Dict[str, int]] = {}  # 板块 → {mmdd: 数量}
    l2_per: Dict[str, Dict[str, int]] = {}
    for ws in date_sheets:
        l1, l2 = _aggregate_one_sheet(ws)
        for k, v in l1.items():
            l1_per.setdefault(k, {})[ws.title] = v
        for k, v in l2.items():
            l2_per.setdefault(k, {})[ws.title] = v

    # 每行数值 = 从首个日期列起的「当日新增」累计和（例：10月8日新增3 → 3；10月9日新增0 → 3；10月10日新增1 → 4）
    def _cumulative(rows_per):
        out = []
        for s, per in rows_per.items():
            total = 0
            cum = []
            for m in dates:
                total += int(per.get(m, 0))
                cum.append(total)
            out.append((s, cum))
        return out

    return dates, _cumulative(l1_per), _cumulative(l2_per)


def _write_stat_table(ws, start_row: int, header_label: str, date_labels: List[str],
                      table_rows: List[Tuple[str, list]]) -> Tuple[int, int]:
    """写一张统计表（A列板块名 + 日期列计数），返回(结束行号, 总列数)。

    date_labels：直接作为日期列表头的显示文本（如 "10月8日"）。
    样式：第一行宋体14+桔黄底；其余宋体11；全部黑细边框（黑线区分表格与非表格区域）。
    """
    n_dates = len(date_labels)
    # 表头
    ws.cell(row=start_row, column=1, value=header_label)
    for j, label in enumerate(date_labels):
        ws.cell(row=start_row, column=2 + j, value=label)
    # 数据行
    for i, (sector, vals) in enumerate(table_rows):
        r = start_row + 1 + i
        ws.cell(row=r, column=1, value=sector)
        for j, v in enumerate(vals):
            # 累计值为0 → 不填充内容，显示为空
            ws.cell(row=r, column=2 + j, value=(v if v else None))
    # 样式 + 边框（对象复用，见模块常量）
    end_row = start_row + len(table_rows)
    for r in range(start_row, end_row + 1):
        for c in range(1, 2 + n_dates):
            cell = ws.cell(row=r, column=c)
            cell.font = _HEADER_FONT if r == start_row else _DATA_FONT
            if r == start_row:
                cell.fill = _ORANGE_FILL
            cell.border = _BORDER_ALL
            cell.alignment = _CENTER
    return end_row, 1 + n_dates


def _add_trend_chart(ws, anchor: str, title: str, header_row: int, n_dates: int, n_rows: int):
    """为一张统计表生成彩色折线图：横坐标=日期(低→高)，纵坐标=数量，每条折线一个板块。

    系列名=板块名（鼠标点击折线/查看图例即可辨识板块）。"""
    from openpyxl.chart import LineChart, Reference, Series

    chart = LineChart()
    chart.title = title
    chart.style = 13
    chart.y_axis.title = "数量"
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    # 空单元格(累计0留空)按0绘制，保证曲线连续（例：10月8日空、10月9日5 → 0→5 的线段，而非孤点）
    chart.display_blanks = "zero"

    cats = Reference(ws, min_col=2, max_col=1 + n_dates, min_row=header_row, max_row=header_row)
    for i in range(n_rows):
        r = header_row + 1 + i
        values = Reference(ws, min_col=2, max_col=1 + n_dates, min_row=r, max_row=r)
        series = Series(values, title=str(ws.cell(row=r, column=1).value or f"系列{i + 1}"))
        color = _CHART_LINE_COLORS[i % len(_CHART_LINE_COLORS)]
        series.graphicalProperties.line.solidFill = color
        series.graphicalProperties.line.width = 22000  # ~1.75pt
        series.marker.symbol = "circle"
        series.marker.size = 5
        series.smooth = False
        chart.series.append(series)
    chart.set_categories(cats)
    chart.width = 22
    chart.height = 9
    ws.add_chart(chart, anchor)


def _parse_stat_table(ws, header_row: int) -> Tuple[List[str], List[Tuple[str, list]]]:
    """解析旧Sheet1统计表：返回(日期列头列表, [(板块名, [各日数值])...])。
    第2列起连续非空为日期列；板块行自表头下一行到A列空为止（表间至少空一行）。"""
    dates: List[str] = []
    c = 2
    while ws.cell(header_row, c).value not in (None, ""):
        dates.append(str(ws.cell(header_row, c).value))
        c += 1
    table_rows: List[Tuple[str, list]] = []
    r = header_row + 1
    while ws.cell(r, 1).value not in (None, ""):
        name = str(ws.cell(r, 1).value)
        vals = [ws.cell(r, 2 + j).value for j in range(len(dates))]
        table_rows.append((name, vals))
        r += 1
    return dates, table_rows


def _merge_today_into_table(old_dates: List[str], old_rows: List[Tuple[str, list]],
                            today_label: str, today_counts: Dict[str, int]) -> Tuple[List[str], List[Tuple[str, list]]]:
    """增量合并（确认后的规则，数值域 = 从首列起的「当日新增」累计值）：
    - 已有日期列数值沿用原值不动（累计值原样保留，手工修正值不覆盖）；
    - 当日列已存在（重复执行）→ 仅刷新该列；不存在 → 追加到最右；
    - 当日列 = 前一列累计值 + 当日新增（首列即当日新增本身）；
      例：10月8日新增3、10月9日新增0、10月10日新增1 → 各列展示 3、3、4；
    - 已有板块保持原顺序，当日新增板块追加到表尾（历史列累计0，写入时显示为空）。"""
    if today_label in old_dates:
        col_idx = old_dates.index(today_label)
        new_dates = list(old_dates)
    else:
        col_idx = len(old_dates)
        new_dates = list(old_dates) + [today_label]

    existing = {name for name, _ in old_rows}
    merged: List[Tuple[str, list]] = []
    for name, vals in old_rows:
        v = list(vals)[:len(new_dates)] + [None] * (len(new_dates) - len(vals))  # 补齐列数（空=累计0）
        # 前一列累计（沿用旧值，含手工修正；空单元格按0）
        prev_total = int(v[col_idx - 1] or 0) if col_idx > 0 else 0
        v[col_idx] = prev_total + int(today_counts.get(name, 0))  # 当日列 = 累计 + 当日新增
        merged.append((name, v))
    for name, cnt in today_counts.items():  # dict保序=当日新增板块出现顺序
        if name not in existing:
            v = [None] * len(new_dates)  # 该板块此前未出现：历史列累计0（写入显示为空）
            v[col_idx] = int(cnt)
            merged.append((name, v))
    return new_dates, merged


def _layout_summary_sheet(ws, l1_dates: List[str], l1_rows: List[Tuple[str, list]],
                         l2_dates: List[str], l2_rows: List[Tuple[str, list]]):
    """按给定数据写 Sheet1：两张统计表 + 两张对应折线图（布局自适应：表2随表1行数下移）。"""
    if not l1_dates:
        ws.cell(row=1, column=1, value="暂无日期数据")
        return
    n_dates = max(len(l1_dates), len(l2_dates))
    ws.column_dimensions["A"].width = 20
    for c in range(2, 2 + n_dates):
        ws.column_dimensions[get_column_letter(c)].width = 12

    # 表1 + 图1：从第1行开始
    t1_end, t1_cols = _write_stat_table(ws, 1, "一级板块", l1_dates, l1_rows)
    chart_anchor_col = get_column_letter(t1_cols + 2)  # 表右侧空一列
    _add_trend_chart(ws, f"{chart_anchor_col}1", "一级板块累计数量趋势", 1, len(l1_dates), len(l1_rows))

    # 表2 + 图2：表1结束行下方，与图1高度(约18行)错开避免重叠
    t2_start = max(t1_end + 2, 20)
    _write_stat_table(ws, t2_start, "二级板块", l2_dates, l2_rows)
    _add_trend_chart(ws, f"{chart_anchor_col}{t2_start}", "二级板块累计数量趋势", t2_start, len(l2_dates), len(l2_rows))


def _rebuild_summary_sheet(wb):
    """全新构建 Sheet1（从所有日期sheet全量聚合）——用于目标文件中无 Sheet1 的场景。"""
    dates, l1_rows, l2_rows = _collect_date_sheet_stats(wb)
    if "Sheet1" in wb.sheetnames:
        del wb["Sheet1"]
    ws = wb.create_sheet("Sheet1", 0)
    labels = [_date_label(m) for m in dates]  # 表头显示文本（与增量路径解析旧表头的口径一致）
    _layout_summary_sheet(ws, labels, l1_rows, labels, l2_rows)


def _update_summary_sheet(wb, mmdd: str):
    """Sheet1 增量更新（确认后的规则，数值 = 从首列起的「当日新增」累计和）：
    - 已有日期列内容沿用原值不动（历史sheet异常/缺失也不会改变已填充的列）；
    - 已有板块行顺序保持原样，当日新增的一级/二级板块追加到对应表尾（历史列累计0，显示为空）；
    - 当日日期列已存在（重复执行）则仅刷新该列（= 前列累计 + 当日新增），否则新增一列；
    - 累计为0的单元格写入留空；两张折线图按新表尺寸重建（数据引用覆盖全部行/列）；
    - 无 Sheet1（全新文件）或结构异常 → 全量聚合构建兜底。
    """
    if mmdd not in wb.sheetnames:
        return
    l1_today, l2_today = _aggregate_one_sheet(wb[mmdd])
    today_label = _date_label(mmdd)

    if "Sheet1" not in wb.sheetnames:
        _rebuild_summary_sheet(wb)
        return

    ws_old = wb["Sheet1"]
    # 表1表头固定第1行；表2表头按A列值「二级板块」定位
    t2_header = next((r for r in range(2, ws_old.max_row + 1)
                      if ws_old.cell(r, 1).value == "二级板块"), None)
    l1_dates, l1_rows = _parse_stat_table(ws_old, 1)
    if t2_header is None or not l1_dates:
        logger.warning("[本月AI筛选汇总] 旧Sheet1结构异常，全量重建兜底")
        _rebuild_summary_sheet(wb)
        return
    l2_dates, l2_rows = _parse_stat_table(ws_old, t2_header)

    l1_dates_m, l1_rows_m = _merge_today_into_table(l1_dates, l1_rows, today_label, l1_today)
    l2_dates_m, l2_rows_m = _merge_today_into_table(l2_dates, l2_rows, today_label, l2_today)

    # 物理重写Sheet1（布局自适应），数值层沿用旧值
    wb.remove(ws_old)
    ws = wb.create_sheet("Sheet1", 0)
    _layout_summary_sheet(ws, l1_dates_m, l1_rows_m, l2_dates_m, l2_rows_m)


def _reorder_sheets(wb):
    """重排：Sheet1 → 日期sheet降序（最新在前，如 1012, 1009, 1008）→ 其他"""
    date_sheets = [ws for ws in wb.worksheets if _DATE_SHEET_RE.match(ws.title)]
    others = [ws for ws in wb.worksheets if not _DATE_SHEET_RE.match(ws.title)]
    sheet1 = next((ws for ws in others if ws.title == "Sheet1"), None)
    rest = [ws for ws in others if ws.title != "Sheet1"]
    date_sheets.sort(key=lambda ws: (int(ws.title[:2]), int(ws.title[2:])), reverse=True)
    wb._sheets = ([sheet1] if sheet1 else []) + date_sheets + rest
    if wb._sheets:
        wb.active = 0
