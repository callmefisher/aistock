import re
from typing import Optional, Tuple


def normalize_stock_code(code: str) -> str:
    """
    统一标准化股票代码格式

    处理规则：
    1. 去除首尾空格
    2. 转换为字符串
    3. 去除可能的空格、制表符等
    4. 统一为大写格式

    Args:
        code: 股票代码（可能包含各种格式）

    Returns:
        标准化后的股票代码

    Examples:
        >>> normalize_stock_code(' 601398 ')
        '601398'
        >>> normalize_stock_code('601398.SH')
        '601398.SH'
        >>> normalize_stock_code('  300001  ')
        '300001'
    """
    if code is None:
        return ''

    code_str = str(code).strip()

    if not code_str or code_str.lower() in ['nan', 'none', '', 'undefined']:
        return ''

    code_str = code_str.upper()
    code_str = re.sub(r'\s+', '', code_str)

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
    1. 先尝试精确匹配原始格式
    2. 再尝试匹配纯数字代码
    3. 支持带后缀和不带后缀的匹配

    Args:
        code: 待匹配的股票代码
        stock_dict: 股票代码字典 {code: name}
        return_value: 是否返回匹配到的值（True）还是返回键（False）

    Returns:
        匹配成功返回对应值/键，失败返回空字符串

    Examples:
        >>> stock_dict = {'601398': '工商银行', '601398.SH': '工商银行'}
        >>> match_stock_code_flexible('601398.SH', stock_dict)
        '工商银行'
        >>> match_stock_code_flexible('601398', stock_dict)
        '工商银行'
    """
    normalized = normalize_stock_code(code)
    if not normalized:
        return ''

    if normalized in stock_dict:
        return stock_dict[normalized] if return_value else normalized

    numeric_code = extract_numeric_code(normalized)
    if numeric_code in stock_dict:
        return stock_dict[numeric_code] if return_value else numeric_code

    for key in stock_dict.keys():
        key_normalized = normalize_stock_code(key)
        key_numeric = extract_numeric_code(key_normalized)

        if normalized == key_normalized or normalized == key_numeric:
            return stock_dict[key] if return_value else key

        if numeric_code and (numeric_code == key_normalized or numeric_code == key_numeric):
            return stock_dict[key] if return_value else key

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
