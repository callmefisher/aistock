import pytest
import pandas as pd
from datetime import datetime, timedelta
from fetcher.akshare_fetcher import StockFetcher


class TestDataNormalizer:
    """数据标准化测试"""

    def setup_method(self):
        self.fetcher = StockFetcher()

    def test_normalize_daily_bar_success(self):
        """测试日线数据标准化成功"""
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

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert 'stock_code' in result.columns
        assert 'trade_date' in result.columns
        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns
        assert 'ma30' in result.columns
        assert 'ma60' in result.columns
        assert 'ma120' in result.columns
        assert 'ma250' in result.columns
        assert 'volume_ratio' in result.columns
        assert result.iloc[0]['stock_code'] == '600000'

    def test_normalize_daily_bar_empty(self):
        """测试日线数据标准化空数据"""
        df = pd.DataFrame()

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert result.empty

    def test_normalize_daily_bar_missing_columns(self):
        """测试日线数据标准化缺少列"""
        df = pd.DataFrame({
            '日期': ['2026-04-09'],
            '收盘': [11.0]
        })

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert 'stock_code' in result.columns
        assert 'ma5' in result.columns

    def test_normalize_daily_bar_single_row(self):
        """测试日线数据标准化单行数据"""
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

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert len(result) == 1
        assert pd.isna(result.iloc[0]['ma5'])

    def test_normalize_daily_bar_null_values(self):
        """测试日线数据标准化包含空值"""
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(5)]
        df = pd.DataFrame({
            '日期': dates,
            '开盘': [10.0, None, 12.0, 11.0, 13.0],
            '收盘': [11.0, 12.0, None, 14.0, 15.0],
            '最高': [12.0, 13.0, 14.0, None, 16.0],
            '最低': [9.0, 10.0, 11.0, 12.0, None],
            '成交量': [1000000, 1200000, 1100000, 1300000, 1400000],
            '成交额': [11000000, 13000000, 12000000, 14000000, 15000000],
            '振幅': [5.0, 4.0, 6.0, 3.0, 5.0],
            '涨跌幅': [1.0, 0.5, -0.5, 1.0, 0.5],
            '涨跌额': [0.5, 0.3, -0.3, 0.5, 0.3],
            '换手率': [2.0, 2.5, 1.5, 3.0, 2.0]
        })

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert not result.empty

    def test_normalize_daily_bar_negative_values(self):
        """测试日线数据标准化负值"""
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(5)]
        df = pd.DataFrame({
            '日期': dates,
            '开盘': [10.0, 9.0, 8.0, 7.0, 6.0],
            '收盘': [9.0, 8.0, 7.0, 6.0, 5.0],
            '最高': [12.0, 11.0, 10.0, 9.0, 8.0],
            '最低': [9.0, 8.0, 7.0, 6.0, 5.0],
            '成交量': [1000000, 1100000, 1200000, 1300000, 1400000],
            '成交额': [11000000, 12000000, 13000000, 14000000, 15000000],
            '振幅': [5.0, 4.0, 6.0, 3.0, 5.0],
            '涨跌幅': [-1.0, -1.0, -1.0, -1.0, -1.0],
            '涨跌额': [-0.5, -0.5, -0.5, -0.5, -0.5],
            '换手率': [2.0, 2.5, 1.5, 3.0, 2.0]
        })

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert (result['change_pct'] < 0).all()

    def test_normalize_daily_bar_zero_volume(self):
        """测试日线数据标准化零成交量"""
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(5)]
        df = pd.DataFrame({
            '日期': dates,
            '开盘': [10.0] * 5,
            '收盘': [11.0] * 5,
            '最高': [12.0] * 5,
            '最低': [9.0] * 5,
            '成交量': [0] * 5,
            '成交额': [0] * 5,
            '振幅': [0] * 5,
            '涨跌幅': [0] * 5,
            '涨跌额': [0] * 5,
            '换手率': [0] * 5
        })

        result = self.fetcher._normalize_daily_bar(df, '600000')

        assert not result.empty

    def test_calculate_ma_success(self):
        """测试均线计算成功"""
        df = pd.DataFrame({
            'close': [10.0 + i for i in range(20)]
        })

        result = self.fetcher.calculate_ma(df, periods=[5, 10, 20])

        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns

    def test_calculate_ma_default_periods(self):
        """测试均线计算默认周期"""
        df = pd.DataFrame({
            'close': [10.0 + i for i in range(300)]
        })

        result = self.fetcher.calculate_ma(df)

        assert 'ma5' in result.columns
        assert 'ma10' in result.columns
        assert 'ma20' in result.columns
        assert 'ma30' in result.columns
        assert 'ma60' in result.columns
        assert 'ma120' in result.columns
        assert 'ma250' in result.columns

    def test_calculate_ma_empty_dataframe(self):
        """测试均线计算空数据框"""
        df = pd.DataFrame({'close': []})

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert result.empty

    def test_calculate_ma_insufficient_data(self):
        """测试均线计算数据不足"""
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0]
        })

        result = self.fetcher.calculate_ma(df, periods=[5, 10])

        assert 'ma5' in result.columns
        assert pd.isna(result['ma5'].iloc[-1])
        assert pd.isna(result['ma10'].iloc[-1])

    def test_calculate_ma_single_value(self):
        """测试均线计算单值"""
        df = pd.DataFrame({'close': [100.0]})

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert 'ma5' in result.columns
        assert pd.isna(result['ma5'].iloc[0])

    def test_calculate_ma_boundary_exactly_5(self):
        """测试均线计算恰好5日"""
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0]
        })

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert not pd.isna(result['ma5'].iloc[-1])
        assert result['ma5'].iloc[-1] == 12.0

    def test_calculate_ma_boundary_6_days(self):
        """测试均线计算6日(边界)"""
        df = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        })

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert not pd.isna(result['ma5'].iloc[-1])
        assert result['ma5'].iloc[-1] == 13.0

    def test_calculate_ma_decimal_values(self):
        """测试均线计算小数数值"""
        df = pd.DataFrame({
            'close': [10.123, 11.456, 12.789, 13.012, 14.345]
        })

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert 'ma5' in result.columns
        assert abs(result['ma5'].iloc[-1] - 12.345) < 0.001

    def test_calculate_ma_unchanged_values(self):
        """测试均线计算值不变"""
        df = pd.DataFrame({
            'close': [10.0, 10.0, 10.0, 10.0, 10.0]
        })

        result = self.fetcher.calculate_ma(df, periods=[5])

        assert result['ma5'].iloc[-1] == 10.0

    def test_calculate_ma_duplicate_periods(self):
        """测试均线计算重复周期"""
        df = pd.DataFrame({
            'close': [10.0 + i for i in range(10)]
        })

        result = self.fetcher.calculate_ma(df, periods=[5, 5, 5])

        assert 'ma5' in result.columns
