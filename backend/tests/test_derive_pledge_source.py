import pytest
from services.workflow_executor import WorkflowExecutor


@pytest.fixture
def executor():
    return WorkflowExecutor(base_dir="/tmp", workflow_type="质押")


class TestDerivePledgeSource:
    def test_file_name_big(self, executor):
        assert executor._derive_pledge_source("中大盘20260420.xlsx", "Sheet1") == "中大盘"

    def test_file_name_small(self, executor):
        assert executor._derive_pledge_source("小盘20260420.xlsx", "任意") == "小盘"

    def test_file_name_both_missing_sheet_big(self, executor):
        assert executor._derive_pledge_source("pledge.xlsx", "中大盘20260420") == "中大盘"

    def test_file_name_both_missing_sheet_unknown(self, executor):
        assert executor._derive_pledge_source("pledge.xlsx", "Sheet1") == "小盘"

    def test_file_name_wins_over_sheet(self, executor):
        assert executor._derive_pledge_source("中大盘.xlsx", "小盘20260420") == "中大盘"

    def test_empty_args(self, executor):
        assert executor._derive_pledge_source("", "") == "小盘"

    def test_none_args(self, executor):
        assert executor._derive_pledge_source(None, None) == "小盘"

    def test_file_name_not_prefix_falls_back_to_sheet(self, executor):
        """文件名含中大盘但不是前缀 → 不匹配，回退到 sheet 名。"""
        assert executor._derive_pledge_source("2026中大盘汇总.xlsx", "Sheet1") == "小盘"

    def test_file_name_substring_xiaopan_not_matched(self, executor):
        """文件名含小盘但不是前缀 → 不匹配，回退默认。"""
        assert executor._derive_pledge_source("非小盘.xlsx", "Sheet1") == "小盘"
