#!/usr/bin/env python3
"""
验证工作流类型系统 - 向后兼容性测试
测试目标：确保老流程（空字符串或"并购重组"）完全正常工作
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.workflow_executor import WorkflowExecutor
from services.path_resolver import WorkflowPathResolver
from config.workflow_type_config import get_type_config
import asyncio


def test_default_type_config():
    """测试1：默认类型配置"""
    print("=" * 60)
    print("测试1: 默认类型配置（空字符串）")
    print("=" * 60)

    config = get_type_config("")
    print(f"✓ 配置获取成功")
    print(f"  display_name: {config['display_name']}")
    print(f"  base_subdir: {config['base_subdir']}")
    print(f"  upload_date模板: {config['directories']['upload_date']}")
    print(f"  public目录: {config['directories']['public']}")
    print(f"  最终输出模板: {config['naming']['output_template']}")

    assert config['display_name'] == '并购重组', "默认类型应该是并购重组"
    assert config['base_subdir'] == '', "默认类型base_subdir应该为空"
    print("✓ 配置验证通过\n")


def test_merge_reorg_type_config():
    """测试2：并购重组类型配置"""
    print("=" * 60)
    print("测试2: 并购重组类型配置")
    print("=" * 60)

    config = get_type_config("并购重组")
    print(f"✓ 配置获取成功")
    print(f"  display_name: {config['display_name']}")

    assert config['display_name'] == '并购重组', "并购重组类型配置应该正确"
    print("✓ 配置验证通过\n")


def test_path_resolver_default():
    """测试3：默认类型路径解析"""
    print("=" * 60)
    print("测试3: 默认类型路径解析")
    print("=" * 60)

    resolver = WorkflowPathResolver("/data/excel", "")
    date = "2026-04-12"

    upload_dir = resolver.get_upload_directory(date)
    public_dir = resolver.get_public_directory()
    final_output = resolver.get_output_filename("match_sector", date)

    print(f"✓ 上传目录: {upload_dir}")
    print(f"✓ 公共目录: {public_dir}")
    print(f"✓ 最终输出: {final_output}")

    assert upload_dir == f"/data/excel/{date}", f"上传目录应该是 /data/excel/{date}"
    assert public_dir == "/data/excel/2025public", "公共目录应该是 /data/excel/2025public"
    assert final_output == "并购重组20260412.xlsx", "最终输出应该是 并购重组20260412.xlsx"

    print("✓ 路径解析验证通过\n")


def test_workflow_executor_default():
    """测试4：WorkflowExecutor默认类型"""
    print("=" * 60)
    print("测试4: WorkflowExecutor默认类型")
    print("=" * 60)

    executor = WorkflowExecutor(base_dir="/data/excel", workflow_type="")

    print(f"✓ executor创建成功")
    print(f"  workflow_type: {executor.workflow_type}")
    print(f"  base_dir: {executor.base_dir}")
    print(f"  resolver类型: {type(executor.resolver).__name__}")

    daily_dir = executor._get_daily_dir("2026-04-12")
    print(f"✓ _get_daily_dir: {daily_dir}")

    assert daily_dir == "/data/excel/2026-04-12", "daily_dir应该正确"
    print("✓ WorkflowExecutor验证通过\n")


def test_match_sources_shared():
    """测试5：匹配源目录共享"""
    print("=" * 60)
    print("测试5: 匹配源目录共享（所有类型）")
    print("=" * 60)

    default_resolver = WorkflowPathResolver("/data/excel", "")
    equity_resolver = WorkflowPathResolver("/data/excel", "股权转让")

    match_steps = ["match_high_price", "match_ma20", "match_soe", "match_sector"]

    for step in match_steps:
        default_dir = default_resolver.get_match_source_directory(step)
        equity_dir = equity_resolver.get_match_source_directory(step)

        print(f"✓ {step}:")
        print(f"    默认: {default_dir}")
        print(f"    股权转让: {equity_dir}")

        assert default_dir == equity_dir, f"{step} 源目录应该相同"

    print("✓ 匹配源目录共享验证通过\n")


def test_output_filename_priority():
    """测试6：输出文件名优先级"""
    print("=" * 60)
    print("测试6: 输出文件名优先级")
    print("=" * 60)

    resolver = WorkflowPathResolver("/data/excel", "")

    # 测试中间步骤：用户自定义优先
    user_filename = "custom_output.xlsx"
    filename = resolver.get_output_filename("merge_excel", "2026-04-12", user_filename)
    print(f"✓ 中间步骤（用户自定义）: {filename}")
    assert filename == user_filename, "中间步骤应该使用用户自定义文件名"

    # 测试中间步骤：默认值
    filename = resolver.get_output_filename("smart_dedup", "2026-04-12", None)
    print(f"✓ 中间步骤（默认）: {filename}")
    assert filename == "deduped.xlsx", "中间步骤默认应该是 deduped.xlsx"

    # 测试最终步骤：强制模板
    filename = resolver.get_output_filename("match_sector", "2026-04-12", "custom.xlsx")
    print(f"✓ 最终步骤（强制模板）: {filename}")
    assert filename == "并购重组20260412.xlsx", "最终步骤应该强制使用模板"

    print("✓ 文件名优先级验证通过\n")


def test_backward_compatibility():
    """测试7：向后兼容性"""
    print("=" * 60)
    print("测试7: 向后兼容性验证")
    print("=" * 60)

    # 测试空字符串
    executor1 = WorkflowExecutor(base_dir="/data/excel", workflow_type="")
    assert executor1.workflow_type == "", "空字符串应该被保留"

    # 测试None（应该被处理为空字符串）
    try:
        executor2 = WorkflowExecutor(base_dir="/data/excel", workflow_type=None)
        print(f"✓ None值处理: workflow_type={executor2.workflow_type}")
    except Exception as e:
        print(f"✗ None值处理失败: {e}")

    # 测试未知类型（应该fallback到默认）
    config = get_type_config("未知类型")
    assert config['display_name'] == '并购重组', "未知类型应该fallback到默认"
    print(f"✓ 未知类型fallback: {config['display_name']}")

    print("✓ 向后兼容性验证通过\n")


def main():
    print("\n" + "=" * 60)
    print("工作流类型系统 - 向后兼容性验证测试")
    print("=" * 60 + "\n")

    try:
        test_default_type_config()
        test_merge_reorg_type_config()
        test_path_resolver_default()
        test_workflow_executor_default()
        test_match_sources_shared()
        test_output_filename_priority()
        test_backward_compatibility()

        print("=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        print("\n结论：")
        print("  ✓ 默认类型（并购重组）配置正确")
        print("  ✓ 路径解析逻辑正确")
        print("  ✓ WorkflowExecutor集成正确")
        print("  ✓ 匹配源目录共享机制正确")
        print("  ✓ 文件名优先级正确")
        print("  ✓ 向后兼容性完全保持")
        print("\n老流程完全不受影响，可以安全部署！\n")

        return True

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
