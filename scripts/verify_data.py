import pymysql, json, zlib
import pandas as pd

conn = pymysql.connect(
    host="127.0.0.1", port=3306, user="stock_user",
    password="stock_password", database="stock_pool", charset="utf8mb4"
)
cur = conn.cursor()
cur.execute(
    "SELECT data_compressed FROM workflow_results "
    "WHERE workflow_type IN ('', '并购重组') "
    "AND date_str = '2026-04-30' AND step_type = 'final' "
    "ORDER BY created_at DESC LIMIT 1"
)
row = cur.fetchone()
if row and row[0]:
    decompressed = zlib.decompress(row[0])
    records = json.loads(decompressed.decode("utf-8"))
    df = pd.DataFrame(records)
    print(f"Columns: {list(df.columns)}")
    ma20_cols = [c for c in df.columns if "20" in c or "均线" in c]
    print(f"MA20 related columns: {ma20_cols}")
    for col in ma20_cols:
        sample = df[col].dropna().head(5).tolist()
        print(f"  {col} sample: {sample}")
conn.close()
