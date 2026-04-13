import pandas as pd
import time
import glob
import os

sources = {
    "国企": "data/excel/国企",
    "百日新高": "data/excel/百日新高",
    "20日均线": "data/excel/20日均线",
    "一级板块": "data/excel/一级板块",
}

print("=== 单次加载耗时 ===")
for name, path in sources.items():
    if not os.path.exists(path):
        print(f"  {name}: 目录不存在")
        continue
    start = time.time()
    files = glob.glob(os.path.join(path, "*.xlsx"))
    files.extend(glob.glob(os.path.join(path, "*.xls")))
    total_rows = 0
    for f in files:
        df = pd.read_excel(f, dtype=str)
        total_rows += len(df)
    elapsed = time.time() - start
    print(f"  {name}: {elapsed:.3f}s, {total_rows} rows")

print()
print("=== 模拟工作流完整执行（4个匹配步骤各加载1次） ===")
start = time.time()
for name, path in sources.items():
    if not os.path.exists(path):
        continue
    files = glob.glob(os.path.join(path, "*.xlsx"))
    files.extend(glob.glob(os.path.join(path, "*.xls")))
    for f in files:
        df = pd.read_excel(f, dtype=str)
elapsed = time.time() - start
print(f"  总耗时: {elapsed:.3f}s")

print()
print("=== 模拟5次工作流执行 ===")
start = time.time()
for i in range(5):
    for name, path in sources.items():
        if not os.path.exists(path):
            continue
        files = glob.glob(os.path.join(path, "*.xlsx"))
        files.extend(glob.glob(os.path.join(path, "*.xls")))
        for f in files:
            df = pd.read_excel(f, dtype=str)
elapsed = time.time() - start
print(f"  总耗时: {elapsed:.3f}s, 平均每次: {elapsed/5:.3f}s")
