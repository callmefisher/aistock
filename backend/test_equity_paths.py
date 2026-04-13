#!/usr/bin/env python3
"""
测试股权转让类型的目录路径
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.path_resolver import WorkflowPathResolver

def test_equity_transfer_paths():
    """测试股权转让类型的目录路径"""
    print("=" * 70)
    print("测试股权转让类型的目录路径")
    print("=" * 70)

    base_dir = "/data/excel"
    date_str = "2026-04-12"

    resolver = WorkflowPathResolver(base_dir, "股权转让")

    print(f"\n工作流类型: 股权转让")
    print(f"基础目录: {base_dir}")
    print(f"日期: {date_str}")

    print(f"\n生成的路径:")
    upload_dir = resolver.get_upload_directory(date_str)
    print(f"  上传目录: {upload_dir}")
    print(f"  预期: /data/excel/股权转让/2026-04-12")
    print(f"  匹配: {'✓' if upload_dir == '/data/excel/股权转让/2026-04-12' else '✗'}")

    public_dir = resolver.get_public_directory()
    print(f"\n  公共目录: {public_dir}")
    print(f"  预期: /data/excel/股权转让/public")
    print(f"  匹配: {'✓' if public_dir == '/data/excel/股权转让/public' else '✗'}")

    print(f"\n配置详情:")
    print(f"  base_subdir: {resolver.config.get('base_subdir')}")
    print(f"  upload_date模板: {resolver.config['directories']['upload_date']}")
    print(f"  public模板: {resolver.config['directories']['public']}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    test_equity_transfer_paths()
