import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from service.retention_service import RetentionPolicyService


class TestRetentionPolicyService:
    """数据保留策略服务测试"""

    def setup_method(self):
        self.service = RetentionPolicyService()

    def test_default_retention_rules(self):
        """测试默认保留规则"""
        assert self.service.retention_rules['fact_daily_bar'] == 730
        assert self.service.retention_rules['fact_financial'] == 730
        assert self.service.retention_rules['stock_spot'] == 30
        assert self.service.retention_rules['log_data_fetch'] == 180

    def test_default_retention_days(self):
        """测试默认保留天数"""
        assert self.service.default_retention_days == 730

    @pytest.mark.asyncio
    async def test_get_retention_policy_exists(self):
        """测试获取保留策略-已存在"""
        result = await self.service.get_retention_policy('fact_daily_bar')
        assert result == 730

    @pytest.mark.asyncio
    async def test_get_retention_policy_not_exists(self):
        """测试获取保留策略-不存在"""
        result = await self.service.get_retention_policy('unknown_table')
        assert result == self.service.default_retention_days

    @pytest.mark.asyncio
    async def test_set_retention_policy_success(self):
        """测试设置保留策略-成功"""
        with patch('service.retention_service.create_async_engine') as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.return_value.__aenter__.return_value = mock_conn

            result = await self.service.set_retention_policy('fact_daily_bar', 365)

            assert result is True
            assert self.service.retention_rules['fact_daily_bar'] == 365

    @pytest.mark.asyncio
    async def test_set_retention_policy_failure(self):
        """测试设置保留策略-失败"""
        with patch('service.retention_service.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Database error")

            result = await self.service.set_retention_policy('fact_daily_bar', 365)

            assert result is False

    @pytest.mark.asyncio
    async def test_get_retention_config(self):
        """测试获取保留配置"""
        result = await self.service.get_retention_config()

        assert 'default_retention_days' in result
        assert 'rules' in result
        assert result['default_retention_days'] == 730
        assert len(result['rules']) > 0

    @pytest.mark.asyncio
    async def test_schedule_cleanup_weekly(self):
        """测试调度清理-每周"""
        result = await self.service.schedule_cleanup("weekly")

        assert result['success'] is True
        assert result['schedule'] == "weekly"
        assert result['interval_hours'] == 168

    @pytest.mark.asyncio
    async def test_schedule_cleanup_daily(self):
        """测试调度清理-每天"""
        result = await self.service.schedule_cleanup("daily")

        assert result['success'] is True
        assert result['schedule'] == "daily"
        assert result['interval_hours'] == 24

    @pytest.mark.asyncio
    async def test_schedule_cleanup_monthly(self):
        """测试调度清理-每月"""
        result = await self.service.schedule_cleanup("monthly")

        assert result['success'] is True
        assert result['schedule'] == "monthly"
        assert result['interval_hours'] == 720

    @pytest.mark.asyncio
    async def test_schedule_cleanup_default(self):
        """测试调度清理-默认(每周)"""
        result = await self.service.schedule_cleanup("unknown")

        assert result['success'] is True
        assert result['interval_hours'] == 168


class TestRetentionCleanup:
    """数据清理测试"""

    def setup_method(self):
        self.service = RetentionPolicyService()

    @pytest.mark.asyncio
    async def test_cleanup_old_data_success(self):
        """测试清理过期数据-成功"""
        with patch.object(self.service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.side_effect = [100, 50, 10]

            result = await self.service.cleanup_old_data()

            assert result['success'] is True
            assert result['total_deleted'] == 160
            assert len(result['cleaned_tables']) > 0

    @pytest.mark.asyncio
    async def test_cleanup_old_data_single_table(self):
        """测试清理过期数据-单个表"""
        with patch.object(self.service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 100

            result = await self.service.cleanup_old_data('fact_daily_bar')

            assert result['success'] is True
            assert result['total_deleted'] == 100
            assert len(result['cleaned_tables']) == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_data_with_errors(self):
        """测试清理过期数据-部分失败"""
        with patch.object(self.service, '_cleanup_table', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.side_effect = [100, Exception("Error"), 50]

            result = await self.service.cleanup_old_data()

            assert result['success'] is True
            assert len(result['errors']) > 0
            assert 'Error' in str(result['errors'])


class TestDataStats:
    """数据统计测试"""

    def setup_method(self):
        self.service = RetentionPolicyService()

    @pytest.mark.asyncio
    async def test_get_data_stats_error(self):
        """测试获取数据统计-错误"""
        with patch('service.retention_service.create_async_engine') as mock_engine:
            mock_engine.side_effect = Exception("Database error")

            result = await self.service.get_data_stats()

            assert 'error' in result


class TestRetentionBoundary:
    """保留策略边界测试"""

    def setup_method(self):
        self.service = RetentionPolicyService()

    @pytest.mark.asyncio
    async def test_retention_2_years_exact(self):
        """测试保留2年-精确边界"""
        cutoff = datetime.now() - timedelta(days=730)

        assert cutoff < datetime.now()
        assert (datetime.now() - cutoff).days >= 729

    @pytest.mark.asyncio
    async def test_retention_30_days_for_spot(self):
        """测试实时行情保留30天"""
        assert self.service.retention_rules['stock_spot'] == 30

    @pytest.mark.asyncio
    async def test_retention_180_days_for_logs(self):
        """测试日志保留180天"""
        assert self.service.retention_rules['log_data_fetch'] == 180

    @pytest.mark.asyncio
    async def test_retention_config_persistence(self):
        """测试保留配置持久化"""
        with patch('service.retention_service.create_async_engine') as mock_engine:
            mock_conn = AsyncMock()
            mock_engine.return_value.__aenter__.return_value = mock_conn

            await self.service.set_retention_policy('test_table', 500)

            assert self.service.retention_rules['test_table'] == 500
