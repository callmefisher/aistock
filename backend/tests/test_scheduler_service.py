import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pandas as pd
from service.scheduler_service import SchedulerService


class TestSchedulerService:
    """调度服务测试"""

    def setup_method(self):
        self.service = SchedulerService()

    def test_service_initial_state(self):
        """测试服务初始状态"""
        assert self.service.running is False
        assert len(self.service.tasks) == 0
        assert len(self.service.last_run) == 0

    def test_determine_stocks_to_update_no_history(self):
        """测试股票需要更新-无历史记录"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000', '000001'],
            'stock_name': ['浦发银行', '平安银行']
        })
        now = datetime(2026, 4, 9)

        with patch.object(self.service, '_get_last_update_date', return_value=None):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 2
        assert '600000' in result
        assert '000001' in result

    def test_determine_stocks_to_update_current_year_recent(self):
        """测试股票需要更新-今年数据已是今天"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9, 15, 0)

        yesterday = datetime(2026, 4, 8)
        with patch.object(self.service, '_get_last_update_date', return_value=yesterday):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_to_update_current_year_old(self):
        """测试股票需要更新-今年数据超过1天"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9)

        two_days_ago = datetime(2026, 4, 7)
        with patch.object(self.service, '_get_last_update_date', return_value=two_days_ago):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1
        assert '600000' in result

    def test_determine_stocks_to_update_last_year_boundary(self):
        """测试股票需要更新-去年数据边界"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 1, 6)

        dec_31 = datetime(2025, 12, 31)
        with patch.object(self.service, '_get_last_update_date', return_value=dec_31):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_to_update_last_year_old(self):
        """测试股票需要更新-去年数据超过5天"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9)

        ten_days_ago = datetime(2025, 12, 25)
        with patch.object(self.service, '_get_last_update_date', return_value=ten_days_ago):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1
        assert '600000' in result

    def test_determine_stocks_to_update_multi_year_old(self):
        """测试股票需要更新-超过1年的数据"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9)

        old_date = datetime(2024, 1, 1)
        with patch.object(self.service, '_get_last_update_date', return_value=old_date):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1
        assert '600000' in result

    def test_determine_stocks_to_update_empty_list(self):
        """测试股票需要更新-空列表"""
        stock_list = pd.DataFrame(columns=['stock_code', 'stock_name'])
        now = datetime(2026, 4, 9)

        result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 0

    def test_should_update_full_history_no_history(self):
        """测试是否应更新全量历史-无历史记录"""
        with patch.object(self.service, '_get_last_update_date', return_value=None):
            result = self.service._should_update_full_history('600000', datetime.now())

        assert result is True

    def test_should_update_full_history_old_history(self):
        """测试是否应更新全量历史-历史数据超过1年"""
        old_date = datetime.now() - timedelta(days=400)
        with patch.object(self.service, '_get_last_update_date', return_value=old_date):
            result = self.service._should_update_full_history('600000', datetime.now())

        assert result is True

    def test_should_update_full_history_recent_history(self):
        """测试是否应更新全量历史-近期数据"""
        recent_date = datetime.now() - timedelta(days=30)
        with patch.object(self.service, '_get_last_update_date', return_value=recent_date):
            result = self.service._should_update_full_history('600000', datetime.now())

        assert result is False

    def test_get_status_initial(self):
        """测试获取服务状态-初始状态"""
        result = self.service.get_status()

        assert result['running'] is False
        assert result['active_tasks'] == 0
        assert len(result['last_run']) == 0

    @pytest.mark.asyncio
    async def test_start_service(self):
        """测试启动服务"""
        await self.service.start()

        assert self.service.running is True

        await self.service.stop()

    @pytest.mark.asyncio
    async def test_stop_service(self):
        """测试停止服务"""
        await self.service.start()
        await self.service.stop()

        assert self.service.running is False


class TestSchedulerManualUpdate:
    """调度服务手动更新测试"""

    def setup_method(self):
        self.service = SchedulerService()

    @pytest.mark.asyncio
    async def test_run_manual_update_stock_daily_success(self):
        """测试手动更新日线数据-成功"""
        mock_df = pd.DataFrame({
            'stock_code': ['600000'] * 5,
            'trade_date': [datetime.now()] * 5,
            'close': [10.0] * 5
        })

        with patch('fetcher.akshare_fetcher.stock_fetcher.fetch_stock_list') as mock_list, \
             patch('fetcher.akshare_fetcher.stock_fetcher.fetch_daily_bar') as mock_bar, \
             patch('service.db_writer.db_writer.write_daily_bar', new_callable=AsyncMock) as mock_write:

            mock_list.return_value = pd.DataFrame({'stock_code': ['600000'], 'stock_name': ['test']})
            mock_bar.return_value = mock_df
            mock_write.return_value = 5

            result = await self.service.run_manual_update(
                data_type="stock_daily",
                start_date="2026-01-01",
                end_date="2026-04-09"
            )

        assert result['success'] is True
        assert result['data_type'] == "stock_daily"

    @pytest.mark.asyncio
    async def test_run_manual_update_stock_daily_empty_data(self):
        """测试手动更新日线数据-无数据"""
        with patch('fetcher.akshare_fetcher.stock_fetcher.fetch_stock_list') as mock_list, \
             patch('fetcher.akshare_fetcher.stock_fetcher.fetch_daily_bar') as mock_bar:

            mock_list.return_value = pd.DataFrame({'stock_code': ['600000'], 'stock_name': ['test']})
            mock_bar.return_value = pd.DataFrame()

            result = await self.service.run_manual_update(data_type="stock_daily")

        assert result['success'] is True
        assert result['records_updated'] == 0

    @pytest.mark.asyncio
    async def test_run_manual_update_stock_spot_success(self):
        """测试手动更新实时行情-成功"""
        mock_df = pd.DataFrame({
            '代码': ['600000', '000001'],
            '名称': ['浦发银行', '平安银行'],
            '最新价': [10.0, 20.0]
        })

        with patch('fetcher.akshare_fetcher.stock_fetcher.fetch_spot') as mock_spot:
            mock_spot.return_value = mock_df

            result = await self.service.run_manual_update(data_type="stock_spot")

        assert result['success'] is True
        assert result['records_updated'] == 2

    @pytest.mark.asyncio
    async def test_run_manual_update_unknown_type(self):
        """测试手动更新-未知类型"""
        result = await self.service.run_manual_update(data_type="unknown_type")

        assert result['success'] is False
        assert len(result['errors']) > 0

    @pytest.mark.asyncio
    async def test_run_manual_update_stock_list_failed(self):
        """测试手动更新-获取股票列表失败"""
        with patch('fetcher.akshare_fetcher.stock_fetcher.fetch_stock_list') as mock_list:
            mock_list.return_value = pd.DataFrame()

            result = await self.service.run_manual_update(data_type="stock_daily")

        assert result['success'] is False
        assert len(result['errors']) > 0

    @pytest.mark.asyncio
    async def test_run_manual_update_with_specific_stock(self):
        """测试手动更新-指定股票代码"""
        mock_df = pd.DataFrame({
            'stock_code': ['600000'] * 3,
            'trade_date': [datetime.now()] * 3,
            'close': [10.0, 11.0, 12.0]
        })

        with patch('fetcher.akshare_fetcher.stock_fetcher.fetch_daily_bar') as mock_bar, \
             patch('service.db_writer.db_writer.write_daily_bar', new_callable=AsyncMock) as mock_write:

            mock_bar.return_value = mock_df
            mock_write.return_value = 3

            result = await self.service.run_manual_update(
                data_type="stock_daily",
                stock_code="600000",
                start_date="2026-04-01",
                end_date="2026-04-09"
            )

        assert result['success'] is True
        assert result['stocks_updated'] == 1


class TestSchedulerUpdateLogic:
    """调度服务更新逻辑测试"""

    def setup_method(self):
        self.service = SchedulerService()

    def test_determine_stocks_multiple_stocks_mixed_status(self):
        """测试多只股票混合状态"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000', '000001', '600001'],
            'stock_name': ['浦发银行', '平安银行', '邯郸钢铁']
        })
        now = datetime(2026, 4, 9)

        def mock_get_date(stock_code):
            if stock_code == '600000':
                return datetime(2026, 4, 7)
            elif stock_code == '000001':
                return datetime(2025, 12, 20)
            else:
                return None

        with patch.object(self.service, '_get_last_update_date', side_effect=mock_get_date):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert '600000' in result
        assert '000001' in result
        assert '600001' in result

    def test_determine_stocks_boundary_5_days(self):
        """测试边界-恰好5天"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9, 12, 0)

        exactly_5_days_ago = datetime(2026, 4, 4, 12, 0)
        with patch.object(self.service, '_get_last_update_date', return_value=exactly_5_days_ago):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_boundary_1_day(self):
        """测试边界-恰好1天"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 4, 9, 15, 0)

        exactly_1_day_ago = datetime(2026, 4, 8, 15, 0)
        with patch.object(self.service, '_get_last_update_date', return_value=exactly_1_day_ago):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_leap_year(self):
        """测试闰年边界"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2028, 3, 1)

        last_year_date = datetime(2027, 2, 28)
        with patch.object(self.service, '_get_last_update_date', return_value=last_year_date):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1

    def test_determine_stocks_year_end_to_new_year(self):
        """测试跨年边界"""
        stock_list = pd.DataFrame({
            'stock_code': ['600000'],
            'stock_name': ['浦发银行']
        })
        now = datetime(2026, 1, 5)

        year_end_date = datetime(2025, 12, 28)
        with patch.object(self.service, '_get_last_update_date', return_value=year_end_date):
            result = self.service._determine_stocks_to_update(stock_list, now)

        assert len(result) == 1
