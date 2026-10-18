"""工作流：全部A股总市值大于800亿（18号表）。

规则（数据日期 date_str，回溯35天含当日）：
- 输出文件：{base_dir}/{date}/全部A股800亿输出/18 全部A股总市值大于800亿{MMDD}.xlsx（同名强制覆盖更新）
- 目标文件解析：35天回溯（数据日期已有文件直接编辑；否则取最近35日内最新文件拷贝重命名；都没有则全新生成）；
- 数据源 B = 公共文件 {base_dir}/{date}/全部A股800亿/；与 18号表 A 对比：
  B 中新增的证券代码 → 将该行前3列复制到 A 的最下面（作为新增行）；
- 「板块」列：已存在则不重复新增，否则在C列之后插入；仅对新增行填充——
  用行内证券代码匹配 全部A股 公共目录文件的「[行业类别]全部」列（表头多行文本标记），匹配成功拷贝其值；
- 「{M}/{D}\\n39日新高」列（日期在上、39日新高在下）：在「板块」列之后插入（同日期列已存在则复用，不重复插入），
  仅对新增行填充——行内证券代码在当日 39日新高 公共数据中命中时，填入该证券代码；
- 其他已有列与数据行均不修改。

复用 weekly_common（35天目标文件解析/公共数据源定位/全部A股行业列映射）
与 monthly_ai_summary.load_39day_high_codes（39日新高代码集合，已有逻辑）。
"""

import logging
import re
from typing import List, Optional

from openpyxl import Workbook, load_workbook

from services.monthly_ai_summary import load_39day_high_codes
from services.weekly_common import (
    find_public_source_file,
    load_all_a_column_map,
    mmdd_of,
    read_sheet_rows,
    resolve_daily_output_file,
)
from utils.stock_code_normalizer import normalize_stock_code

logger = logging.getLogger(__name__)

# 18号表目标输出子目录
OUT_SUBDIR = "全部A股800亿输出"
# 公共数据源子目录
PUBLIC_SUBDIR = "全部A股800亿"
# 默认输出文件名模板
DEFAULT_FILENAME_TEMPLATE = "18 全部A股总市值大于800亿{MMDD}.xlsx"
# 全部A股 行业列标记（[行业类别]全部）
ALL_A_INDUSTRY_MARKER = "[行业类别]全部"

NEW_ROW_COPY_COLS = 3  # 新增行仅复制数据源行的前3列
SECTOR_COL_NAME = "板块"


def build_default_filename(date_str: str) -> str:
    """数据日期 → 默认输出文件名，如 2026-10-15 → 18 全部A股总市值大于800亿1015.xlsx"""
    return DEFAULT_FILENAME_TEMPLATE.replace("{MMDD}", mmdd_of(date_str))


def resolve_output_filename(config: dict, date_str: str) -> str:
    """解析输出文件名：优先使用配置（前端可编辑），否则按数据日期生成默认名。"""
    configured = (config.get("output_filename") or "").strip()
    if configured:
        return configured.replace("{MMDD}", mmdd_of(date_str))
    return build_default_filename(date_str)


def _find_code_col_index(header: List) -> int:
    """定位代码列索引（0起）：优先「股票代码」，其次「证券代码」，否则第0列。"""
    for i, h in enumerate(header):
        if str(h).strip() == "股票代码":
            return i
    for i, h in enumerate(header):
        if str(h).strip() == "证券代码":
            return i
    return 0


def _sheet_header(ws) -> List:
    """读取 sheet 第1行表头。"""
    return [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]


def _find_col_by_name(ws, name: str) -> Optional[int]:
    """按表头名定位列索引（0起），找不到返回 None。"""
    header = _sheet_header(ws)
    for i, h in enumerate(header):
        if str(h).strip() == name:
            return i
    return None


async def execute_all_a_800(executor, config: dict, date_str: Optional[str] = None):
    """主入口：生成/更新 18号表「全部A股800亿输出」。"""
    date_str = (config.get("date_str") or "").strip() or (date_str or "").strip() or executor.today
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return {"success": False, "error": f"数据日期格式错误: {date_str}"}

    base_dir = executor.base_dir

    # 公共数据源 B
    public_path = find_public_source_file(base_dir, date_str, PUBLIC_SUBDIR)
    if not public_path:
        return {
            "success": False,
            "error": f"公共数据源缺失: {base_dir}/{date_str}/{PUBLIC_SUBDIR}/ 下无公共文件",
        }
    public_rows = read_sheet_rows(public_path)
    if not public_rows:
        return {"success": False, "error": f"公共文件无数据: {public_path}"}

    output_filename = resolve_output_filename(config, date_str)
    target_path, mode = resolve_daily_output_file(
        base_dir, date_str, OUT_SUBDIR, output_filename, log_tag="全部A股总市值大于800亿"
    )
    logger.info(f"[全部A股800亿] 目标文件: {target_path} (mode={mode})")

    # ------------------------------------------------------------------
    # 加载/初始化 18号表工作簿与sheet
    # ------------------------------------------------------------------
    if mode == "new":
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Sheet1"
    else:
        wb = load_workbook(target_path)
        ws = wb.worksheets[0]

    # 表头为空（如拷贝来的空模板）时，先用数据源前3列表头初始化
    if ws.max_row < 1 or ws.cell(row=1, column=1).value in (None, ""):
        for c, v in enumerate(public_rows[0][:NEW_ROW_COPY_COLS], start=1):
            ws.cell(row=1, column=c).value = v

    # ------------------------------------------------------------------
    # 对比新增：B 中 A 不存在的证券代码 → 前3列追加到 A 底部
    # ------------------------------------------------------------------
    a_header = _sheet_header(ws)
    a_code_col = _find_code_col_index(a_header) + 1  # 1起
    b_code_idx = _find_code_col_index(public_rows[0])

    existing_codes = set()
    for r in range(2, ws.max_row + 1):
        nc = normalize_stock_code(ws.cell(row=r, column=a_code_col).value)
        if nc:
            existing_codes.add(nc)

    new_rows = []
    for row in public_rows[1:]:
        if not any(v not in (None, "") for v in row):
            continue
        nc = normalize_stock_code(row[b_code_idx]) if b_code_idx < len(row) else None
        if not nc or nc in existing_codes:
            continue
        new_rows.append(row)
        existing_codes.add(nc)

    append_start = ws.max_row + 1 if ws.max_row >= 1 else 2
    for i, row in enumerate(new_rows):
        r = append_start + i
        for c, v in enumerate(row[:NEW_ROW_COPY_COLS], start=1):
            ws.cell(row=r, column=c).value = v

    new_row_nums = list(range(append_start, append_start + len(new_rows)))

    # ------------------------------------------------------------------
    # 「板块」列：不存在则在C列之后新增；仅新增行填充（[行业类别]全部 匹配）
    # ------------------------------------------------------------------
    sector_idx = _find_col_by_name(ws, SECTOR_COL_NAME)
    if sector_idx is None:
        ws.insert_cols(NEW_ROW_COPY_COLS + 1)  # C列之后（新列占第4列）
        ws.cell(row=1, column=NEW_ROW_COPY_COLS + 1).value = SECTOR_COL_NAME
        sector_idx = NEW_ROW_COPY_COLS  # 0起
        logger.info("[全部A股800亿] 已新增「板块」列")

    sector_map = load_all_a_column_map(base_dir, ALL_A_INDUSTRY_MARKER)
    for r in new_row_nums:
        code = ws.cell(row=r, column=a_code_col).value
        nc = normalize_stock_code(code)
        ws.cell(row=r, column=sector_idx + 1).value = sector_map.get(nc, "") if nc else ""

    # ------------------------------------------------------------------
    # 「{M}/{D}\n39日新高」列：板块列之后插入（同日已存在则复用）；仅新增行填充
    # ------------------------------------------------------------------
    m, d = int(date_str[5:7]), int(date_str[8:10])
    col39_name = f"{m}/{d}\n39日新高"
    col39_idx = _find_col_by_name(ws, col39_name)
    if col39_idx is None:
        insert_at = sector_idx + 2  # 板块列之后（1起）
        ws.insert_cols(insert_at)
        ws.cell(row=1, column=insert_at).value = col39_name
        col39_idx = insert_at - 1  # 0起
        logger.info(f"[全部A股800亿] 已新增「{col39_name}」列")

    if new_row_nums:
        high39_codes = load_39day_high_codes(base_dir, date_str)
        hit = 0
        for r in new_row_nums:
            code = ws.cell(row=r, column=a_code_col).value
            nc = normalize_stock_code(code)
            if nc and nc in high39_codes:
                ws.cell(row=r, column=col39_idx + 1).value = code
                hit += 1
    else:
        hit = 0

    wb.save(target_path)
    wb.close()

    logger.info(
        f"[全部A股800亿] 完成: {target_path} ({mode}) 新增行={len(new_rows)} 39日新高命中={hit}"
    )
    return {
        "success": True,
        "message": f"18号表已生成({mode})，数据日期 {date_str} 新增 {len(new_rows)} 行，39日新高命中 {hit}",
        "file_path": target_path,
        "_preview": [{"数据日期": date_str, "新增行数": len(new_rows), "39日新高命中": hit}],
    }
