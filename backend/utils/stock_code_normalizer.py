import re
from typing import Optional, Tuple


def normalize_stock_code(code: str) -> str:
    if code is None:
        return ''

    code_str = str(code).strip()

    if not code_str or code_str.lower() in ['nan', 'none', '', 'undefined']:
        return ''

    code_str = code_str.upper()
    code_str = re.sub(r'\s+', '', code_str)

    if re.match(r'^\d+\.\d+$', code_str):
        code_str = str(int(float(code_str)))

    if re.match(r'^\d+$', code_str) and len(code_str) < 6:
        code_str = code_str.zfill(6)

    suffix_match = re.match(r'^(\d+)\.(SH|SZ|BJ)$', code_str)
    if suffix_match:
        numeric_part = suffix_match.group(1)
        if len(numeric_part) < 6:
            numeric_part = numeric_part.zfill(6)
        code_str = f"{numeric_part}.{suffix_match.group(2)}"

    return code_str


def extract_numeric_code(code: str) -> str:
    """
    从股票代码中提取纯数字部分

    Args:
        code: 股票代码（如 '601398.SH', '300001.SZ'）

    Returns:
        纯数字代码（如 '601398', '300001'）

    Examples:
        >>> extract_numeric_code('601398.SH')
        '601398'
        >>> extract_numeric_code('300001.SZ')
        '300001'
        >>> extract_numeric_code('601398')
        '601398'
    """
    normalized = normalize_stock_code(code)
    if not normalized:
        return ''

    if '.' in normalized:
        return normalized.split('.')[0]

    return normalized


def match_stock_code_flexible(
    code: str,
    stock_dict: dict,
    return_value: bool = True
) -> Optional[str]:
    """
    灵活匹配股票代码（支持多种格式）

    匹配策略：
    1. 精确匹配标准化后的代码 (如 601398.SH) — O(1)
    2. 匹配纯数字代码 (如 601398)                — O(1)
    3. 反向匹配：查询的数字部分 == 字典键的数字部分（如 查 "601398" 命中键 "601398.SH"）— O(n)
    """
    normalized = normalize_stock_code(code)
    if not normalized:
        return ''

    if normalized in stock_dict:
        return stock_dict[normalized] if return_value else normalized

    numeric_code = extract_numeric_code(normalized)
    if numeric_code and numeric_code in stock_dict:
        return stock_dict[numeric_code] if return_value else numeric_code
     
    return ''


def is_public_file(filepath: str, public_dir: str) -> bool:
    """
    判断文件是否属于public目录

    Args:
        filepath: 文件完整路径
        public_dir: public目录路径

    Returns:
        是否是public文件

    Examples:
        >>> is_public_file('/data/excel/2025public/file.xlsx', '/data/excel/2025public')
        True
        >>> is_public_file('/data/excel/股权转让/public/file.xlsx', '/data/excel/股权转让/public')
        True
        >>> is_public_file('/data/excel/2026-04-13/file.xlsx', '/data/excel/2025public')
        False
    """
    if not filepath or not public_dir:
        return False

    normalized_path = os.path.normpath(filepath)
    normalized_public = os.path.normpath(public_dir)

    return normalized_public in normalized_path


import os
