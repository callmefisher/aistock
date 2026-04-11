import pytest
import pandas as pd
from services.rule_engine import RuleEngine


def test_parse_simple_rule():
    engine = RuleEngine()
    result = engine.parse_natural_language("筛选PE小于20的股票")
    
    assert result['success'] == True
    assert len(result['result']['filter_conditions']) == 1
    assert result['result']['filter_conditions'][0]['column'] == 'PE'
    assert result['result']['filter_conditions'][0]['operator'] == 'less_than'
    assert result['result']['filter_conditions'][0]['value'] == 20


def test_parse_multiple_rules():
    engine = RuleEngine()
    result = engine.parse_natural_language("筛选PE小于20且ROE大于15%的股票")
    
    assert result['success'] == True
    assert len(result['result']['filter_conditions']) == 2


def test_apply_rules():
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
    assert stats['removed_rows'] == 2


def test_validate_rules():
    engine = RuleEngine()
    
    conditions = [
        {'column': 'PE', 'operator': 'less_than', 'value': 20}
    ]
    
    columns = ['PE', 'ROE', 'Name']
    validation = engine.validate_rules(conditions, columns)
    
    assert validation['valid'] == True
    assert len(validation['errors']) == 0


def test_validate_rules_missing_column():
    engine = RuleEngine()
    
    conditions = [
        {'column': 'Price', 'operator': 'less_than', 'value': 100}
    ]
    
    columns = ['PE', 'ROE', 'Name']
    validation = engine.validate_rules(conditions, columns)
    
    assert validation['valid'] == True
    assert len(validation['warnings']) == 1
