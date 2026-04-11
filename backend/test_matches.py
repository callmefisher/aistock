import asyncio
import sys
sys.path.insert(0, '/app')
from services.workflow_executor import WorkflowExecutor
import pandas as pd

executor = WorkflowExecutor()

async def test():
    config_soe = {
        'source_dir': '国企',
        'new_column_name': '国企',
        'output_filename': 'output_5.xlsx'
    }

    df = pd.read_excel('/app/data/excel/2026-04-09/output_4.xlsx')
    print(f'Loaded output_4.xlsx: {len(df)} rows')

    result_soe = await executor._match_soe(config_soe, df, '2026-04-09')
    print(f'SOE match: {result_soe.get("message", "")}')

    config_sector = {
        'source_dir': '一级板块',
        'new_column_name': '一级板块',
        'output_filename': '2026-04-09.xlsx'
    }

    df2 = pd.read_excel('/app/data/excel/2026-04-09/output_5.xlsx')
    print(f'Loaded output_5.xlsx: {len(df2)} rows')

    result_sector = await executor._match_sector(config_sector, df2, '2026-04-09')
    print(f'Sector match: {result_sector.get("message", "")}')

    df_final = pd.read_excel('/app/data/excel/2026-04-09/2026-04-09.xlsx')
    print(f'Final rows: {len(df_final)}')
    print(f'Columns: {df_final.columns.tolist()}')

    guoqi_matched = (df_final['国企'].notna() & (df_final['国企'] != '')).sum()
    sector_matched = (df_final['一级板块'].notna() & (df_final['一级板块'] != '')).sum()
    print(f'Guoqi matched: {guoqi_matched}')
    print(f'Sector matched: {sector_matched}')

    if guoqi_matched > 0:
        print('Sample with Guoqi:')
        print(df_final[df_final['国企'].notna() & (df_final['国企'] != '')][['证券代码', '证券简称', '国企']].head(3))

    if sector_matched > 0:
        print('Sample with Sector:')
        print(df_final[df_final['一级板块'].notna() & (df_final['一级板块'] != '')][['证券代码', '证券简称', '一级板块']].head(3))

asyncio.run(test())