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

print('Total loaded:', len(all_soe_stocks))
print('601398 in dict:', '601398' in all_soe_stocks)
print('601939 in dict:', '601939' in all_soe_stocks)
print('601988 in dict:', '601988' in all_soe_stocks)
print()
print('601398 ->', all_soe_stocks.get('601398', 'NOT FOUND'))
print('601939 ->', all_soe_stocks.get('601939', 'NOT FOUND'))
print('601988 ->', all_soe_stocks.get('601988', 'NOT FOUND'))