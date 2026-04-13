import pandas as pd
from utils.stock_code_normalizer import normalize_stock_code, match_stock_code_flexible

soe_dict = {}
soe_df = pd.read_excel('/app/data/excel/国企/问财国央企 0331.xlsx', dtype=str)
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

print(f'Loaded {len(soe_dict)} SOE stocks')

test_matches = [
    ('000638.SZ', '*ST万方'),
    ('601398.SH', '工商银行'),
    ('601939.SH', '建设银行'),
    ('001280.SZ', '中国铀业'),
    ('300091.SZ', '*ST金灵'),
    ('002114.SZ', '罗平锌电'),
]
all_pass = True
for code, expected_name in test_matches:
    result = match_stock_code_flexible(code, soe_dict)
    status = 'PASS' if result == expected_name else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    print(f'  {status}: match({code}) = {result} (expected {expected_name})')

print()
print('All tests passed!' if all_pass else 'SOME TESTS FAILED!')
