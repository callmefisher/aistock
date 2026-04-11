import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


class TestDatabaseWriter:
    """数据库写入测试"""

    def test_write_daily_bar_empty_dataframe(self):
        """测试写入空数据框"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
            df = pd.DataFrame()

            result = writer.write_daily_bar(df)

            assert result == 0

    def test_write_daily_bar_success(self):
        """测试写入日线数据成功"""
        from service.db_writer import DatabaseWriter

        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(5)]
        df = pd.DataFrame({
            'stock_code': ['600000'] * 5,
            'trade_date': dates,
            'open': [10.0] * 5,
            'high': [12.0] * 5,
            'low': [9.0] * 5,
            'close': [11.0] * 5,
            'volume': [1000000] * 5,
            'amount': [11000000] * 5,
            'turnover_rate': [2.0] * 5,
            'amplitude': [5.0] * 5,
            'change_pct': [1.0] * 5,
            'change_amount': [0.5] * 5,
            'pre_close': [10.5] * 5,
            'ma5': [10.8] * 5,
            'ma10': [10.5] * 5,
            'ma20': [10.2] * 5,
            'ma30': [10.0] * 5,
            'ma60': [9.8] * 5,
            'ma120': [9.5] * 5,
            'ma250': [9.0] * 5,
            'volume_ratio': [1.2] * 5
        })

        with patch('service.db_writer.create_async_engine') as mock_engine:
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")

                result = writer.write_daily_bar(df)

                assert result == 5

    def test_write_daily_bar_null_values(self):
        """测试写入包含空值的日线数据"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'trade_date': [datetime.now()],
            'open': [None],
            'high': [12.0],
            'low': [9.0],
            'close': [11.0],
            'volume': [1000000],
            'amount': [11000000],
            'turnover_rate': [None],
            'amplitude': [5.0],
            'change_pct': [1.0],
            'change_amount': [0.5],
            'pre_close': [None],
            'ma5': [None],
            'ma10': [10.5],
            'ma20': [10.2],
            'ma30': [10.0],
            'ma60': [9.8],
            'ma120': [9.5],
            'ma250': [9.0],
            'volume_ratio': [None]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_daily_bar(df)
                assert result == 1

    def test_write_dim_stock_empty(self):
        """测试写入空股票维度数据"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                df = pd.DataFrame()

                result = writer.write_dim_stock(df)

                assert result == 0

    def test_write_dim_stock_success(self):
        """测试写入股票维度数据成功"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000', '000001'],
            'stock_name': ['浦发银行', '平安银行'],
            'exchange_code': ['SH', 'SZ'],
            'listing_date': ['2020-01-01', '2020-02-01']
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_dim_stock(df)

                assert result == 2

    def test_write_dim_stock_missing_columns(self):
        """测试写入股票维度数据缺少列"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000']
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_dim_stock(df)

                assert result == 1

    def test_write_financial_empty(self):
        """测试写入空财务数据"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                df = pd.DataFrame()

                result = writer.write_financial(df)

                assert result == 0

    def test_write_financial_success(self):
        """测试写入财务数据成功"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'] * 3,
            'report_date': ['2025-12-31', '2025-09-30', '2025-06-30'],
            'report_type': ['FY', 'Q3', 'Q2'],
            'revenue': [1000000, 750000, 500000],
            'revenue_yoy': [10.5, 8.3, 6.2],
            'net_profit': [100000, 75000, 50000],
            'net_profit_yoy': [15.0, 12.0, 9.0],
            'total_assets': [5000000, 4900000, 4800000],
            'total_liabilities': [2500000, 2450000, 2400000],
            'equity': [2500000, 2450000, 2400000],
            'roe': [10.0, 9.5, 9.0],
            'gross_margin': [30.0, 29.0, 28.0],
            'net_margin': [10.0, 10.0, 10.0],
            'eps': [1.0, 0.75, 0.5],
            'bps': [10.0, 9.8, 9.6],
            'pe_ratio': [15.0, 14.5, 14.0],
            'pb_ratio': [1.5, 1.4, 1.3],
            'ps_ratio': [1.0, 0.9, 0.8]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_financial(df)

                assert result == 3

    def test_write_financial_null_values(self):
        """测试写入财务数据包含空值"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'report_date': ['2025-12-31'],
            'report_type': ['FY'],
            'revenue': [None],
            'revenue_yoy': [None],
            'net_profit': [None],
            'net_profit_yoy': [None],
            'total_assets': [None],
            'total_liabilities': [None],
            'equity': [None],
            'roe': [None],
            'gross_margin': [None],
            'net_margin': [None],
            'eps': [None],
            'bps': [None],
            'pe_ratio': [None],
            'pb_ratio': [None],
            'ps_ratio': [None]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_financial(df)

                assert result == 1

    def test_write_financial_negative_values(self):
        """测试写入财务数据负值"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'report_date': ['2025-12-31'],
            'report_type': ['FY'],
            'revenue': [-100000],
            'revenue_yoy': [-10.0],
            'net_profit': [-50000],
            'net_profit_yoy': [-15.0],
            'total_assets': [5000000],
            'total_liabilities': [5500000],
            'equity': [-500000],
            'roe': [-5.0],
            'gross_margin': [-10.0],
            'net_margin': [-5.0],
            'eps': [-0.5],
            'bps': [-2.0],
            'pe_ratio': [-15.0],
            'pb_ratio': [-1.5],
            'ps_ratio': [-1.0]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_financial(df)

                assert result == 1

    def test_write_financial_zero_values(self):
        """测试写入财务数据零值"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'report_date': ['2025-12-31'],
            'report_type': ['FY'],
            'revenue': [0],
            'revenue_yoy': [0],
            'net_profit': [0],
            'net_profit_yoy': [0],
            'total_assets': [0],
            'total_liabilities': [0],
            'equity': [0],
            'roe': [0],
            'gross_margin': [0],
            'net_margin': [0],
            'eps': [0],
            'bps': [0],
            'pe_ratio': [0],
            'pb_ratio': [0],
            'ps_ratio': [0]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_financial(df)

                assert result == 1

    def test_write_financial_extreme_values(self):
        """测试写入财务数据极端值"""
        from service.db_writer import DatabaseWriter

        df = pd.DataFrame({
            'stock_code': ['600000'],
            'report_date': ['2025-12-31'],
            'report_type': ['FY'],
            'revenue': [1e15],
            'revenue_yoy': [999.99],
            'net_profit': [1e12],
            'net_profit_yoy': [999.99],
            'total_assets': [1e18],
            'total_liabilities': [1e17],
            'equity': [1e16],
            'roe': [999.99],
            'gross_margin': [99.99],
            'net_margin': [99.99],
            'eps': [1e6],
            'bps': [1e8],
            'pe_ratio': [1e8],
            'pb_ratio': [1e5],
            'ps_ratio': [1e5]
        })

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock):
                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.write_financial(df)

                assert result == 1


class TestDatabaseConnection:
    """数据库连接测试"""

    def test_database_url_construction(self):
        """测试数据库URL构建"""
        from service.db_writer import DatabaseWriter

        writer = DatabaseWriter("mysql+aiomysql://user:pass@localhost:3306/testdb")

        assert writer.database_url == "mysql+aiomysql://user:pass@localhost:3306/testdb"

    def test_database_url_default(self):
        """测试数据库URL默认"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            writer = DatabaseWriter()

            assert "finance_data" in writer.database_url

    def test_get_last_trade_date_exists(self):
        """测试获取最后交易日期存在"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock) as mock_session:
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (datetime(2026, 4, 9),)
                mock_session.return_value.__aenter__.return_value.execute.return_value.fetchone = mock_result.fetchone

                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.get_last_trade_date("600000")

    def test_get_last_trade_date_not_exists(self):
        """测试获取最后交易日期不存在"""
        from service.db_writer import DatabaseWriter

        with patch('service.db_writer.create_async_engine'):
            with patch.object(DatabaseWriter, 'get_session', new_callable=AsyncMock) as mock_session:
                mock_result = MagicMock()
                mock_result.fetchone.return_value = (None,)
                mock_session.return_value.__aenter__.return_value.execute.return_value.fetchone = mock_result.fetchone

                writer = DatabaseWriter("mysql+aiomysql://test:test@localhost/test")
                result = writer.get_last_trade_date("600000")

                assert result is None
