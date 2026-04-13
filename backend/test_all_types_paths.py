#!/usr/bin/env python3
"""
测试所有类型的目录路径
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.path_resolver import WorkflowPathResolver

def test_all_types():
    """测试所有类型的目录路径"""
    print("=" * 70)
    print("测试所有类型的目录路径")
    print("=" * 70)

    base_dir = "/data/excel"
    date_str = "2026-04-12"

    # 测试默认类型（空字符串）
    print("\n【类型1：默认（空字符串）】")
    resolver1 = WorkflowPathResolver(base_dir, "")
    print(f"  上传目录: {resolver1.get_upload_directory(date_str)}")
    print(f"  公共目录: {resolver1.get_public_directory()}")
    print(f"  预期上传: /data/excel/2026-04-12")
    print(f"  预期公共: /data/excel/2025public")

    # 测试并购重组类型
    print("\n【类型2：并购重组】")
    resolver2 = WorkflowPathResolver(base_dir, "并购重组")
    print(f"  上传目录: {resolver2.get_upload_directory(date_str)}")
    print(f"  公共目录: {resolver2.get_public_directory()}")
    print(f"  预期上传: /data/excel/2026-04-12")
    print(f"  预期公共: /data/excel/2025public")

    # 测试股权转让类型
    print("\n【类型3：股权转让】")
    resolver3 = WorkflowPathResolver(base_dir, "股权转让")
    print(f"  上传目录: {resolver3.get_upload_directory(date_str)}")
    print(f"  公共目录: {resolver3.get_public_directory()}")
    print(f"  预期上传: /data/excel/股权转让/2026-04-12")
    print(f"  预期公共: /data/excel/股权转让/public")

    print("\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)

    # 验证默认类型
    upload1 = resolver1.get_upload_directory(date_str)
    public1 = resolver1.get_public_directory()
    print(f"\n默认类型:")
    print(f"  上传目录正确: {'✓' if upload1 == '/data/excel/2026-04-12' else '✗'}")
    print(f"  公共目录正确: {'✓' if public1 == '/data/excel/2025public' else '✗'}")

    # 验证并购重组类型
    upload2 = resolver2.get_upload_directory(date_str)
    public2 = resolver2.get_public_directory()
    print(f"\n并购重组类型:")
    print(f"  上传目录正确: {'✓' if upload2 == '/data/excel/2026-04-12' else '✗'}")
    print(f"  公共目录正确: {'✓' if public2 == '/data/excel/2025public' else '✗'}")

    # 验证股权转让类型
    upload3 = resolver3.get_upload_directory(date_str)
    public3 = resolver3.get_public_directory()
    print(f"\n股权转让类型:")
    print(f"  上传目录正确: {'✓' if upload3 == '/data/excel/股权转让/2026-04-12' else '✗'}")
    print(f"  公共目录正确: {'✓' if public3 == '/data/excel/股权转让/public' else '✗'}")

if __name__ == "__main__":
    test_all_types()
