import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class DatabaseWriter:
    def __init__(self, database_url: str = None):
        if database_url is None:
            from core.config import settings
            database_url = settings.DATABASE_URL
        self.database_url = database_url
        self.async_engine = create_async_engine(database_url, echo=False)
        self.async_session = sessionmaker(
            self.async_engine, class_=AsyncSession, expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self):
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def write_daily_bar(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        async with self.get_session() as session:
            for _, row in df.iterrows():
                stmt = text("""
                    INSERT INTO fact_daily_bar
                    (stock_code, trade_date, open, high, low, close, volume, amount,
                     turnover_rate, amplitude, change_pct, change_amount, pre_close,
                     ma5, ma10, ma20, ma30, ma60, ma120, ma250, volume_ratio)
                    VALUES
                    (:stock_code, :trade_date, :open, :high, :low, :close, :volume, :amount,
                     :turnover_rate, :amplitude, :change_pct, :change_amount, :pre_close,
                     :ma5, :ma10, :ma20, :ma30, :ma60, :ma120, :ma250, :volume_ratio)
                    ON DUPLICATE KEY UPDATE
                    open = VALUES(open), high = VALUES(high), low = VALUES(low),
                    close = VALUES(close), volume = VALUES(volume), amount = VALUES(amount)
                """)
                await session.execute(stmt, {
                    'stock_code': row['stock_code'],
                    'trade_date': row['trade_date'].strftime('%Y-%m-%d') if hasattr(row['trade_date'], 'strftime') else row['trade_date'],
                    'open': float(row['open']) if pd.notna(row['open']) else 0,
                    'high': float(row['high']) if pd.notna(row['high']) else 0,
                    'low': float(row['low']) if pd.notna(row['low']) else 0,
                    'close': float(row['close']) if pd.notna(row['close']) else 0,
                    'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                    'amount': float(row['amount']) if pd.notna(row['amount']) else 0,
                    'turnover_rate': float(row['turnover_rate']) if pd.notna(row.get('turnover_rate', 0)) else 0,
                    'amplitude': float(row['amplitude']) if pd.notna(row.get('amplitude', 0)) else 0,
                    'change_pct': float(row['change_pct']) if pd.notna(row.get('change_pct', 0)) else 0,
                    'change_amount': float(row['change_amount']) if pd.notna(row.get('change_amount', 0)) else 0,
                    'pre_close': float(row['pre_close']) if pd.notna(row.get('pre_close', 0)) else 0,
                    'ma5': float(row['ma5']) if pd.notna(row.get('ma5', 0)) else 0,
                    'ma10': float(row['ma10']) if pd.notna(row.get('ma10', 0)) else 0,
                    'ma20': float(row['ma20']) if pd.notna(row.get('ma20', 0)) else 0,
                    'ma30': float(row['ma30']) if pd.notna(row.get('ma30', 0)) else 0,
                    'ma60': float(row['ma60']) if pd.notna(row.get('ma60', 0)) else 0,
                    'ma120': float(row['ma120']) if pd.notna(row.get('ma120', 0)) else 0,
                    'ma250': float(row['ma250']) if pd.notna(row.get('ma250', 0)) else 0,
                    'volume_ratio': float(row['volume_ratio']) if pd.notna(row.get('volume_ratio', 0)) else 0,
                })
            await session.commit()
        return len(df)

    async def write_dim_stock(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        async with self.get_session() as session:
            for _, row in df.iterrows():
                stmt = text("""
                    INSERT INTO dim_stock
                    (stock_code, stock_name, exchange_code, listing_date, is_active)
                    VALUES
                    (:stock_code, :stock_name, :exchange_code, :listing_date, 1)
                    ON DUPLICATE KEY UPDATE
                    stock_name = VALUES(stock_name)
                """)
                await session.execute(stmt, {
                    'stock_code': row['stock_code'],
                    'stock_name': row.get('stock_name', ''),
                    'exchange_code': row.get('exchange_code', ''),
                    'listing_date': row.get('listing_date', None),
                })
        return len(df)

    async def write_financial(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0

        async with self.get_session() as session:
            for _, row in df.iterrows():
                stmt = text("""
                    INSERT INTO fact_financial
                    (stock_code, report_date, report_type, revenue, revenue_yoy,
                     net_profit, net_profit_yoy, total_assets, total_liabilities, equity,
                     roe, gross_margin, net_margin, eps, bps, pe_ratio, pb_ratio, ps_ratio)
                    VALUES
                    (:stock_code, :report_date, :report_type, :revenue, :revenue_yoy,
                     :net_profit, :net_profit_yoy, :total_assets, :total_liabilities, :equity,
                     :roe, :gross_margin, :net_margin, :eps, :bps, :pe_ratio, :pb_ratio, :ps_ratio)
                    ON DUPLICATE KEY UPDATE
                    revenue = VALUES(revenue), net_profit = VALUES(net_profit), roe = VALUES(roe)
                """)
                await session.execute(stmt, {
                    'stock_code': row.get('stock_code', ''),
                    'report_date': row.get('report_date', None),
                    'report_type': row.get('report_type', 'FY'),
                    'revenue': float(row['revenue']) if pd.notna(row.get('revenue')) else None,
                    'revenue_yoy': float(row['revenue_yoy']) if pd.notna(row.get('revenue_yoy')) else None,
                    'net_profit': float(row['net_profit']) if pd.notna(row.get('net_profit')) else None,
                    'net_profit_yoy': float(row['net_profit_yoy']) if pd.notna(row.get('net_profit_yoy')) else None,
                    'total_assets': float(row['total_assets']) if pd.notna(row.get('total_assets')) else None,
                    'total_liabilities': float(row['total_liabilities']) if pd.notna(row.get('total_liabilities')) else None,
                    'equity': float(row['equity']) if pd.notna(row.get('equity')) else None,
                    'roe': float(row['roe']) if pd.notna(row.get('roe')) else None,
                    'gross_margin': float(row['gross_margin']) if pd.notna(row.get('gross_margin')) else None,
                    'net_margin': float(row['net_margin']) if pd.notna(row.get('net_margin')) else None,
                    'eps': float(row['eps']) if pd.notna(row.get('eps')) else None,
                    'bps': float(row['bps']) if pd.notna(row.get('bps')) else None,
                    'pe_ratio': float(row['pe_ratio']) if pd.notna(row.get('pe_ratio')) else None,
                    'pb_ratio': float(row['pb_ratio']) if pd.notna(row.get('pb_ratio')) else None,
                    'ps_ratio': float(row['ps_ratio']) if pd.notna(row.get('ps_ratio')) else None,
                })
        return len(df)

    async def get_last_trade_date(self, stock_code: str) -> Optional[str]:
        async with self.get_session() as session:
            stmt = text("""
                SELECT MAX(trade_date) as last_date
                FROM fact_daily_bar
                WHERE stock_code = :stock_code
            """)
            result = await session.execute(stmt, {'stock_code': stock_code})
            row = result.fetchone()
            if row and row[0]:
                return row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0])
            return None


db_writer = DatabaseWriter()
