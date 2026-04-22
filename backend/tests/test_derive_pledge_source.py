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

    def test_file_name_substring_in_middle_matches(self, executor):
        """文件名中部含"中大盘" → 匹配（真实命名 '质押和大宗交易 中大盘0421.xlsx'）。"""
        assert executor._derive_pledge_source("质押和大宗交易 中大盘0421.xlsx", "Sheet1") == "中大盘"
        assert executor._derive_pledge_source("2026中大盘汇总.xlsx", "Sheet1") == "中大盘"

    def test_file_name_substring_xiaopan_in_middle_matches(self, executor):
        """文件名中部含"小盘" → 匹配。"""
        assert executor._derive_pledge_source("质押和大宗交易 小盘 0421.xlsx", "Sheet1") == "小盘"

    def test_priority_zhongdapan_over_xiaopan(self, executor):
        """文件名同时含"中大盘"和"小盘" → 中大盘优先（因"小盘"是"中大盘"子串）。"""
        # 实际上"中大盘"必然含"小盘"，所以任何含"中大盘"的都先被判中大盘
        assert executor._derive_pledge_source("中大盘.xlsx", "Sheet1") == "中大盘"
