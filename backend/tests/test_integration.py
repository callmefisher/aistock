import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any


class TestDataFetchIntegration:
    """集成测试：数据获取功能"""

    @pytest.mark.asyncio
    async def test_fetch_status_returns_valid_structure(self):
        """测试获取数据状态返回有效结构"""
        from api.data_api import get_fetch_status

        with patch('api.data_api.create_async_engine') as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.fetchone.return_value = (1000, 50000, 500, datetime(2026, 4, 9), datetime(2026, 3, 31))
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.__aenter__.return_value = mock_conn

            result = await get_fetch_status()

            assert result['success'] is True
            assert 'data' in result
            assert result['data']['stock_count'] == 1000

    @pytest.mark.asyncio
    async def test_fetch_status_handles_error(self):
        """测试获取数据状态处理错误"""
        from api.data_api import get_fetch_status

        with patch('api.data_api.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Database connection error")

            result = await get_fetch_status()

            assert result['success'] is False
            assert 'message' in result or 'error' in result


class TestStockListIntegration:
    """集成测试：股票列表功能"""

    @pytest.mark.asyncio
    async def test_get_stock_list_from_akshare(self):
        """测试从AkShare获取股票列表"""
        from api.data_api import get_stock_list
        from fetcher.akshare_fetcher import StockFetcher

        mock_df = None

        with patch.object(StockFetcher, 'fetch_stock_list') as mock_fetch:
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.to_dict.return_value = [{'stock_code': '600000', 'stock_name': '测试股'}]
            mock_fetch.return_value = mock_df

            result = await get_stock_list()

            assert result.get('success') is True

    @pytest.mark.asyncio
    async def test_get_industry_list_from_akshare(self):
        """测试从AkShare获取行业列表"""
        from api.data_api import get_industry_list
        from fetcher.akshare_fetcher import StockFetcher

        with patch.object(StockFetcher, 'fetch_industry分类') as mock_fetch:
            mock_df = MagicMock()
            mock_df.empty = False
            mock_df.to_dict.return_value = [{'industry_code': 'BK', 'industry_name': '银行'}]
            mock_fetch.return_value = mock_df

            result = await get_industry_list()

            assert result.get('success') is True


class TestSQLQueryIntegration:
    """集成测试：SQL查询功能"""

    @pytest.mark.asyncio
    async def test_execute_valid_sql(self):
        """测试执行有效SQL"""
        from api.data_api import query_sql

        with patch('api.data_api.create_async_engine') as mock_engine:
            mock_conn = AsyncMock()
            mock_result = AsyncMock()
            mock_result.keys.return_value = ['id', 'value']
            mock_result.fetchall.return_value = [(1, 'test'), (2, 'test2')]
            mock_conn.execute.return_value = mock_result
            mock_engine.return_value.__aenter__.return_value = mock_conn

            result = await query_sql({"sql": "SELECT 1 as id, 'test' as value"})

            assert result['success'] is True
            assert result['row_count'] == 2
            assert 'data' in result

    @pytest.mark.asyncio
    async def test_execute_sql_with_error(self):
        """测试执行SQL出错"""
        from api.data_api import query_sql

        with patch('api.data_api.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Syntax error in SQL")

            result = await query_sql({"sql": "INVALID SQL"})

            assert result['success'] is False
            assert 'error' in result

    @pytest.mark.asyncio
    async def test_execute_empty_sql(self):
        """测试执行空SQL"""
        from api.data_api import query_sql

        result = await query_sql({"sql": ""})

        assert result['success'] is False


class TestAIQueryIntegration:
    """集成测试：AI查询功能"""

    @pytest.mark.asyncio
    async def test_ai_query_consume_industry(self):
        """测试AI查询消费行业"""
        from api.data_api import query_ai

        with patch('api.data_api.ai_query_service') as mock_service:
            mock_service.parse_query.return_value = {
                "success": True,
                "sql": "SELECT * FROM dim_stock WHERE industry LIKE '%消费%'",
                "explanation": "查询消费行业"
            }

            with patch('api.data_api.query_service') as mock_query_service:
                mock_query_service.execute_sql.return_value = {
                    "success": True,
                    "data": [],
                    "row_count": 0
                }

                result = await query_ai({"query": "查询消费行业的股票"})

                assert "sql" in result or "explanation" in result

    @pytest.mark.asyncio
    async def test_ai_query_unrecognized(self):
        """测试AI查询无法识别"""
        from api.data_api import query_ai

        with patch('api.data_api.ai_query_service') as mock_service:
            mock_service.parse_query.return_value = {
                "success": False,
                "explanation": "无法理解"
            }

            result = await query_ai({"query": "随机文本"})

            assert result['success'] is False


class TestStockDailyQueryIntegration:
    """集成测试：股票日线查询功能"""

    @pytest.mark.asyncio
    async def test_query_stock_daily_basic(self):
        """测试查询股票日线-基本"""
        from api.data_api import query_stock_daily

        with patch('api.data_api.query_service') as mock_service:
            mock_service.query_stock_daily.return_value = {
                "success": True,
                "data": [{"trade_date": "2026-04-09", "close": 10.0}],
                "columns": ["trade_date", "close"],
                "row_count": 1
            }

            result = await query_stock_daily({
                "start_date": "2026-04-01",
                "end_date": "2026-04-09"
            })

            assert result['success'] is True
            assert result['row_count'] == 1

    @pytest.mark.asyncio
    async def test_query_stock_daily_with_code(self):
        """测试查询股票日线-指定代码"""
        from api.data_api import query_stock_daily

        with patch('api.data_api.query_service') as mock_service:
            mock_service.query_stock_daily.return_value = {
                "success": True,
                "data": [],
                "row_count": 0
            }

            result = await query_stock_daily({
                "stock_code": "600000",
                "start_date": "2026-04-01",
                "end_date": "2026-04-09"
            })

            assert result['success'] is True


class TestStocksFilterIntegration:
    """集成测试：股票筛选功能"""

    @pytest.mark.asyncio
    async def test_query_stocks_filter_pe(self):
        """测试股票筛选-市盈率"""
        from api.data_api import query_stocks_filter

        with patch('api.data_api.query_service') as mock_service:
            mock_service.query_stocks.return_value = {
                "success": True,
                "data": [{"stock_code": "600000", "pe_ratio": 15.5}],
                "row_count": 1
            }

            result = await query_stocks_filter({
                "pe_min": 0,
                "pe_max": 30,
                "limit": 10
            })

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_query_stocks_filter_industry(self):
        """测试股票筛选-行业"""
        from api.data_api import query_stocks_filter

        with patch('api.data_api.query_service') as mock_service:
            mock_service.query_stocks.return_value = {
                "success": True,
                "data": [],
                "row_count": 0
            }

            result = await query_stocks_filter({
                "industry": "银行",
                "limit": 10
            })

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_query_stocks_filter_sort(self):
        """测试股票筛选-排序"""
        from api.data_api import query_stocks_filter

        with patch('api.data_api.query_service') as mock_service:
            mock_service.query_stocks.return_value = {
                "success": True,
                "data": [],
                "row_count": 0
            }

            result = await query_stocks_filter({
                "sort_by": "pe_ratio",
                "order": "asc",
                "limit": 5
            })

            assert result['success'] is True


class TestFetchDailyBarIntegration:
    """集成测试：获取日线数据功能"""

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_success(self):
        """测试获取日线数据-成功"""
        from api.data_api import fetch_daily_bar

        with patch('api.data_api.stock_fetcher') as mock_fetcher:
            mock_fetcher.fetch_daily_bar.return_value = MagicMock(empty=False)

            with patch('api.data_api.db_writer') as mock_writer:
                mock_writer.write_daily_bar.return_value = 5

                result = await fetch_daily_bar({
                    "data_type": "stock_daily",
                    "stock_code": "600000",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-09"
                })

                assert result.get('success') is True

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_missing_stock_code(self):
        """测试获取日线数据-缺少股票代码"""
        from api.data_api import fetch_daily_bar

        result = await fetch_daily_bar({
            "data_type": "stock_daily",
            "start_date": "2026-04-01",
            "end_date": "2026-04-09"
        })

        assert result.get('success') is False

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_missing_dates(self):
        """测试获取日线数据-缺少日期"""
        from api.data_api import fetch_daily_bar

        result = await fetch_daily_bar({
            "data_type": "stock_daily",
            "stock_code": "600000"
        })

        assert result.get('success') is False

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_no_data(self):
        """测试获取日线数据-无数据"""
        from api.data_api import fetch_daily_bar

        with patch('api.data_api.stock_fetcher') as mock_fetcher:
            mock_fetcher.fetch_daily_bar.return_value = MagicMock(empty=True)

            result = await fetch_daily_bar({
                "data_type": "stock_daily",
                "stock_code": "600000",
                "start_date": "2026-04-01",
                "end_date": "2026-04-09"
            })

            assert result.get('success') is False


class TestBulkFetchIntegration:
    """集成测试：批量获取数据功能"""

    @pytest.mark.asyncio
    async def test_fetch_bulk_daily_bar(self):
        """测试批量获取日线数据"""
        from api.data_api import fetch_bulk_daily_bar

        with patch('api.data_api.stock_fetcher') as mock_fetcher:
            mock_fetcher.fetch_stock_list.return_value = MagicMock(empty=False)
            mock_fetcher.fetch_stock_list.return_value.iterrows.return_value = iter([
                ('0', MagicMock(stock_code='600000', stock_name='test'))
            ])

            mock_fetcher.fetch_daily_bar.return_value = MagicMock(empty=False)

            with patch('api.data_api.db_writer') as mock_writer:
                mock_writer.write_daily_bar.return_value = 5

                result = await fetch_bulk_daily_bar({
                    "data_type": "stock_daily",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-09"
                })

                assert result.get('success') is True

    @pytest.mark.asyncio
    async def test_fetch_bulk_empty_stock_list(self):
        """测试批量获取-股票列表为空"""
        from api.data_api import fetch_bulk_daily_bar

        with patch('api.data_api.stock_fetcher') as mock_fetcher:
            mock_fetcher.fetch_stock_list.return_value = MagicMock(empty=True)

            result = await fetch_bulk_daily_bar({
                "data_type": "stock_daily"
            })

            assert result.get('success') is False


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    async def test_complete_query_flow(self):
        """测试完整查询流程"""
        from service.query_service import query_service

        result = await query_service.query_stock_daily(
            start_date="2026-01-01",
            end_date="2026-04-09"
        )

        assert 'success' in result

    @pytest.mark.asyncio
    async def test_ai_to_sql_flow(self):
        """测试AI转SQL流程"""
        from service.query_service import ai_query_service

        result = ai_query_service.parse_query("查询消费行业的股票")

        assert 'success' in result
        if result['success']:
            assert 'sql' in result

    @pytest.mark.asyncio
    async def test_ai_query_execution_flow(self):
        """测试AI查询执行流程"""
        from service.query_service import ai_query_service, query_service

        parsed = ai_query_service.parse_query("查询消费行业的股票")
        assert parsed['success'] is True

        if parsed.get('sql'):
            result = await query_service.execute_sql(parsed['sql'])
            assert 'success' in result

    @pytest.mark.asyncio
    async def test_stocks_filter_flow(self):
        """测试股票筛选流程"""
        from service.query_service import query_service

        result = await query_service.query_stocks(
            industry="银行",
            pe_max=50,
            limit=10
        )

        assert 'success' in result

    @pytest.mark.asyncio
    async def test_financial_query_flow(self):
        """测试财务数据查询流程"""
        from service.query_service import query_service

        result = await query_service.query_financial(
            start_date="2025-01-01",
            end_date="2026-04-09"
        )

        assert 'success' in result


class TestSchedulerIntegration:
    """集成测试：调度服务"""

    @pytest.mark.asyncio
    async def test_manual_update_stock_daily(self):
        """测试手动更新日线数据"""
        from service.scheduler_service import scheduler_service

        with patch('fetcher.akshare_fetcher.stock_fetcher') as mock_fetcher:
            mock_fetcher.fetch_stock_list.return_value = MagicMock(empty=False)
            mock_fetcher.fetch_stock_list.return_value.__getitem__.return_value = ['600000']
            mock_fetcher.fetch_stock_list.return_value.iterrows.return_value = iter([
                (0, MagicMock(stock_code='600000'))
            ])

            mock_fetcher.fetch_daily_bar.return_value = MagicMock(empty=False)

            with patch('service.db_writer.db_writer') as mock_writer:
                mock_writer.write_daily_bar.return_value = 5

                result = await scheduler_service.run_manual_update(
                    data_type="stock_daily",
                    start_date="2026-04-01",
                    end_date="2026-04-09"
                )

                assert 'success' in result

    @pytest.mark.asyncio
    async def test_manual_update_unknown_type(self):
        """测试手动更新-未知类型"""
        from service.scheduler_service import scheduler_service

        result = await scheduler_service.run_manual_update(data_type="unknown")

        assert result['success'] is False


class TestRetentionIntegration:
    """集成测试：数据保留服务"""

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self):
        """测试清理过期数据"""
        from service.retention_service import retention_service

        with patch.object(retention_service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.side_effect = [100, 50, 10]

            result = await retention_service.cleanup_old_data()

            assert result['success'] is True
            assert result['total_deleted'] == 160

    @pytest.mark.asyncio
    async def test_cleanup_single_table(self):
        """测试清理单个表"""
        from service.retention_service import retention_service

        with patch.object(retention_service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 100

            result = await retention_service.cleanup_old_data('fact_daily_bar')

            assert result['success'] is True
            assert result['total_deleted'] == 100

    @pytest.mark.asyncio
    async def test_schedule_cleanup(self):
        """测试调度清理"""
        from service.retention_service import retention_service

        result = await retention_service.schedule_cleanup("weekly")

        assert result['success'] is True
        assert result['interval_hours'] == 168

    @pytest.mark.asyncio
    async def test_retention_config(self):
        """测试保留配置"""
        from service.retention_service import retention_service

        result = await retention_service.get_retention_config()

        assert 'rules' in result
        assert result['rules']['fact_daily_bar'] == 730


class TestFetcherIntegration:
    """集成测试：数据获取器"""

    @pytest.mark.asyncio
    async def test_fetch_spot(self):
        """测试获取实时行情"""
        from fetcher.akshare_fetcher import StockFetcher

        with patch('fetcher.akshare_fetcher.stock_fetcher') as mock:
            result = mock.fetch_spot()

    def test_normalize_daily_bar(self):
        """测试标准化日线数据"""
        from fetcher.akshare_fetcher import StockFetcher
        import pandas as pd
        from datetime import datetime

        fetcher = StockFetcher()
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(10)]
        df = pd.DataFrame({
            '日期': dates,
            '开盘': [10.0] * 10,
            '收盘': [11.0] * 10,
            '最高': [12.0] * 10,
            '最低': [9.0] * 10,
            '成交量': [1000000] * 10,
            '成交额': [11000000] * 10,
            '振幅': [5.0] * 10,
            '涨跌幅': [1.0] * 10,
            '涨跌额': [0.5] * 10,
            '换手率': [2.0] * 10
        })

        result = fetcher._normalize_daily_bar(df, '600000')

        assert 'stock_code' in result.columns
        assert 'ma5' in result.columns
        assert 'ma10' in result.columns

    def test_calculate_ma(self):
        """测试均线计算"""
        from fetcher.akshare_fetcher import StockFetcher
        import pandas as pd

        fetcher = StockFetcher()
        df = pd.DataFrame({
            'close': [10.0 + i for i in range(20)]
        })

        result = fetcher.calculate_ma(df, periods=[5, 10, 20])

        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns


class TestDatabaseWriterIntegration:
    """集成测试：数据库写入"""

    @pytest.mark.asyncio
    async def test_write_daily_bar(self):
        """测试写入日线数据"""
        from service.db_writer import DatabaseWriter
        import pandas as pd
        from datetime import datetime

        writer = DatabaseWriter()

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'trade_date': [datetime.now()],
            'open': [10.0],
            'high': [12.0],
            'low': [9.0],
            'close': [11.0],
            'volume': [1000000],
            'amount': [11000000],
            'turnover_rate': [2.0],
            'amplitude': [5.0],
            'change_pct': [1.0],
            'change_amount': [0.5],
            'pre_close': [10.5],
            'ma5': [10.5],
            'ma10': [10.2],
            'ma20': [10.0],
            'ma30': [9.8],
            'ma60': [9.5],
            'ma120': [9.0],
            'ma250': [8.5],
            'volume_ratio': [1.2]
        })

        with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
            result = await writer.write_daily_bar(df)
            assert result >= 0

    @pytest.mark.asyncio
    async def test_write_empty_dataframe(self):
        """测试写入空数据框"""
        from service.db_writer import DatabaseWriter
        import pandas as pd

        writer = DatabaseWriter()
        df = pd.DataFrame()

        with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
            result = await writer.write_daily_bar(df)
            assert result == 0
