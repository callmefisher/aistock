import pandas as pd

soe_df = pd.read_excel('/app/data/excel/国企/问财国央企 0331.xlsx')
all_soe_stocks = {}
for _, row in soe_df.iterrows():
    stock_code = ''
    for col in ['股票代码.1', '股票代码', '证券代码']:
        if col in soe_df.columns and pd.notna(row[col]):
            val = str(row[col]).strip()
            if val and val != 'nan':
                stock_code = val
                break
    stock_name = str(row['股票简称']).strip() if pd.notna(row['股票简称']) else ''
    if stock_code and stock_code != 'nan':
        all_soe_stocks[stock_code] = stock_name

print('Dict size:', len(all_soe_stocks))
print('601398 in dict:', '601398' in all_soe_stocks)
print('601398.SH in dict:', '601398.SH' in all_soe_stocks)

def match(code):
    s = str(code).strip()
    if s in all_soe_stocks:
        return all_soe_stocks[s]
    num = s.split('.')[0] if '.' in s else s
    if num in all_soe_stocks:
        return all_soe_stocks[num]
    return ''

print()
print('Test results:')
print('601398.SH ->', match('601398.SH'))
print('601398 ->', match('601398'))
print('601939.SH ->', match('601939.SH'))
print('601988.SH ->', match('601988.SH'))