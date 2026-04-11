import pytest
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


class TestQueryServiceUnit:
    """单元测试：查询服务"""

    @pytest.mark.asyncio
    async def test_query_stock_daily_success(self):
        """测试查询股票日线-成功"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['trade_date', 'stock_code', 'close']
        mock_result.fetchall = AsyncMock(return_value=[
            (datetime(2026, 4, 9), '600000', 10.0),
            (datetime(2026, 4, 8), '600000', 9.5)
        ])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.query_stock_daily(
                stock_code='600000',
                start_date='2026-04-01',
                end_date='2026-04-09'
            )

            assert result['success'] is True
            assert result['row_count'] == 2

    @pytest.mark.asyncio
    async def test_query_stock_daily_no_params(self):
        """测试查询股票日线-无参数"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['trade_date', 'stock_code', 'close']
        mock_result.fetchall = AsyncMock(return_value=[])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.query_stock_daily()

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_query_stocks_filter_success(self):
        """测试股票筛选-成功"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['stock_code', 'stock_name', 'pe_ratio']
        mock_result.fetchall = AsyncMock(return_value=[
            ('600000', '浦发银行', 15.5)
        ])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.query_stocks(
                industry='银行',
                pe_max=30,
                limit=10
            )

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_query_stocks_filter_by_exchange(self):
        """测试股票筛选-按交易所"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['stock_code']
        mock_result.fetchall = AsyncMock(return_value=[('600000',), ('600001',)])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.query_stocks(exchange='SH', limit=10)

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_query_financial_success(self):
        """测试财务查询-成功"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['stock_code', 'report_date', 'net_profit']
        mock_result.fetchall = AsyncMock(return_value=[
            ('600000', datetime(2025, 12, 31), 1000000)
        ])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.query_financial(
                start_date='2025-01-01',
                end_date='2025-12-31'
            )

            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_execute_sql_success(self):
        """测试执行SQL-成功"""
        from service.query_service import QueryService

        service = QueryService()

        mock_result = MagicMock()
        mock_result.keys.return_value = ['id', 'value']
        mock_result.fetchall = AsyncMock(return_value=[(1, 'test')])

        mock_execute = AsyncMock(return_value=mock_result)

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.return_value.connect.return_value.__aenter__.return_value.execute = mock_execute

            result = await service.execute_sql("SELECT 1 as id, 'test' as value")

            assert result['success'] is True
            assert result['row_count'] == 1

    @pytest.mark.asyncio
    async def test_execute_sql_error(self):
        """测试执行SQL-错误"""
        from service.query_service import QueryService

        service = QueryService()

        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("SQL syntax error")

            result = await service.execute_sql("INVALID SQL")

            assert result['success'] is False
            assert 'error' in result


class TestAIQueryServiceUnit:
    """单元测试：AI查询服务"""

    def test_parse_query_consume_growth_pe(self):
        """测试解析查询-消费+增长+PE"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("查询近三年净利润增长均超过20%且市盈率低于30倍的消费股")

        assert result['success'] is True
        assert 'sql' in result
        assert '消费' in result['sql']

    def test_parse_query_date_range(self):
        """测试解析查询-日期范围"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("2026-01-01到2026-04-09的行情数据")

        assert result['success'] is True
        assert '2026-01-01' in result['sql']

    def test_parse_query_lowest_pe(self):
        """测试解析查询-最低PE"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("市盈率最低的前10只股票")

        assert result['success'] is True
        assert 'pe_ratio ASC' in result['sql']
        assert 'LIMIT 10' in result['sql']

    def test_parse_query_bank_industry(self):
        """测试解析查询-银行行业"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("查询银行行业的股票")

        assert result['success'] is True
        assert '银行' in result['sql']

    def test_parse_query_high_growth(self):
        """测试解析查询-高增长"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("净利润增长超过50%的股票")

        assert result['success'] is True
        assert '50' in result['sql']

    def test_parse_query_empty(self):
        """测试解析查询-空查询"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("")

        assert result['success'] is False

    def test_parse_query_random(self):
        """测试解析查询-随机文本"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("今天天气怎么样")

        assert result['success'] is False

    def test_parse_query_injection_attempt(self):
        """测试解析查询-SQL注入尝试"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        result = service.parse_query("'; DROP TABLE users; --")

        assert result['success'] is False


class TestStockFetcherUnit:
    """单元测试：股票数据获取器"""

    def test_normalize_daily_bar_basic(self):
        """测试标准化日线数据-基本"""
        from fetcher.akshare_fetcher import StockFetcher

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
        assert 'trade_date' in result.columns
        assert result.iloc[0]['stock_code'] == '600000'

    def test_normalize_daily_bar_with_ma(self):
        """测试标准化日线数据-均线"""
        from fetcher.akshare_fetcher import StockFetcher

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

        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns
        assert 'ma30' in result.columns
        assert 'ma60' in result.columns
        assert 'ma120' in result.columns
        assert 'ma250' in result.columns

    def test_normalize_daily_bar_empty(self):
        """测试标准化日线数据-空"""
        from fetcher.akshare_fetcher import StockFetcher

        fetcher = StockFetcher()
        df = pd.DataFrame()

        result = fetcher._normalize_daily_bar(df, '600000')

        assert result.empty

    def test_normalize_daily_bar_single_row(self):
        """测试标准化日线数据-单行"""
        from fetcher.akshare_fetcher import StockFetcher

        fetcher = StockFetcher()
        df = pd.DataFrame({
            '日期': ['2026-04-09'],
            '开盘': [10.0],
            '收盘': [11.0],
            '最高': [12.0],
            '最低': [9.0],
            '成交量': [1000000],
            '成交额': [11000000],
            '振幅': [5.0],
            '涨跌幅': [1.0],
            '涨跌额': [0.5],
            '换手率': [2.0]
        })

        result = fetcher._normalize_daily_bar(df, '600000')

        assert len(result) == 1
        assert pd.isna(result.iloc[0]['ma5'])

    def test_calculate_ma_success(self):
        """测试均线计算-成功"""
        from fetcher.akshare_fetcher import StockFetcher

        fetcher = StockFetcher()
        df = pd.DataFrame({
            'close': [10.0 + i for i in range(20)]
        })

        result = fetcher.calculate_ma(df, periods=[5, 10, 20])

        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns
        assert not pd.isna(result['ma5'].iloc[-1])

    def test_calculate_ma_insufficient_data(self):
        """测试均线计算-数据不足"""
        from fetcher.akshare_fetcher import StockFetcher

        fetcher = StockFetcher()
        df = pd.DataFrame({'close': [10.0, 11.0, 12.0]})

        result = fetcher.calculate_ma(df, periods=[5, 10])

        assert pd.isna(result['ma5'].iloc[-1])
        assert pd.isna(result['ma10'].iloc[-1])

    def test_calculate_ma_empty(self):
        """测试均线计算-空数据"""
        from fetcher.akshare_fetcher import StockFetcher

        fetcher = StockFetcher()
        df = pd.DataFrame({'close': []})

        result = fetcher.calculate_ma(df, periods=[5])

        assert result.empty


class TestSchedulerServiceUnit:
    """单元测试：调度服务"""

    def test_determine_stocks_no_history(self):
        """测试确定股票需更新-无历史"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        stock_list = pd.DataFrame({
            'stock_code': ['600000', '000001'],
            'stock_name': ['浦发银行', '平安银行']
        })
        now = datetime(2026, 4, 9)

        with patch.object(service, '_get_last_update_date', return_value=None):
            result = service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 2

    def test_determine_stocks_current_year_recent(self):
        """测试确定股票需更新-今年近期"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9, 15, 0)

        yesterday = datetime(2026, 4, 8)
        with patch.object(service, '_get_last_update_date', return_value=yesterday):
            result = service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_last_year_old(self):
        """测试确定股票需更新-去年旧数据"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9)

        old_date = datetime(2025, 12, 25)
        with patch.object(service, '_get_last_update_date', return_value=old_date):
            result = service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_empty_list(self):
        """测试确定股票需更新-空列表"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        stock_list = pd.DataFrame(columns=['stock_code', 'stock_name'])
        now = datetime(2026, 4, 9)

        result = service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 0

    def test_should_update_full_history_no_history(self):
        """测试是否更新全量历史-无历史"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()

        with patch.object(service, '_get_last_update_date', return_value=None):
            result = service._should_update_full_history('600000', datetime.now())

        assert result is True

    def test_should_update_full_history_recent(self):
        """测试是否更新全量历史-近期"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()

        recent = datetime.now() - timedelta(days=30)
        with patch.object(service, '_get_last_update_date', return_value=recent):
            result = service._should_update_full_history('600000', datetime.now())

        assert result is False

    def test_get_status(self):
        """测试获取状态"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        result = service.get_status()

        assert 'running' in result
        assert result['running'] is False


class TestRetentionServiceUnit:
    """单元测试：数据保留服务"""

    def test_default_retention_rules(self):
        """测试默认保留规则"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()

        assert service.retention_rules['fact_daily_bar'] == 730
        assert service.retention_rules['fact_financial'] == 730
        assert service.retention_rules['stock_spot'] == 30

    @pytest.mark.asyncio
    async def test_get_retention_policy_exists(self):
        """测试获取保留策略-存在"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        result = await service.get_retention_policy('fact_daily_bar')

        assert result == 730

    @pytest.mark.asyncio
    async def test_get_retention_policy_not_exists(self):
        """测试获取保留策略-不存在"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        result = await service.get_retention_policy('unknown')

        assert result == service.default_retention_days

    @pytest.mark.asyncio
    async def test_schedule_cleanup_weekly(self):
        """测试调度清理-每周"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        result = await service.schedule_cleanup("weekly")

        assert result['success'] is True
        assert result['interval_hours'] == 168

    @pytest.mark.asyncio
    async def test_schedule_cleanup_daily(self):
        """测试调度清理-每天"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        result = await service.schedule_cleanup("daily")

        assert result['success'] is True
        assert result['interval_hours'] == 24

    @pytest.mark.asyncio
    async def test_get_retention_config(self):
        """测试获取保留配置"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        result = await service.get_retention_config()

        assert 'rules' in result
        assert 'default_retention_days' in result

    @pytest.mark.asyncio
    async def test_cleanup_old_data_success(self):
        """测试清理过期数据-成功"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()

        with patch.object(service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.side_effect = [100, 50, 10]

            result = await service.cleanup_old_data()

            assert result['success'] is True
            assert result['total_deleted'] == 160

    @pytest.mark.asyncio
    async def test_cleanup_single_table(self):
        """测试清理单个表"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()

        with patch.object(service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 100

            result = await service.cleanup_old_data('fact_daily_bar')

            assert result['success'] is True
            assert result['total_deleted'] == 100


class TestEndToEndScenarios:
    """端到端场景测试"""

    def test_complete_query_flow(self):
        """测试完整查询流程"""
        from service.query_service import AIQueryService

        ai_service = AIQueryService()

        parsed = ai_service.parse_query("查询消费行业的股票")
        assert parsed['success'] is True
        assert 'sql' in parsed

        parsed = ai_service.parse_query("净利润增长超过30%")
        assert parsed['success'] is True

        parsed = ai_service.parse_query("市盈率最低的前10只股票")
        assert parsed['success'] is True

    def test_multiple_ai_queries(self):
        """测试多个AI查询"""
        from service.query_service import AIQueryService

        service = AIQueryService()
        queries = [
            "查询消费行业的股票",
            "净利润增长超过50%的股票",
            "市盈率低于20的股票",
            "查询银行行业的股票"
        ]

        for query in queries:
            result = service.parse_query(query)
            assert 'success' in result

    def test_scheduler_update_decisions(self):
        """测试调度更新决策"""
        from service.scheduler_service import SchedulerService

        service = SchedulerService()
        now = datetime(2026, 4, 9)

        with patch.object(service, '_get_last_update_date', return_value=datetime(2026, 4, 8)):
            result = service._should_update_full_history('600000', now)
            assert result is False

        with patch.object(service, '_get_last_update_date', return_value=datetime(2025, 1, 1)):
            result = service._should_update_full_history('600000', now)
            assert result is True

    def test_retention_boundary_2_years(self):
        """测试保留边界2年"""
        from service.retention_service import RetentionPolicyService

        service = RetentionPolicyService()
        cutoff = datetime.now() - timedelta(days=730)

        assert cutoff < datetime.now()
        assert (datetime.now() - cutoff).days >= 729
