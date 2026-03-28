import pandas as pd
import re
from typing import Dict, List, Optional, Any, Tuple
import logging
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self, openai_api_key: Optional[str] = None, openai_api_base: Optional[str] = None):
        self.client = None
        if openai_api_key:
            self.client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_api_base
            )
    
    def parse_natural_language(self, natural_language: str) -> Dict[str, Any]:
        if not self.client:
            return self._parse_with_rules(natural_language)
        
        try:
            prompt = f"""
你是一个Excel公式和筛选条件转换专家。请将以下自然语言规则转换为Excel公式和筛选条件。

自然语言规则：{natural_language}

请返回JSON格式的结果，包含以下字段：
1. filter_conditions: 筛选条件列表，每个条件包含 {{"column": "列名", "operator": "操作符", "value": "值"}}
2. excel_formula: Excel公式（如果需要）
3. description: 规则描述

操作符可以是：equals, not_equals, greater_than, less_than, greater_equal, less_equal, contains, not_contains, in, not_in

示例输入："筛选PE小于20且ROE大于15%的股票"
示例输出：
{{
    "filter_conditions": [
        {{"column": "PE", "operator": "less_than", "value": 20}},
        {{"column": "ROE", "operator": "greater_than", "value": 15}}
    ],
    "excel_formula": "=AND(PE<20, ROE>15)",
    "description": "筛选PE小于20且ROE大于15%的股票"
}}

请只返回JSON，不要包含其他内容。
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个Excel公式转换专家，只返回JSON格式的结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)
            
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            logger.error(f"AI解析失败: {str(e)}")
            return self._parse_with_rules(natural_language)
    
    def _parse_with_rules(self, natural_language: str) -> Dict[str, Any]:
        try:
            filter_conditions = []
            
            patterns = {
                r'(\w+)\s*小于\s*(\d+\.?\d*)': ('less_than', float),
                r'(\w+)\s*大于\s*(\d+\.?\d*)': ('greater_than', float),
                r'(\w+)\s*小于等于\s*(\d+\.?\d*)': ('less_equal', float),
                r'(\w+)\s*大于等于\s*(\d+\.?\d*)': ('greater_equal', float),
                r'(\w+)\s*等于\s*(\d+\.?\d*)': ('equals', float),
                r'(\w+)\s*等于\s*["\']?([^"\']+)["\']?': ('equals', str),
                r'(\w+)\s*包含\s*["\']?([^"\']+)["\']?': ('contains', str),
            }
            
            for pattern, (operator, value_type) in patterns.items():
                matches = re.finditer(pattern, natural_language)
                for match in matches:
                    column = match.group(1)
                    value_str = match.group(2)
                    
                    try:
                        value = value_type(value_str)
                    except:
                        value = value_str
                    
                    filter_conditions.append({
                        "column": column,
                        "operator": operator,
                        "value": value
                    })
            
            if filter_conditions:
                return {
                    "success": True,
                    "result": {
                        "filter_conditions": filter_conditions,
                        "excel_formula": self._generate_formula(filter_conditions),
                        "description": natural_language
                    }
                }
            else:
                return {
                    "success": False,
                    "result": None,
                    "message": "无法解析规则"
                }
        except Exception as e:
            logger.error(f"规则解析失败: {str(e)}")
            return {
                "success": False,
                "result": None,
                "message": f"规则解析失败: {str(e)}"
            }
    
    def _generate_formula(self, conditions: List[Dict]) -> str:
        if not conditions:
            return ""
        
        formulas = []
        for cond in conditions:
            column = cond['column']
            operator = cond['operator']
            value = cond['value']
            
            if operator == 'less_than':
                formulas.append(f"{column}<{value}")
            elif operator == 'greater_than':
                formulas.append(f"{column}>{value}")
            elif operator == 'less_equal':
                formulas.append(f"{column}<={value}")
            elif operator == 'greater_equal':
                formulas.append(f"{column}>={value}")
            elif operator == 'equals':
                if isinstance(value, str):
                    formulas.append(f'{column}="{value}"')
                else:
                    formulas.append(f"{column}={value}")
            elif operator == 'contains':
                formulas.append(f'ISNUMBER(SEARCH("{value}",{column}))')
        
        if len(formulas) == 1:
            return f"={formulas[0]}"
        else:
            return f"=AND({','.join(formulas)})"
    
    def apply_rules(
        self,
        df: pd.DataFrame,
        filter_conditions: List[Dict],
        excel_formula: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        try:
            filtered_df = df.copy()
            applied_conditions = []
            
            for condition in filter_conditions:
                column = condition['column']
                operator = condition['operator']
                value = condition['value']
                
                if column not in filtered_df.columns:
                    logger.warning(f"列 {column} 不存在，跳过该条件")
                    continue
                
                if operator == 'less_than':
                    filtered_df = filtered_df[filtered_df[column] < value]
                elif operator == 'greater_than':
                    filtered_df = filtered_df[filtered_df[column] > value]
                elif operator == 'less_equal':
                    filtered_df = filtered_df[filtered_df[column] <= value]
                elif operator == 'greater_equal':
                    filtered_df = filtered_df[filtered_df[column] >= value]
                elif operator == 'equals':
                    filtered_df = filtered_df[filtered_df[column] == value]
                elif operator == 'not_equals':
                    filtered_df = filtered_df[filtered_df[column] != value]
                elif operator == 'contains':
                    filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(str(value), na=False)]
                elif operator == 'not_contains':
                    filtered_df = filtered_df[~filtered_df[column].astype(str).str.contains(str(value), na=False)]
                elif operator == 'in':
                    if isinstance(value, list):
                        filtered_df = filtered_df[filtered_df[column].isin(value)]
                elif operator == 'not_in':
                    if isinstance(value, list):
                        filtered_df = filtered_df[~filtered_df[column].isin(value)]
                
                applied_conditions.append(condition)
            
            stats = {
                "original_rows": len(df),
                "filtered_rows": len(filtered_df),
                "removed_rows": len(df) - len(filtered_df),
                "applied_conditions": applied_conditions
            }
            
            return filtered_df, stats
        except Exception as e:
            logger.error(f"规则应用失败: {str(e)}")
            return df, {
                "error": str(e),
                "original_rows": len(df),
                "filtered_rows": len(df)
            }
    
    def validate_rules(self, filter_conditions: List[Dict], columns: List[str]) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        for condition in filter_conditions:
            column = condition.get('column')
            operator = condition.get('operator')
            value = condition.get('value')
            
            if not column:
                errors.append("条件缺少列名")
                continue
            
            if column not in columns:
                warnings.append(f"列 '{column}' 不存在于数据中")
            
            if not operator:
                errors.append(f"条件缺少操作符（列：{column}）")
            elif operator not in ['equals', 'not_equals', 'greater_than', 'less_than', 
                                   'greater_equal', 'less_equal', 'contains', 'not_contains', 
                                   'in', 'not_in']:
                errors.append(f"不支持的操作符：{operator}")
            
            if value is None:
                errors.append(f"条件缺少值（列：{column}）")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
