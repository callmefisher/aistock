"""工作流：本周总市值千亿新高（14号表 + 20号表）。

规则（数据日期 date_str，回溯35天含当日）：
- 输出文件：{base_dir}/{date}/本周总市值千亿新高输出/14 总市值大于1000亿 本周最高价格大于上周最高价格{MMDD}.xlsx
  （注意与公共上传目录「本周总市值千亿新高」区分；同名强制覆盖更新）
- 目标文件解析：35天回溯（数据日期已有文件直接编辑；否则取最近35日内最新文件拷贝重命名；都没有则全新生成）；
- 全新生成：第一个 sheet「筛选结果」= 公共文件内容原样复制；
- 无论何种模式：新建以 MMDD 命名的第2个 sheet（位于「筛选结果」之后，重复执行先删后建保证幂等），
  内容为公共文件数据：按代码列（优先「股票代码」，其次「证券代码」，否则A列）降序整体排序，
  排序后在B列后插入一列空白列；
- 第一个 sheet「筛选结果」内容不修改；
- 最后将 MMDD sheet 的 A 列（含表头）复制到新 Excel（20号表），固定输出到
  {base_dir}/{date}/20号表本周总市值千亿新高A列/20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx。

复用 weekly_common：35天目标文件解析 / 公共数据源定位 / 行值读取。
"""

import logging
import re
import os
from typing import List, Optional

from openpyxl import Workbook, load_workbook

from services.weekly_common import (
    find_public_source_file,
    mmdd_of,
    read_sheet_rows,
    resolve_daily_output_file,
)
from utils.stock_code_normalizer import normalize_stock_code

logger = logging.getLogger(__name__)

# 14号表目标输出子目录（注意与公共上传目录「本周总市值千亿新高」区分）
OUT_SUBDIR = "本周总市值千亿新高输出"
# 公共数据源子目录
PUBLIC_SUBDIR = "本周总市值千亿新高"
# 默认输出文件名模板
DEFAULT_FILENAME_TEMPLATE = "14 总市值大于1000亿 本周最高价格大于上周最高价格{MMDD}.xlsx"
# 20号表输出目录名与固定文件名
TABLE20_SUBDIR = "20号表本周总市值千亿新高A列"
TABLE20_FILENAME = "20 总市值大于1000亿 本周最高价格大于上周最高价格.xlsx"

FIRST_SHEET_NAME = "筛选结果"


def build_default_filename(date_str: str) -> str:
    """数据日期 → 默认输出文件名，如 2026-10-15 → 14 总市值大于1000亿 本周最高价格大于上周最高价格1015.xlsx"""
    return DEFAULT_FILENAME_TEMPLATE.replace("{MMDD}", mmdd_of(date_str))


def resolve_output_filename(config: dict, date_str: str) -> str:
    """解析输出文件名：优先使用配置（前端可编辑），否则按数据日期生成默认名。"""
    configured = (config.get("output_filename") or "").strip()
    if configured:
        return configured.replace("{MMDD}", mmdd_of(date_str))
    return build_default_filename(date_str)


def _find_code_col_index(header: List) -> Optional[int]:
    """定位代码列索引：优先「股票代码」，其次「证券代码」，否则 None（由调用方回退A列）。"""
    for i, h in enumerate(header):
        if str(h).strip() == "股票代码":
            return i
    for i, h in enumerate(header):
        if str(h).strip() == "证券代码":
            return i
    return None


def sort_rows_by_code_desc(rows: List[List]) -> List[List]:
    """数据行按代码列降序整体排序（表头不动，其余列跟随不混行；无代码的行排在末尾）。"""
    if not rows:
        return []
    header = rows[0]
    data = [r for r in rows[1:] if any(v not in (None, "") for v in r)]
    code_idx = _find_code_col_index(header)

    def key(row: List):
        raw = row[code_idx] if code_idx is not None and code_idx < len(row) else (row[0] if row else None)
        nc = normalize_stock_code(raw)
        return (nc is not None, nc or "")

    data.sort(key=key, reverse=True)
    return [header] + data


def _is_invalid_data_row(row) -> bool:
    """数据行无效判定：全空行，或任一非空单元格为「数据来源」说明行 /
    undefined / null / none / nan 等脏数据（写入 MMDD sheet 前排除）。"""
    if not row or not any(v not in (None, "") for v in row):
        return True
    for v in row:
        if v in (None, ""):
            continue
        s = str(v).strip()
        if s.startswith("数据来源"):
            return True
        low = s.lower()
        if "undefined" in low or low in ("null", "none", "nan"):
            return True
    return False


def _write_mmdd_sheet(wb, sheet_name: str, rows: List[List]) -> None:
    """（重）建 MMDD sheet：位于「筛选结果」之后；内容=排序结果+B列后空白列。

    数据行排除「数据来源」/undefined 等无效行（表头保留原样；
    「筛选结果」sheet 不修改，保持公共文件原貌）。"""
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]
    ws = wb.create_sheet(title=sheet_name, index=1)
    sorted_rows = sort_rows_by_code_desc(rows)
    filtered = [sorted_rows[0]] + [r for r in sorted_rows[1:] if not _is_invalid_data_row(r)]
    skipped = len(sorted_rows) - len(filtered)
    if skipped:
        logger.info(f"[本周总市值千亿新高] MMDD sheet 排除无效行 {skipped} 行（数据来源/undefined等）")
    for row in filtered:
        ws.append(["" if v is None else v for v in row])
    # B列后插入一列空白列
    ws.insert_cols(3)


def _is_invalid_table20_cell(v) -> bool:
    """20号表无效行判定：空值、「数据来源」开头的说明行、undefined/null 等脏数据。"""
    if v is None:
        return True
    s = str(v).strip()
    if not s:
        return True
    if s.startswith("数据来源"):
        return True
    low = s.lower()
    if "undefined" in low or low in ("null", "none", "nan"):
        return True
    return False


def _export_table20(base_dir: str, date_str: str, mv1000_path: str, mmdd: str) -> str:
    """20号表：从已生成的 14号表 的 MMDD sheet 拷贝第一列（A列，含表头）到独立 Excel，
    按股票代码/证券代码降序排列，仅此一列；排除「数据来源」/undefined 等无效行；固定文件名输出。"""
    out_dir = os.path.join(base_dir, date_str, TABLE20_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, TABLE20_FILENAME)

    # 读取 14号表 MMDD sheet 的 A 列（第一列）
    wb_src = load_workbook(mv1000_path, read_only=True, data_only=True)
    try:
        if mmdd not in wb_src.sheetnames:
            raise ValueError(f"14号表缺少 sheet「{mmdd}」: {mv1000_path}")
        ws_src = wb_src[mmdd]
        rows = [list(row) for row in ws_src.iter_rows(min_col=1, max_col=1, values_only=True)]
    finally:
        wb_src.close()

    if not rows:
        raise ValueError(f"14号表 sheet「{mmdd}」无数据: {mv1000_path}")

    # 表头保留原样；数据行剔除无效行（数据来源说明行、undefined/null 脏数据、空行）
    header, data_rows = rows[0], rows[1:]
    col_a = [header] + [r for r in data_rows if not _is_invalid_table20_cell(r[0] if r else None)]

    # 单列按代码降序（表头不动），复用既有排序逻辑
    sorted_col = sort_rows_by_code_desc(col_a)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = mmdd
    for row in sorted_col:
        ws.append([row[0] if row and row[0] is not None else ""])
    # 样式与用户模板「21ok.xlsx」完全一致，且为「整列统一格式」：
    # 字体 宋体11、charset=134（GB2312）、颜色=主题色1（theme=1）、字体方案=minor；
    # 数值格式 0.00_);[Red]\(0.00\)；默认行高16.8、默认列宽9、A列宽18.75。
    # 列级样式覆盖整列所有行（含空行区域，后续手工追加行自动继承）；
    # 已有单元格再显式设置一遍确保优先生效。
    from openpyxl.styles import Color, Font
    fmt = "0.00_);[Red]\\(0.00\\)"
    font = Font(name="宋体", size=11, charset=134,
                color=Color(theme=1, tint=0.0), scheme="minor")
    ws.sheet_format.defaultRowHeight = 16.8
    ws.sheet_format.defaultColWidth = 9
    col_dim = ws.column_dimensions["A"]
    col_dim.width = 18.75
    col_dim.font = font
    col_dim.number_format = fmt
    for r in range(1, ws.max_row + 1):
        cell = ws.cell(row=r, column=1)
        cell.number_format = fmt
        cell.font = font
    wb.save(out_path)
    wb.close()
    # 生成后自动执行一次「标准化保存」（等价用 Excel 打开再原样保存一次）：
    # 1) styles.xml 替换为模板样式表，实际单元格样式引用链与 21ok.xlsx 逐字节一致；
    # 2) inlineStr → sharedStrings 规范化：openpyxl 只写 t="inlineStr"（无
    #    sharedStrings.xml），Choice 等第三方导入器不识别该形态；Excel 手动
    #    重存后能正常导入，正是重存把字符串规范化为 t="s" + 共享字符串表所致
    _standard_save(out_path)
    return out_path


_TABLE20_STYLES_TEMPLATE: Optional[bytes] = None


def _table20_template_styles() -> bytes:
    """模板 styles.xml（提取自用户模板 21ok.xlsx），进程内缓存。"""
    global _TABLE20_STYLES_TEMPLATE
    if _TABLE20_STYLES_TEMPLATE is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "table20_styles_template.xml")
        with open(path, "rb") as f:
            _TABLE20_STYLES_TEMPLATE = f.read()
    return _TABLE20_STYLES_TEMPLATE


def _xml_unescape(s: str) -> str:
    """XML 文本反转义（单遍）：数值字符引用 &#NNN; / &#xHH; + 基本实体。
    openpyxl 序列化把非 ASCII 写成数值字符引用，转 sharedStrings 时需还原为
    字面 UTF-8（与 Excel 原生形态一致）。"""
    def _sub(m) -> str:
        if m.group(1) is not None:
            return chr(int(m.group(1)))
        if m.group(2) is not None:
            return chr(int(m.group(2), 16))
        return {"&amp;": "&", "&lt;": "<", "&gt;": ">",
                "&quot;": '"', "&apos;": "'"}[m.group(0)]
    return re.sub(r"&#(\d+);|&#x([0-9A-Fa-f]+);|&amp;|&lt;|&gt;|&quot;|&apos;", _sub, s)


def _xml_escape(s: str) -> str:
    """XML 文本转义（仅文本内容必需的三个字符）。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _standard_save(out_path: str) -> None:
    """Excel 标准化保存后处理（生成后自动执行，等价「用 Excel 打开再原样保存一次」）：

    1. xl/styles.xml 整体替换为模板（21ok.xlsx）样式表——实际单元格样式引用链
       与模板逐字节一致（openpyxl 默认字体 Calibri 占 fonts[0]，使数据单元格
       fontId=1；模板默认字体即宋体，fontId=0 + numFmtId=176）；
    2. sheetFormatPr 对齐模板形态（去掉 openpyxl 附加的 baseColWidth）；
    3. inlineStr 字符串单元格 → Excel 原生 sharedStrings 共享字符串表：
       openpyxl 保存只写 <c t="inlineStr"><is><t>…（且无 sharedStrings.xml），
       部分第三方导入器（如 Choice 金融终端）不支持该形态；Excel 打开手动重存
       后能正常导入，正是重存把字符串规范化为 <c t="s"><v>索引</v> + 共享字符串表。
       此处自动完成同等转换，并补写 xl/sharedStrings.xml、[Content_Types].xml
       Override 及 workbook.xml.rels 关系。
    4. 所有 xml/rels 部件补 <?xml?> 声明：openpyxl 3.1 原生输出除 theme1.xml 外
       均不写声明（直接以根元素开头），严格 OPC 解析器（Choice 导入器）要求声明存在；
    5. [Content_Types].xml 重打包为 zip 第一个条目：OPC 规范要求，openpyxl 原生
       排在最后一个条目，流式/严格解析器依赖其位于包首；
    6. worksheet 关系 Target 由包绝对路径 /xl/worksheets/sheetN.xml 规范化为相对
       路径 worksheets/sheetN.xml（Excel/WPS 均为相对路径；Choice 等导入器按
       「基目录+Target」拼接解析，绝对形式直接解析失败），并丢弃 openpyxl 写出的
       空 workbookProtection/definedNames 元素（WPS 重存同样会丢弃）。"""
    import zipfile

    tpl = _table20_template_styles()

    cell_re = re.compile(
        r'<c ([^>]*?)t="inlineStr"([^>]*?)><is><t( xml:space="preserve")?>(.*?)</t></is></c>',
        re.S,
    )
    empty_re = re.compile(r'<c ([^>]*?)t="inlineStr"([^>]*?)/>')

    ss_items: list = []   # [(xml:space 属性, 未转义文本), ...]，去重
    ss_index: dict = {}   # (space, text) -> 索引
    ss_refs = 0           # 字符串单元格总数（含重复引用）

    def _to_shared(m) -> str:
        nonlocal ss_refs
        ss_refs += 1
        # 还原数值字符引用为字面文本（去重键与 sst 输出统一用未转义形式）
        key = (m.group(3) or "", _xml_unescape(m.group(4)))
        idx = ss_index.get(key)
        if idx is None:
            idx = len(ss_items)
            ss_index[key] = idx
            ss_items.append(key)
        return '<c %st="s"%s><v>%d</v></c>' % (m.group(1), m.group(2), idx)

    # 两遍处理：先处理 worksheet（收集字符串），再补 sharedStrings 及注册部件
    with zipfile.ZipFile(out_path) as zin:
        entries = [(it.filename, zin.read(it.filename)) for it in zin.infolist()]

    processed = []
    for name, data in entries:
        if name == "xl/styles.xml":
            data = tpl
        elif name == "xl/_rels/workbook.xml.rels":
            # worksheet 关系 Target：包绝对路径 → 相对路径（openpyxl 怪癖，见 docstring 第6点）
            data = data.replace(b'Target="/xl/', b'Target="')
        elif name == "xl/workbook.xml":
            # 丢弃空元素（WPS 重存同样丢弃；空 workbookProtection 可能被保守解析器误判为保护态）
            data = data.replace(b"<workbookProtection/>", b"") \
                       .replace(b"<definedNames/>", b"")
        elif name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            text = data.decode("utf-8")
            text = cell_re.sub(_to_shared, text)
            text = empty_re.sub(lambda m: "<c %s%s/>" % (m.group(1), m.group(2)), text)
            text = text.replace('<sheetFormatPr baseColWidth="8" ', '<sheetFormatPr ')
            data = text.encode("utf-8")
        processed.append((name, data))

    if ss_items:
        sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
               ' count="%d" uniqueCount="%d">' % (ss_refs, len(ss_items))
               + "".join('<si><t%s>%s</t></si>' % (sp, _xml_escape(tx)) for sp, tx in ss_items)
               + '</sst>')
        processed.append(("xl/sharedStrings.xml", sst.encode("utf-8")))
        for i, (name, data) in enumerate(processed):
            if name == "[Content_Types].xml":
                text = data.decode("utf-8").replace(
                    "</Types>",
                    '<Override PartName="/xl/sharedStrings.xml" ContentType='
                    '"application/vnd.openxmlformats-officedocument.spreadsheetml'
                    '.sharedStrings+xml"/></Types>')
                processed[i] = (name, text.encode("utf-8"))
            elif name == "xl/_rels/workbook.xml.rels":
                text = data.decode("utf-8")
                ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', text)]
                rid = "rId%d" % (max(ids) + 1 if ids else 1)
                text = text.replace(
                    "</Relationships>",
                    '<Relationship Id="%s" Type="http://schemas.openxmlformats.org'
                    '/officeDocument/2006/relationships/sharedStrings"'
                    ' Target="sharedStrings.xml"/></Relationships>' % rid)
                processed[i] = (name, text.encode("utf-8"))

    # OPC 兼容修复（等价 WPS/Excel 重存的规范化）：
    # a) xml/rels 部件缺 <?xml?> 声明则补写（模板 styles 与生成的 sharedStrings 已带，跳过）；
    # b) [Content_Types].xml 置于 zip 首条目（稳定排序，其余保持原相对顺序）。
    _decl = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    _fixed = []
    for name, data in processed:
        if (name.endswith(".xml") or name.endswith(".rels")) \
                and not data.lstrip().startswith(b"<?xml"):
            data = _decl + data
        _fixed.append((name, data))
    _fixed.sort(key=lambda it: it[0] != "[Content_Types].xml")

    tmp = out_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in _fixed:
            zout.writestr(name, data)
    os.replace(tmp, out_path)


async def execute_weekly_mv1000_high(executor, config: dict, date_str: Optional[str] = None):
    """主入口：生成/更新 14号表「本周总市值千亿新高输出」+ 20号表 A列输出。"""
    date_str = (config.get("date_str") or "").strip() or (date_str or "").strip() or executor.today
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return {"success": False, "error": f"数据日期格式错误: {date_str}"}

    base_dir = executor.base_dir

    # 公共数据源（本周总市值千亿新高）
    public_path = find_public_source_file(base_dir, date_str, PUBLIC_SUBDIR)
    if not public_path:
        return {
            "success": False,
            "error": f"公共数据源缺失: {base_dir}/{date_str}/{PUBLIC_SUBDIR}/ 下无公共文件",
        }
    public_rows = read_sheet_rows(public_path)  # 优先「筛选结果」sheet，否则首个sheet
    if not public_rows:
        return {"success": False, "error": f"公共文件无数据: {public_path}"}

    output_filename = resolve_output_filename(config, date_str)
    target_path, mode = resolve_daily_output_file(
        base_dir, date_str, OUT_SUBDIR, output_filename, log_tag="本周总市值千亿新高"
    )
    logger.info(f"[本周总市值千亿新高] 目标文件: {target_path} (mode={mode})")

    mmdd = mmdd_of(date_str)

    if mode == "new":
        # 全新生成：第一个 sheet「筛选结果」= 公共文件内容原样复制
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = FIRST_SHEET_NAME
        for row in public_rows:
            ws.append(["" if v is None else v for v in row])
    else:
        # 编辑目标文件（reuse=同名可读 / copy=35日内拷贝重命名副本），「筛选结果」内容不修改。
        # 加载失败时降级为全新生成（目标文件解析已验证可读，此处兜底竞态/极端损坏，
        # 保证 20号表输出与步骤成功，不因单个坏文件中断工作流）。
        try:
            wb = load_workbook(target_path)
            if FIRST_SHEET_NAME not in wb.sheetnames:
                wb.worksheets[0].title = FIRST_SHEET_NAME
        except Exception as e:
            logger.warning(f"[本周总市值千亿新高] 目标文件加载失败，降级全新生成: {target_path}, {e}")
            wb = Workbook()
            ws = wb.active
            assert ws is not None
            ws.title = FIRST_SHEET_NAME
            for row in public_rows:
                ws.append(["" if v is None else v for v in row])
            mode = "new(降级)"

    # 只保留2个sheet：第1个「筛选结果」+ 第2个当前数据日期（如 1016）；
    # 拷贝来的历史文件可能残留旧日期sheet（1014/1015等），全部删除
    for name in list(wb.sheetnames):
        if name not in (FIRST_SHEET_NAME, mmdd):
            del wb[name]
    # 保证 sheet 顺序：筛选结果在前，数据日期在后
    if FIRST_SHEET_NAME in wb.sheetnames and wb.sheetnames[0] != FIRST_SHEET_NAME:
        wb.move_sheet(FIRST_SHEET_NAME, offset=-wb.sheetnames.index(FIRST_SHEET_NAME))

    _write_mmdd_sheet(wb, mmdd, public_rows)
    wb.save(target_path)
    wb.close()

    # 20号表：从已保存的 14号表 MMDD sheet 拷贝第一列（A列），降序，仅此一列
    table20_path = _export_table20(base_dir, date_str, target_path, mmdd)

    count = max(len(public_rows) - 1, 0)
    logger.info(f"[本周总市值千亿新高] 完成: {target_path} ({mode}) 记录数={count}; 20号表: {table20_path}")
    return {
        "success": True,
        "message": f"14号表已生成({mode})，数据日期 {date_str} 记录数 {count}；20号表A列已输出",
        "file_path": target_path,
        "table20_path": table20_path,
        # 20号表相对 {date} 的下载路径（含子目录），merge 进 step_config 供前端批量下载
        "_extra_outputs": {"output_filename_table20": f"{TABLE20_SUBDIR}/{TABLE20_FILENAME}"},
        "_preview": [{"数据日期": date_str, "记录数": count}],
    }
