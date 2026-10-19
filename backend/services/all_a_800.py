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
from utils.stock_code_normalizer import match_stock_code_flexible, normalize_stock_code

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
    """定位代码列索引（0起）：优先「股票代码」，其次「证券代码」（均含包含匹配——
    源文件表头可能是多行文本如"证券代码\\n[单位]只"），否则第0列。"""
    for i, h in enumerate(header):
        if str(h).strip() == "股票代码":
            return i
    for i, h in enumerate(header):
        if "股票代码" in str(h):
            return i
    for i, h in enumerate(header):
        if "证券代码" in str(h):
            return i
    return 0


def _is_valid_stock_row(code_raw) -> bool:
    """过滤非证券代码行：如表尾“数据来源：xxx”说明行——normalize 对其返回非空文本，
    会污染代码集合与新增行识别，必须在匹配前排除。"""
    if code_raw is None:
        return False
    s = str(code_raw).strip()
    if not s or s.startswith("数据来源"):
        return False
    # normalize 后必须形如纯数字代码（可带 .SH/.SZ/.BJ 后缀）
    nc = normalize_stock_code(s)
    return bool(re.match(r"^\d{6}(\.(SH|SZ|BJ))?$", nc))


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
        # reuse/copy 模式：目标文件解析已验证可读，此处 try 兜底竞态/极端损坏，降级全新生成
        try:
            wb = load_workbook(target_path)
            ws = wb.worksheets[0]
        except Exception as e:
            logger.warning(f"[全部A股800亿] 目标文件加载失败，降级全新生成: {target_path}, {e}")
            wb = Workbook()
            ws = wb.active
            assert ws is not None
            ws.title = "Sheet1"
            mode = "new(降级)"

    # 表头为空（如拷贝来的空模板）时，先用数据源前3列表头初始化
    if ws.max_row < 1 or ws.cell(row=1, column=1).value in (None, ""):
        for c, v in enumerate(public_rows[0][:NEW_ROW_COPY_COLS], start=1):
            ws.cell(row=1, column=c).value = v

    # ------------------------------------------------------------------
    # 对比新增：B 中 A 不存在的证券代码 → 前3列追加到 A 底部
    # （“数据来源：xxx”等非代码行一律排除，不参与比对也不追加）
    # ------------------------------------------------------------------
    a_header = _sheet_header(ws)
    a_code_col = _find_code_col_index(a_header) + 1  # 1起
    b_code_idx = _find_code_col_index(public_rows[0])

    existing_codes = set()
    last_valid_row = 1  # 最后一个有效代码数据行（1=仅有表头）
    for r in range(2, ws.max_row + 1):
        raw = ws.cell(row=r, column=a_code_col).value
        if _is_valid_stock_row(raw):
            existing_codes.add(normalize_stock_code(raw))
            last_valid_row = r

    new_rows = []
    skipped_invalid = 0
    for row in public_rows[1:]:
        if not any(v not in (None, "") for v in row):
            continue
        raw = row[b_code_idx] if b_code_idx < len(row) else None
        if not _is_valid_stock_row(raw):
            skipped_invalid += 1
            continue
        nc = normalize_stock_code(raw)
        if nc in existing_codes:
            continue
        new_rows.append(row)
        existing_codes.add(nc)

    # 新增行紧贴最后一个有效数据行追加（表格下方可能有“数据来源”等杂散行，
    # insert_rows 将其下移，不覆盖不跳行）
    if new_rows:
        insert_at = last_valid_row + 1
        ws.insert_rows(insert_at, amount=len(new_rows))
        for i, row in enumerate(new_rows):
            r = insert_at + i
            for c, v in enumerate(row[:NEW_ROW_COPY_COLS], start=1):
                ws.cell(row=r, column=c).value = v
        last_valid_row = insert_at + len(new_rows) - 1

    # 全部数据行范围（含新增）：39日新高整列重匹配用
    all_data_rows = list(range(2, last_valid_row + 1))
    # 新增行范围（板块列仅新增行填充）
    new_row_nums = list(range(last_valid_row - len(new_rows) + 1, last_valid_row + 1))

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
    sector_hit = 0
    for r in new_row_nums:
        code = ws.cell(row=r, column=a_code_col).value
        # 双键匹配（精确键 + 纯数字键）：全部A股文件代码常带 .SZ/.SH 后缀，
        # 本表代码多为纯数字，直接 .get() 会 miss（板块为空的根因），复用既有灵活匹配
        val = match_stock_code_flexible(code, sector_map) if code else ""
        if val:
            sector_hit += 1
        ws.cell(row=r, column=sector_idx + 1).value = val

    # ------------------------------------------------------------------
    # 「{M}/{D}\n39日新高」列：板块列之后插入（同日已存在则复用）。
    # 整列重匹配：每次执行对全部已有数据行（含新增）按当日 39日新高 公共数据
    # 重新匹配——命中填入该行证券代码，未命中清空（反映当日最新状态）。
    # 表头单元格为“日期在上、39日新高在下”的单列双行格式，写入后立即设置
    # 自动换行 + 行高，保证打开文件即呈现双行（无需鼠标点击单元格）。
    # ------------------------------------------------------------------
    from openpyxl.styles import Alignment

    m, d = int(date_str[5:7]), int(date_str[8:10])
    col39_name = f"{m}/{d}\n39日新高"
    col39_idx = _find_col_by_name(ws, col39_name)
    if col39_idx is None:
        insert_at = sector_idx + 2  # 板块列之后（1起）
        ws.insert_cols(insert_at)
        ws.cell(row=1, column=insert_at).value = col39_name
        col39_idx = insert_at - 1  # 0起
        logger.info(f"[全部A股800亿] 已新增「{col39_name}」列")
    # 表头双行显示（重复执行时也统一刷新格式）
    _head = ws.cell(row=1, column=col39_idx + 1)
    _head.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = 30

    high39_codes = load_39day_high_codes(base_dir, date_str)
    high39_count = len(high39_codes)
    hit = 0
    for r in all_data_rows:
        code = ws.cell(row=r, column=a_code_col).value
        nc = normalize_stock_code(code)
        if nc and nc in high39_codes:
            ws.cell(row=r, column=col39_idx + 1).value = code
            hit += 1
        else:
            ws.cell(row=r, column=col39_idx + 1).value = ""

    wb.save(target_path)
    wb.close()

    logger.info(
        f"[全部A股800亿] 完成: {target_path} ({mode}) "
        f"B有效数据行(代码列={public_rows[0][b_code_idx] if b_code_idx < len(public_rows[0]) else 'A列'}) "
        f"A已有代码={len(existing_codes) - len(new_rows)} 新增行={len(new_rows)} "
        f"排除非代码行={skipped_invalid} 板块命中(新增行)={sector_hit}/{len(new_rows)} "
        f"39日新高源={high39_count}个代码 整列重匹配命中={hit}/{len(all_data_rows)}"
    )
    return {
        "success": True,
        "message": (
            f"18号表已生成({mode})，数据日期 {date_str}：新增 {len(new_rows)} 行"
            f"（排除非代码行 {skipped_invalid}），板块命中 {sector_hit}，"
            f"39日新高整列重匹配 {len(all_data_rows)} 行、命中 {hit}"
        ),
        "file_path": target_path,
        "_preview": [{
            "数据日期": date_str, "新增行数": len(new_rows),
            "排除非代码行": skipped_invalid, "板块命中": sector_hit,
            "39日新高源代码数": high39_count, "39日新高命中": hit,
        }],
    }
