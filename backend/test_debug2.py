#!/usr/bin/env python3
import pandas as pd
import tempfile
import os
import sys
import asyncio
sys.path.insert(0, '/Users/xiayanji/qbox/aistock/backend')
from services.workflow_executor import WorkflowExecutor

with tempfile.TemporaryDirectory() as tmpdir:
    df1 = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})
    df2 = pd.DataFrame({'A': [5, 6], 'B': [7, 8]})
    df1.to_excel(os.path.join(tmpdir, 'file1.xlsx'), index=False)
    df2.to_excel(os.path.join(tmpdir, 'file2.xlsx'), index=False)

    public_dir = os.path.join(tmpdir, '2025public')
    os.makedirs(public_dir, exist_ok=True)
    df3 = pd.DataFrame({'A': [9, 10], 'B': [11, 12]})
    df3.to_excel(os.path.join(public_dir, 'public1.xlsx'), index=False)

    print(f"tmpdir: {tmpdir}")
    print(f"当日目录: {tmpdir}")
    print(f"当日目录文件: {os.listdir(tmpdir)}")
    print(f"public目录: {public_dir}")
    print(f"public目录文件: {os.listdir(public_dir)}")

    executor = WorkflowExecutor(base_dir=tmpdir)
    files = executor._get_excel_files_in_dir(tmpdir)
    print(f"当日目录Excel文件: {files}")
    public_files = executor._get_excel_files_in_dir(public_dir)
    print(f"public目录Excel文件: {public_files}")
