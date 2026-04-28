"""path_resolver 的 auto_copy 开关：百日新高/20日均线 禁用历史回溯复制。"""
import os
import tempfile

from services.path_resolver import WorkflowPathResolver


def test_resolve_source_entry_string_fallback():
    """字符串形态的 match_sources 条目 → auto_copy 默认 True。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake", workflow_type="")
    dir_name, auto_copy = resolver._resolve_source_entry("match_soe")
    assert dir_name == "国企"
    assert auto_copy is True


def test_resolve_source_entry_dict_form():
    """dict 形态的 match_sources 条目 → 返回 dir + auto_copy。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake", workflow_type="")
    for step in ("match_high_price", "match_ma20"):
        dir_name, auto_copy = resolver._resolve_source_entry(step)
        assert dir_name in ("百日新高", "20日均线")
        assert auto_copy is False


def test_ensure_match_source_files_auto_copy_false_does_not_copy():
    """百日新高 / 20日均线：即使历史日期有文件，也不复制到新目录。"""
    with tempfile.TemporaryDirectory() as base:
        resolver = WorkflowPathResolver(base_dir=base, workflow_type="")

        for src_dir, step in [("百日新高", "match_high_price"), ("20日均线", "match_ma20")]:
            prev = os.path.join(base, "2026-04-20", src_dir)
            os.makedirs(prev, exist_ok=True)
            # 放一个历史文件
            with open(os.path.join(prev, "history.xlsx"), "w") as f:
                f.write("x")

            target = resolver.ensure_match_source_files(step, "2026-04-28")
            assert os.path.isdir(target)
            # 关键断言：新目录不应复制任何历史文件
            assert os.listdir(target) == [], (
                f"auto_copy=False 应阻止复制，但 {target} 里出现: {os.listdir(target)}"
            )


def test_ensure_match_source_files_auto_copy_true_still_copies():
    """国企 / 一级板块 保持原行为，历史文件会被复制过来。"""
    with tempfile.TemporaryDirectory() as base:
        resolver = WorkflowPathResolver(base_dir=base, workflow_type="")

        for src_dir, step in [("国企", "match_soe"), ("一级板块", "match_sector")]:
            prev = os.path.join(base, "2026-04-27", src_dir)
            os.makedirs(prev, exist_ok=True)
            with open(os.path.join(prev, "old.xlsx"), "w") as f:
                f.write("x")

            target = resolver.ensure_match_source_files(step, "2026-04-28")
            files = sorted(os.listdir(target))
            assert files == ["old.xlsx"], (
                f"auto_copy=True 应触发回溯复制，但 {target} 里没有 old.xlsx: {files}"
            )


def test_ensure_match_source_files_existing_dir_untouched():
    """目录已存在 → 不论 auto_copy 开关，都不再复制（沿用旧规则）。"""
    with tempfile.TemporaryDirectory() as base:
        resolver = WorkflowPathResolver(base_dir=base, workflow_type="")

        # 预先创建空目录
        target_pre = os.path.join(base, "2026-04-28", "百日新高")
        os.makedirs(target_pre, exist_ok=True)

        # 历史目录有文件
        prev = os.path.join(base, "2026-04-27", "百日新高")
        os.makedirs(prev, exist_ok=True)
        with open(os.path.join(prev, "history.xlsx"), "w") as f:
            f.write("x")

        target = resolver.ensure_match_source_files("match_high_price", "2026-04-28")
        assert target == target_pre
        assert os.listdir(target) == []  # 仍为空
