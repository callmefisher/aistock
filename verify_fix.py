#!/usr/bin/env python3
"""
快速验证脚本：验证股票代码标准化模块和public文件识别逻辑
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from utils.stock_code_normalizer import (
    normalize_stock_code,
    extract_numeric_code,
    match_stock_code_flexible,
    is_public_file as check_is_public_file
)


def test_normalize_stock_code():
    """测试标准化功能"""
    print("=" * 60)
    print("测试1: 股票代码标准化")
    print("=" * 60)

    test_cases = [
        ('601398', '601398'),
        ('  601398  ', '601398'),
        ('601398.SH', '601398.SH'),
        (None, ''),
        ('', ''),
        ('nan', ''),
        ('\t300001\n', '300001'),
    ]

    all_passed = True
    for input_val, expected in test_cases:
        result = normalize_stock_code(input_val)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} normalize_stock_code({repr(input_val)}) = {repr(result)} (期望: {repr(expected)})")

    return all_passed


def test_extract_numeric_code():
    """测试提取纯数字代码"""
    print("\n" + "=" * 60)
    print("测试2: 提取纯数字代码")
    print("=" * 60)

    test_cases = [
        ('601398.SH', '601398'),
        ('300001.SZ', '300001'),
        ('601398', '601398'),
        ('', ''),
        (None, ''),
    ]

    all_passed = True
    for input_val, expected in test_cases:
        result = extract_numeric_code(input_val)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} extract_numeric_code({repr(input_val)}) = {repr(result)} (期望: {repr(expected)})")

    return all_passed


def test_match_flexible():
    """测试灵活匹配"""
    print("\n" + "=" * 60)
    print("测试3: 灵活匹配")
    print("=" * 60)

    stock_dict = {
        '601398': '工商银行',
        '601939.SH': '中国银行',
        '300001': '特锐德'
    }

    test_cases = [
        ('601398', '工商银行'),
        ('601398.SH', '工商银行'),
        ('  601398  ', '工商银行'),
        ('601939.SH', '中国银行'),
        ('601939', '中国银行'),
        ('300001.SZ', '特锐德'),
        ('000001', ''),  # 无匹配
        (None, ''),
        ('', ''),
    ]

    all_passed = True
    for input_val, expected in test_cases:
        result = match_stock_code_flexible(input_val, stock_dict)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} match({repr(input_val)}) = {repr(result)} (期望: {repr(expected)})")

    return all_passed


def test_is_public_file():
    """测试public文件识别"""
    print("\n" + "=" * 60)
    print("测试4: Public文件识别逻辑（关键Bug修复）")
    print("=" * 60)

    test_cases = [
        # (filepath, public_dir, expected_result, description)
        (
            '/data/excel/2025public/file.xlsx',
            '/data/excel/2025public',
            True,
            '2025public目录 - 并购重组类型'
        ),
        (
            '/data/excel/股权转让/public/file.xlsx',
            '/data/excel/股权转让/public',
            True,
            '股权转让/public目录 - 股权转让类型'
        ),
        (
            '/data/excel/股权转让/public/股权转让25_1-12.xlsx',
            '/data/excel/股权转让/public',
            True,
            '股权转让具体文件'
        ),
        (
            '/data/excel/2026-04-13/file.xlsx',
            '/data/excel/2025public',
            False,
            '非public文件'
        ),
        (
            '',
            '/data/excel/2025public',
            False,
            '空路径'
        ),
    ]

    all_passed = True
    for filepath, public_dir, expected, desc in test_cases:
        result = check_is_public_file(filepath, public_dir)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} [{desc}]")
        print(f"      filepath: {filepath}")
        print(f"      public_dir: {public_dir}")
        print(f"      结果: {result} (期望: {expected})")

    return all_passed


def main():
    """运行所有测试"""
    print("\n" + "#" * 70)
    print("#  股权转让工作流修复验证脚本")
    print("#  验证内容:")
    print("#  1. 股票代码统一标准化")
    print("#  2. Public文件识别逻辑修复（解决数据缺失问题）")
    print("#  3. 国企匹配字符串格式化问题修复")
    print("#" * 70)

    results = []
    results.append(("股票代码标准化", test_normalize_stock_code()))
    results.append(("提取纯数字代码", test_extract_numeric_code()))
    results.append(("灵活匹配", test_match_flexible()))
    results.append(("Public文件识别", test_is_public_file()))

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "通过 ✓" if passed else "失败 ✗"
        if not passed:
            all_passed = False
        print(f"  {name}: {status}")

    print("\n" + "#" * 70)
    if all_passed:
        print("#  ✓ 所有测试通过！修复成功！")
        print("#")
        print("#  关键修复点:")
        print("#  1. is_public_file() 不再硬编码 '2025public'")
        print("#     现在支持任意类型的 public 目录（包括 股权转让/public）")
        print("#")
        print("#  2. 所有股票代码处理使用统一的 normalize_stock_code()")
        print("#     解决国企1459行后数据无法识别的问题")
        print("#")
        print("#  3. 匹配逻辑使用 match_stock_code_flexible()")
        print("#     支持多种格式自动匹配（带后缀、不带后缀等）")
    else:
        print("#  ✗ 部分测试失败，需要进一步排查")
    print("#" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
