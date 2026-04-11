from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

COLUMN_NAMES_CN = {
    'stock_code': '证券代码',
    'stock_name': '证券名称',
    'trade_date': '交易日期',
    'open': '开盘价',
    'high': '最高价',
    'low': '最低价',
    'close': '收盘价',
    'volume': '成交量',
    'amount': '成交额',
    'change_pct': '涨跌幅',
    'pre_close': '前收价',
    'amplitude': '振幅',
    'turnover_rate': '换手率',
    'ma5': '5日均线',
    'ma10': '10日均线',
    'ma20': '20日均线',
    'ma30': '30日均线',
    'ma60': '60日均线',
    'ma120': '120日均线',
    'ma250': '250日均线',
    'volume_ratio': '量比',
    'pe_ratio': '市盈率',
    'pb_ratio': '市净率',
    'ps_ratio': '市销率',
    'industry_name': '行业',
    'report_date': '报告日期',
    'net_profit_yoy': '净利润同比增长',
    'signal': '信号',
    'max_close': '区间最高价',
    'min_close': '区间最低价',
    'change_amount': '涨跌额'
}


class QueryService:
    def __init__(self, database_url: str = None):
        if database_url is None:
            from core.config import settings
            database_url = settings.DATABASE_URL
        self.database_url = database_url

    async def execute_sql(self, sql: str, params: Dict = None) -> Dict[str, Any]:
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            engine = create_async_engine(self.database_url, echo=False)

            async with engine.connect() as conn:
                if params:
                    result = await conn.execute(text(sql), params)
                else:
                    result = await conn.execute(text(sql))

                columns = result.keys()
                rows_result = result.fetchall()
                if hasattr(rows_result, '__await__'):
                    rows = await rows_result
                else:
                    rows = rows_result

                data = [dict(zip(columns, row)) for row in rows]

                columns_cn = [COLUMN_NAMES_CN.get(col, col) for col in columns]

                return {
                    "success": True,
                    "data": data,
                    "columns": columns_cn,
                    "row_count": len(data)
                }
        except Exception as e:
            logger.error(f"SQL执行失败: {e}, SQL: {sql}")
            return {
                "success": False,
                "error": str(e),
                "message": f"SQL执行失败: {str(e)}"
            }

    async def query_stock_daily(
        self,
        stock_code: str = None,
        start_date: str = None,
        end_date: str = None,
        indicators: List[str] = None
    ) -> Dict[str, Any]:
        if indicators is None:
            indicators = ['trade_date', 'stock_code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'change_pct']

        valid_indicators = {
            'trade_date': 'trade_date',
            'stock_code': 'stock_code',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'change_pct': 'change_pct',
            'turnover_rate': 'turnover_rate',
            'amplitude': 'amplitude',
            'pre_close': 'pre_close',
            'ma5': 'ma5',
            'ma10': 'ma10',
            'ma20': 'ma20',
            'ma30': 'ma30',
            'ma60': 'ma60',
            'ma120': 'ma120',
            'ma250': 'ma250',
            'volume_ratio': 'volume_ratio',
        }

        select_cols = [valid_indicators.get(ind, ind) for ind in indicators]
        sql = f"SELECT {', '.join(select_cols)} FROM fact_daily_bar WHERE 1=1"
        params = {}

        if stock_code:
            sql += " AND stock_code = :stock_code"
            params['stock_code'] = stock_code

        if start_date:
            sql += " AND trade_date >= :start_date"
            params['start_date'] = start_date

        if end_date:
            sql += " AND trade_date <= :end_date"
            params['end_date'] = end_date

        sql += " ORDER BY trade_date DESC"

        return await self.execute_sql(sql, params)

    async def query_stocks(
        self,
        exchange: str = None,
        industry: str = None,
        pe_min: float = None,
        pe_max: float = None,
        pb_min: float = None,
        pb_max: float = None,
        sort_by: str = "stock_code",
        order: str = "asc",
        limit: int = 100
    ) -> Dict[str, Any]:
        sql = """
            SELECT s.stock_code, s.stock_name, s.exchange_code, s.industry_name,
                   f.pe_ratio, f.pb_ratio, f.roe, f.net_profit, f.revenue
            FROM dim_stock s
            LEFT JOIN fact_financial f ON s.stock_code = f.stock_code
            WHERE s.is_active = 1
        """
        params = {}

        if exchange:
            sql += " AND s.exchange_code = :exchange"
            params['exchange'] = exchange

        if industry:
            sql += " AND s.industry_name LIKE :industry"
            params['industry'] = f"%{industry}%"

        if pe_min is not None:
            sql += " AND f.pe_ratio >= :pe_min"
            params['pe_min'] = pe_min

        if pe_max is not None:
            sql += " AND f.pe_ratio <= :pe_max"
            params['pe_max'] = pe_max

        if pb_min is not None:
            sql += " AND f.pb_ratio >= :pb_min"
            params['pb_min'] = pb_min

        if pb_max is not None:
            sql += " AND f.pb_ratio <= :pb_max"
            params['pb_max'] = pb_max

        valid_sort_fields = ['stock_code', 'pe_ratio', 'pb_ratio', 'roe', 'net_profit', 'revenue']
        if sort_by not in valid_sort_fields:
            sort_by = 'stock_code'

        sql += f" ORDER BY {sort_by} {order.upper()}"
        sql += f" LIMIT {limit}"

        return await self.execute_sql(sql, params)

    async def query_financial(
        self,
        stock_code: str = None,
        start_date: str = None,
        end_date: str = None,
        report_type: str = None
    ) -> Dict[str, Any]:
        sql = """
            SELECT f.stock_code, s.stock_name, f.report_date, f.report_type,
                   f.revenue, f.revenue_yoy, f.net_profit, f.net_profit_yoy,
                   f.roe, f.gross_margin, f.net_margin, f.eps, f.bps,
                   f.pe_ratio, f.pb_ratio, f.ps_ratio
            FROM fact_financial f
            LEFT JOIN dim_stock s ON f.stock_code = s.stock_code
            WHERE 1=1
        """
        params = {}

        if stock_code:
            sql += " AND f.stock_code = :stock_code"
            params['stock_code'] = stock_code

        if start_date:
            sql += " AND f.report_date >= :start_date"
            params['start_date'] = start_date

        if end_date:
            sql += " AND f.report_date <= :end_date"
            params['end_date'] = end_date

        if report_type:
            sql += " AND f.report_type = :report_type"
            params['report_type'] = report_type

        sql += " ORDER BY f.report_date DESC"

        return await self.execute_sql(sql, params)


class AIQueryService:
    def __init__(self):
        self.query_templates = {
            "stock_by_industry": {
                "pattern": r"(.*?)行业",
                "sql_template": "SELECT s.stock_code, s.stock_name, s.industry_name, f.pe_ratio, f.pb_ratio FROM dim_stock s LEFT JOIN fact_financial f ON s.stock_code = f.stock_code WHERE s.industry_name LIKE '%{industry}%' AND s.is_active = 1"
            },
            "high_growth_stocks": {
                "pattern": r"净利润增长.*?(\d+)%",
                "sql_template": "SELECT s.stock_code, s.stock_name, f.net_profit_yoy, f.pe_ratio FROM dim_stock s JOIN fact_financial f ON s.stock_code = f.stock_code WHERE f.net_profit_yoy > {growth} AND s.is_active = 1"
            },
            "low_pe_stocks": {
                "pattern": r"市盈率.*?低于.*?(\d+)",
                "sql_template": "SELECT s.stock_code, s.stock_name, f.pe_ratio FROM dim_stock s JOIN fact_financial f ON s.stock_code = f.stock_code WHERE f.pe_ratio < {pe} AND f.pe_ratio > 0 AND s.is_active = 1"
            },
            "stock_daily_range": {
                "pattern": r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})",
                "sql_template": "SELECT b.stock_code, s.stock_name, b.trade_date, b.close, b.change_pct, b.volume FROM fact_daily_bar b LEFT JOIN dim_stock s ON b.stock_code = s.stock_code WHERE b.trade_date BETWEEN '{start}' AND '{end}' ORDER BY b.trade_date DESC"
            }
        }

    def parse_query(self, query: str) -> Dict[str, Any]:
        import re

        result = {
            "success": False,
            "sql": None,
            "explanation": None,
            "params": {}
        }

        if "消费" in query and ("净利润" in query or "增长" in query):
            years = 3
            growth = 20
            pe = 30

            year_match = re.search(r"(\d+)年", query)
            if year_match:
                years = int(year_match.group(1))

            growth_match = re.search(r"增长.*?(\d+)%", query)
            if growth_match:
                growth = int(growth_match.group(1))

            pe_match = re.search(r"市盈率.*?(\d+)", query)
            if pe_match:
                pe = int(pe_match.group(1))

            sql = f"""
                SELECT s.stock_code, s.stock_name, s.industry_name,
                       f.report_date, f.net_profit_yoy, f.pe_ratio
                FROM dim_stock s
                JOIN fact_financial f ON s.stock_code = f.stock_code
                WHERE s.industry_name LIKE '%消费%'
                  AND f.pe_ratio > 0 AND f.pe_ratio < {pe}
                  AND f.net_profit_yoy > {growth}
                  AND f.report_date >= DATE_SUB(CURDATE(), INTERVAL {years} YEAR)
                ORDER BY s.stock_code, f.report_date DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询消费行业，近{years}年净利润增长超过{growth}%且市盈率低于{pe}的股票"
            return result

        date_match = re.search(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})", query)
        if date_match:
            start = date_match.group(1)
            end = date_match.group(2)
            sql = f"SELECT b.stock_code, s.stock_name, b.trade_date, b.open, b.high, b.low, b.close, b.volume, b.amount, b.change_pct, b.ma5, b.ma10, b.ma20 FROM fact_daily_bar b LEFT JOIN dim_stock s ON b.stock_code = s.stock_code WHERE b.trade_date BETWEEN '{start}' AND '{end}' ORDER BY b.trade_date DESC"
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询从{start}到{end}的股票日线数据"
            return result

        if "日线" in query or ("查询" in query and "行情" in query) or "行情数据" in query:
            sql = "SELECT b.stock_code, s.stock_name, b.trade_date, b.open, b.high, b.low, b.close, b.volume, b.amount, b.change_pct, b.ma5, b.ma10, b.ma20 FROM fact_daily_bar b LEFT JOIN dim_stock s ON b.stock_code = s.stock_code ORDER BY b.trade_date DESC LIMIT 100"
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = "查询股票日线数据"
            return result

        if "行业" in query and "股票" in query:
            industry_match = re.search(r"(\w+)行业", query)
            industry = industry_match.group(1) if industry_match else query.replace("查询", "").replace("行业", "").replace("的股票", "").strip()
            sql = f"SELECT s.stock_code, s.stock_name, s.industry_name FROM dim_stock s WHERE s.industry_name LIKE '%{industry}%' AND s.is_active = 1"
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询{industry}行业的股票"
            return result

        if "净利润" in query and "增长" in query:
            years = 3
            growth = 20

            year_match = re.search(r"近(\d+)年", query)
            if year_match:
                years = int(year_match.group(1))

            growth_match = re.search(r"增长.*?(\d+)%", query)
            if growth_match:
                growth = int(growth_match.group(1))

            sql = f"""
                SELECT s.stock_code, s.stock_name, f.net_profit_yoy, f.report_date
                FROM dim_stock s
                JOIN fact_financial f ON s.stock_code = f.stock_code
                WHERE f.net_profit_yoy > {growth}
                  AND f.report_date >= DATE_SUB(CURDATE(), INTERVAL {years} YEAR)
                  AND s.is_active = 1
                ORDER BY f.net_profit_yoy DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询近{years}年净利润增长超过{growth}%的股票"
            return result

        if "市盈率" in query and "最低" in query:
            limit_match = re.search(r"前(\d+)", query)
            limit = limit_match.group(1) if limit_match else "10"
            sql = f"SELECT s.stock_code, s.stock_name, f.pe_ratio FROM dim_stock s JOIN fact_financial f ON s.stock_code = f.stock_code WHERE f.pe_ratio > 0 AND s.is_active = 1 ORDER BY f.pe_ratio ASC LIMIT {limit}"
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询市盈率最低的前{limit}只股票"
            return result

        if "市盈率" in query and "低于" in query:
            pe_match = re.search(r"低于(\d+)", query)
            if pe_match:
                pe = pe_match.group(1)
                sql = f"SELECT s.stock_code, s.stock_name, f.pe_ratio FROM dim_stock s JOIN fact_financial f ON s.stock_code = f.stock_code WHERE f.pe_ratio > 0 AND f.pe_ratio < {pe} AND s.is_active = 1"
                result["success"] = True
                result["sql"] = sql
                result["explanation"] = f"查询市盈率低于{pe}的股票"
                return result

        if "银行" in query:
            sql = "SELECT stock_code, stock_name, industry_name FROM dim_stock WHERE industry_name LIKE '%银行%' AND is_active = 1"
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = "查询银行行业的股票"
            return result

        ma_match = re.search(r"(\d+)日均线", query)
        if ma_match and ("大于" in query or "高于" in query or "上穿" in query or "超过" in query or "突破" in query):
            ma_period = ma_match.group(1)
            sql = f"""
                SELECT b.stock_code, s.stock_name, b.trade_date, b.close, b.ma{ma_period}, b.pre_close
                FROM fact_daily_bar b
                LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                WHERE b.close > b.ma{ma_period}
                  AND b.trade_date >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
                ORDER BY b.trade_date DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询收盘价大于{ma_period}日均线的股票"
            return result

        if "均线" in query and ("金叉" in query or "死叉" in query):
            sql = """
                SELECT b.stock_code, s.stock_name, b.trade_date, b.close, b.ma5, b.ma10, b.ma20,
                       CASE WHEN b.ma5 > b.ma10 THEN '金叉' ELSE '死叉' END as signal
                FROM fact_daily_bar b
                LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                WHERE b.trade_date >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
                ORDER BY b.trade_date DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = "查询均线金叉死叉信号"
            return result

        if "最近" in query and "交易日" in query:
            days_match = re.search(r"(\d+)个?交易日", query)
            days = days_match.group(1) if days_match else "5"
            sql = f"""
                SELECT b.stock_code, s.stock_name, b.trade_date, b.close, b.change_pct, b.volume
                FROM fact_daily_bar b
                LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                WHERE b.trade_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                ORDER BY b.trade_date DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = f"查询最近{days}个交易日的数据"
            return result

        if "成交量" in query and "放大" in query:
            sql = """
                SELECT b.stock_code, s.stock_name, b.trade_date, b.volume, b.amount, b.volume_ratio
                FROM fact_daily_bar b
                LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                WHERE b.volume_ratio > 1.5
                  AND b.trade_date >= DATE_SUB(CURDATE(), INTERVAL 5 DAY)
                ORDER BY b.volume_ratio DESC
            """
            result["success"] = True
            result["sql"] = sql
            result["explanation"] = "查询成交量放大的股票"
            return result

        if "新高" in query or "新低" in query:
            days = 100
            days_match = re.search(r"(\d+)日", query)
            if days_match:
                days = int(days_match.group(1))

            if "新高" in query:
                sql = f"""
                    SELECT b.stock_code, s.stock_name, b.trade_date, b.close,
                           (SELECT MAX(close) FROM fact_daily_bar WHERE stock_code = b.stock_code AND trade_date >= DATE_SUB(b.trade_date, INTERVAL {days} DAY) AND trade_date < b.trade_date) as max_close
                    FROM fact_daily_bar b
                    LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                    WHERE b.close = (
                        SELECT MAX(close) FROM fact_daily_bar
                        WHERE stock_code = b.stock_code
                          AND trade_date >= DATE_SUB(b.trade_date, INTERVAL {days} DAY)
                          AND trade_date <= b.trade_date
                    )
                    AND b.trade_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                    ORDER BY b.close DESC
                    LIMIT 100
                """
                result["success"] = True
                result["sql"] = sql
                result["explanation"] = f"查询{days}日新高的股票"
                return result

            if "新低" in query:
                sql = f"""
                    SELECT b.stock_code, s.stock_name, b.trade_date, b.close,
                           (SELECT MIN(close) FROM fact_daily_bar WHERE stock_code = b.stock_code AND trade_date >= DATE_SUB(b.trade_date, INTERVAL {days} DAY) AND trade_date < b.trade_date) as min_close
                    FROM fact_daily_bar b
                    LEFT JOIN dim_stock s ON b.stock_code = s.stock_code
                    WHERE b.close = (
                        SELECT MIN(close) FROM fact_daily_bar
                        WHERE stock_code = b.stock_code
                          AND trade_date >= DATE_SUB(b.trade_date, INTERVAL {days} DAY)
                          AND trade_date <= b.trade_date
                    )
                    AND b.trade_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                    ORDER BY b.close ASC
                    LIMIT 100
                """
                result["success"] = True
                result["sql"] = sql
                result["explanation"] = f"查询{days}日新低的股票"
                return result

        result["explanation"] = "抱歉，无法理解您的查询，请尝试用更具体的描述"
        return result


query_service = QueryService()
ai_query_service = AIQueryService()
