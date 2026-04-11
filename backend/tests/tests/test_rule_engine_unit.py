import pytest
import pandas as pd
from services.rule_engine import RuleEngine
from models.models import Rule


class TestRuleEngine:
    """规则引擎单元测试"""

    def test_parse_simple_rule_pe_less_than(self):
        """测试解析简单规则：PE小于"""
        engine = RuleEngine()
        result = engine.parse_natural_language("筛选PE小于20的股票")

        assert result['success'] is True
        assert len(result['result']['filter_conditions']) == 1
        assert result['result']['filter_conditions'][0]['column'] == 'PE'
        assert result['result']['filter_conditions'][0]['operator'] == 'less_than'
        assert result['result']['filter_conditions'][0]['value'] == 20

    def test_parse_simple_rule_pe_greater_than(self):
        """测试解析简单规则：PE大于"""
        engine = RuleEngine()
        result = engine.parse_natural_language("筛选ROE大于15")

        assert result['success'] is True
        assert len(result['result']['filter_conditions']) == 1
        assert result['result']['filter_conditions'][0]['column'] == 'ROE'
        assert result['result']['filter_conditions'][0]['operator'] == 'greater_than'
        assert result['result']['filter_conditions'][0]['value'] == 15

    def test_parse_multiple_rules_with_and(self):
        """测试解析多条件规则：AND"""
        engine = RuleEngine()
        result = engine.parse_natural_language("筛选PE小于20且ROE大于15%的股票")

        assert result['success'] is True
        assert len(result['result']['filter_conditions']) == 2
        conditions = result['result']['filter_conditions']
        assert conditions[0]['column'] == 'PE'
        assert conditions[0]['operator'] == 'less_than'
        assert conditions[1]['column'] == 'ROE'
        assert conditions[1]['operator'] == 'greater_than'

    def test_parse_multiple_rules_with_or(self):
        """测试解析多条件规则：OR"""
        engine = RuleEngine()
        result = engine.parse_natural_language("筛选PE小于10或ROE大于20的股票")

        assert result['success'] is True
        assert len(result['result']['filter_conditions']) == 2

    def test_parse_invalid_rule(self):
        """测试解析无效规则 - 返回无法解析结果"""
        engine = RuleEngine()
        result = engine.parse_natural_language("这是一个完全无法解析的字符串xyz123")

        assert result['success'] is False
        assert result['result'] is None
        assert 'message' in result

    def test_apply_rules_single_condition(self):
        """测试应用单条件规则"""
        engine = RuleEngine()

        df = pd.DataFrame({
            'PE': [10, 25, 15, 30],
            'ROE': [20, 10, 18, 5],
            'Name': ['Stock A', 'Stock B', 'Stock C', 'Stock D']
        })

        conditions = [
            {'column': 'PE', 'operator': 'less_than', 'value': 20}
        ]

        filtered_df, stats = engine.apply_rules(df, conditions)

        assert len(filtered_df) == 2
        assert stats['original_rows'] == 4
        assert stats['filtered_rows'] == 2
        assert stats['removed_rows'] == 2

    def test_apply_rules_multiple_conditions(self):
        """测试应用多条件规则"""
        engine = RuleEngine()

        df = pd.DataFrame({
            'PE': [10, 25, 15, 30],
            'ROE': [20, 10, 18, 5],
            'Name': ['Stock A', 'Stock B', 'Stock C', 'Stock D']
        })

        conditions = [
            {'column': 'PE', 'operator': 'less_than', 'value': 20},
            {'column': 'ROE', 'operator': 'greater_than', 'value': 15}
        ]

        filtered_df, stats = engine.apply_rules(df, conditions)

        assert len(filtered_df) == 2
        assert stats['original_rows'] == 4
        assert stats['filtered_rows'] == 2

    def test_apply_rules_no_match(self):
        """测试应用规则无匹配"""
        engine = RuleEngine()

        df = pd.DataFrame({
            'PE': [10, 25, 15, 30],
            'Name': ['Stock A', 'Stock B', 'Stock C', 'Stock D']
        })

        conditions = [
            {'column': 'PE', 'operator': 'greater_than', 'value': 100}
        ]

        filtered_df, stats = engine.apply_rules(df, conditions)

        assert len(filtered_df) == 0
        assert stats['filtered_rows'] == 0

    def test_validate_rules_valid(self):
        """测试验证有效规则"""
        engine = RuleEngine()

        conditions = [
            {'column': 'PE', 'operator': 'less_than', 'value': 20}
        ]

        columns = ['PE', 'ROE', 'Name']
        validation = engine.validate_rules(conditions, columns)

        assert validation['valid'] is True
        assert len(validation['errors']) == 0

    def test_validate_rules_missing_column(self):
        """测试验证规则列不存在"""
        engine = RuleEngine()

        conditions = [
            {'column': 'Price', 'operator': 'less_than', 'value': 100}
        ]

        columns = ['PE', 'ROE', 'Name']
        validation = engine.validate_rules(conditions, columns)

        assert validation['valid'] is True
        assert len(validation['warnings']) == 1
        assert '不存在' in validation['warnings'][0]

    def test_validate_rules_invalid_operator(self):
        """测试验证规则无效操作符"""
        engine = RuleEngine()

        conditions = [
            {'column': 'PE', 'operator': 'invalid_op', 'value': 20}
        ]

        columns = ['PE', 'ROE', 'Name']
        validation = engine.validate_rules(conditions, columns)

        assert validation['valid'] is False
        assert len(validation['errors']) > 0

    def test_generate_excel_formula(self):
        """测试生成Excel公式"""
        engine = RuleEngine()

        conditions = [
            {'column': 'PE', 'operator': 'less_than', 'value': 20}
        ]

        formula = engine.generate_excel_formula(conditions)

        assert '=' in formula
        assert 'PE' in formula
        assert '<' in formula
        assert '20' in formula

    def test_excel_formula_with_multiple_conditions(self):
        """测试生成多条件Excel公式"""
        engine = RuleEngine()

        conditions = [
            {'column': 'PE', 'operator': 'less_than', 'value': 20},
            {'column': 'ROE', 'operator': 'greater_than', 'value': 15}
        ]

        formula = engine.generate_excel_formula(conditions)

        assert '=' in formula
        assert 'AND' in formula
