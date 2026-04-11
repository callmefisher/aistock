import pytest
import pandas as pd
from service.query_service import AIQueryService


class TestAIQueryService:
    """AI查询服务测试 - 本地规则模板"""

    def setup_method(self):
        self.service = AIQueryService()

    def test_parse_query_consume_industry_high_growth(self):
        """测试解析消费行业高增长查询"""
        query = "查询近三年净利润增长均超过20%且市盈率低于30倍的消费股"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert result["sql"] is not None
        assert "消费" in result["sql"]
        assert "pe_ratio < 30" in result["sql"]
        assert "net_profit_yoy > 20" in result["sql"]
        assert "消费" in result["explanation"]

    def test_parse_query_empty_query(self):
        """测试解析空查询"""
        query = ""

        result = self.service.parse_query(query)

        assert result["success"] is False
        assert result["sql"] is None

    def test_parse_query_random_text(self):
        """测试解析随机文本"""
        query = "今天天气真好"

        result = self.service.parse_query(query)

        assert result["success"] is False

    def test_parse_query_stock_daily_with_dates(self):
        """测试解析股票日线日期范围查询"""
        query = "查询2026-01-01到2026-04-09的股票数据"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "2026-01-01" in result["sql"]
        assert "2026-04-09" in result["sql"]
        assert "fact_daily_bar" in result["sql"]

    def test_parse_query_lowest_pe_stocks(self):
        """测试解析最低市盈率股票查询"""
        query = "查询市盈率最低的前10只股票"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "pe_ratio ASC" in result["sql"]
        assert "LIMIT 10" in result["sql"]

    def test_parse_query_only_industry(self):
        """测试仅按行业查询"""
        query = "查询银行行业的股票"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "银行" in result["sql"] or "%银行%" in result["sql"]

    def test_parse_query_invalid_sql_chars(self):
        """测试解析包含SQL注入风险字符"""
        query = "查询'; DROP TABLE users; --"

        result = self.service.parse_query(query)

        assert result["success"] is False or result["sql"] is None

    def test_parse_query_very_long_query(self):
        """测试解析超长查询"""
        query = "查询" + "近三年" + "净利润增长均超过20%" * 100 + "且市盈率低于30倍的消费股"

        result = self.service.parse_query(query)

        assert result["success"] is True

    def test_parse_query_special_chars(self):
        """测试解析包含特殊字符"""
        query = "查询 @#$%^&*() 股票数据"

        result = self.service.parse_query(query)

        assert result["success"] is False or result["explanation"] is not None

    def test_parse_query_multiple_conditions(self):
        """测试解析多条件查询"""
        query = "查询近5年净利润增长超过30%且市盈率低于25倍的消费股"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "5" in result["sql"] or "5 YEAR" in result["sql"]
        assert "30" in result["sql"]
        assert "25" in result["sql"]

    def test_parse_query_no_matching_template(self):
        """测试解析无匹配模板"""
        query = "请告诉我为什么天是蓝色的"

        result = self.service.parse_query(query)

        assert result["success"] is False

    def test_parse_query_partial_keyword(self):
        """测试解析部分关键词"""
        query = "净利润增长"

        result = self.service.parse_query(query)

        assert result["success"] is False or result["sql"] is not None

    def test_parse_query_malformed_date(self):
        """测试解析格式错误的日期"""
        query = "查询2026年到2026年的股票数据"

        result = self.service.parse_query(query)

        assert result["success"] is False or "2026-01-01" not in result["sql"]


class TestQueryTemplates:
    """查询模板测试"""

    def setup_method(self):
        self.service = AIQueryService()

    def test_template_high_growth_stocks(self):
        """测试高增长股票模板"""
        query = "净利润增长超过50%的股票"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "50" in result["sql"]

    def test_template_low_pe_stocks(self):
        """测试低市盈率股票模板"""
        query = "市盈率低于10的股票"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "10" in result["sql"]

    def test_template_date_range(self):
        """测试日期范围模板"""
        query = "2025-01-01到2026-01-01的行情数据"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "2025-01-01" in result["sql"]
        assert "2026-01-01" in result["sql"]

    def test_template_with_year_modifier(self):
        """测试年份修饰符"""
        query = "查询近2年净利润增长超过15%的股票"

        result = self.service.parse_query(query)

        assert result["success"] is True
        assert "2" in result["sql"] or "2 YEAR" in result["sql"]
