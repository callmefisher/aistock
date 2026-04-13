import re
import pandas as pd

def normalize_stock_code(code):
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

def extract_numeric_code(code):
    normalized = normalize_stock_code(code)
    if not normalized:
        return ''
    if '.' in normalized:
        return normalized.split('.')[0]
    return normalized

def match_stock_code_flexible(code, stock_dict, return_value=True):
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

print("=== Test normalize_stock_code ===")
test_cases = [
    (638, "000638"),
    (1280, "001280"),
    (601398, "601398"),
    (8, "000008"),
    (30, "000030"),
    (1257, "001257"),
    (638.0, "000638"),
    (1280.0, "001280"),
    ("000638.SZ", "000638.SZ"),
    ("601398.SH", "601398.SH"),
    ("  601398  ", "601398"),
    ("638.SZ", "000638.SZ"),
    (None, ""),
    ("nan", ""),
    ("*ST万方", "*ST万方"),
]
for input_val, expected in test_cases:
    result = normalize_stock_code(input_val)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: normalize_stock_code({input_val!r}) = {result!r} (expected {expected!r})")

print()
print("=== Test match_stock_code_flexible with SOE dict ===")
soe_dict = {}
soe_df = pd.read_excel('data/excel/国企/问财国央企 0331.xlsx', dtype=str)
code_col = next((col for col in ['股票代码.1', '股票代码', '证券代码'] if col in soe_df.columns), None)
name_col = next((col for col in ['股票简称', '证券简称'] if col in soe_df.columns), None)
if code_col and name_col:
    for _, row in soe_df.iterrows():
        stock_code = ''
        for col in ['股票代码.1', '股票代码', '证券代码']:
            if col in soe_df.columns and pd.notna(row[col]):
                val = normalize_stock_code(row[col])
                if val:
                    stock_code = val
                    break
        stock_name = row[name_col] if pd.notna(row[name_col]) else ''
        if stock_code:
            soe_dict[stock_code] = stock_name

print(f"Loaded {len(soe_dict)} SOE stocks")

test_matches = [
    ("000638.SZ", "*ST万方"),
    ("601398.SH", "工商银行"),
    ("601939.SH", "建设银行"),
    ("001280.SZ", "中国铀业"),
    ("000008.SZ", "神州高铁"),
    ("300091.SZ", "*ST金灵"),
]
for code, expected_name in test_matches:
    result = match_stock_code_flexible(code, soe_dict)
    status = "PASS" if result == expected_name else "FAIL"
    print(f"  {status}: match('{code}') = '{result}' (expected '{expected_name}')")

print()
print("=== Check rows from 1459 onwards ===")
unmatched = []
for idx in range(1457, len(soe_df)):
    row = soe_df.iloc[idx]
    code1 = row.get('股票代码', '')
    code2 = row.get('股票代码.1', '')
    name = row.get('股票简称', '')
    if pd.notna(code1):
        norm_code = normalize_stock_code(code1)
        test_code = f"{norm_code}.SZ" if '.' not in norm_code else norm_code
        result = match_stock_code_flexible(test_code, soe_dict)
        if not result:
            unmatched.append((idx+2, code1, code2, name, test_code))

if unmatched:
    print(f"  Unmatched rows: {len(unmatched)}")
    for row_num, code1, code2, name, test_code in unmatched[:10]:
        print(f"    Row {row_num}: stock_code={code1}, stock_code.1={code2}, name={name}, test_code={test_code}")
else:
    print("  All rows from 1459 onwards matched successfully!")
