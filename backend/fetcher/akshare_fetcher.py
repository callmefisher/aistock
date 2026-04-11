import akshare as ak
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StockFetcher:
    def __init__(self):
        self.source = "akshare"

    def fetch_stock_list(self) -> pd.DataFrame:
        try:
            df = ak.stock_info_a_code_name()
            logger.info(f"[DEBUG] raw df shape: {df.shape}, columns: {df.columns.tolist()}")
            if len(df.columns) == 2:
                df.columns = ['stock_code', 'stock_name']
            elif len(df.columns) == 3:
                df = df.iloc[:, :2]
                df.columns = ['stock_code', 'stock_name']
            else:
                df = df[['code', 'name']]
                df.columns = ['stock_code', 'stock_name']
            df['exchange_code'] = df['stock_code'].apply(
                lambda x: 'SH' if str(x).startswith(('6', '5', '9')) else 'SZ'
            )
            df = df[['stock_code', 'stock_name', 'exchange_code']]
            logger.info(f"获取股票列表成功，共 {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return pd.DataFrame()

    def fetch_industry分类(self) -> pd.DataFrame:
        try:
            df = ak.stock_board_industry_name_em()
            df.columns = ['industry_code', 'industry_name', 'volume', 'amount', 'change_pct', 'stock_count', 'lead_stock']
            df = df[['industry_code', 'industry_name', 'stock_count']]
            logger.info(f"获取行业分类成功，共 {len(df)} 个行业")
            return df
        except Exception as e:
            logger.error(f"获取行业分类失败: {e}")
            return pd.DataFrame()

    def fetch_daily_bar(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            symbol = stock_code if stock_code.startswith(('sh', 'sz')) else ('sh' + stock_code if stock_code.startswith(('6', '5', '9')) else 'sz' + stock_code)
            df = ak.stock_zh_a_daily(symbol=symbol, adjust=adjust)
            df['date'] = pd.to_datetime(df['date']).dt.date
            df = df[(df['date'] >= pd.to_datetime(start_date).date()) & (df['date'] <= pd.to_datetime(end_date).date())]
            df = self._normalize_daily_bar(df, stock_code)
            logger.info(f"获取 {stock_code} 日线数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取 {stock_code} 日线数据失败: {e}")
            return pd.DataFrame()

    def fetch_bulk_daily_bar(
        self,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        try:
            df = ak.stock_zh_a_daily(symbol="sh600000", adjust=adjust)
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            logger.info(f"批量获取日线数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"批量获取日线数据失败: {e}")
            return pd.DataFrame()

    def fetch_spot(self) -> pd.DataFrame:
        try:
            df = ak.stock_zh_a_spot_em()
            rename_map = {
                '代码': 'stock_code',
                '名称': 'stock_name',
                '最新价': 'close',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change_amount',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'pre_close',
                '量比': 'volume_ratio',
                '换手率': 'turnover_rate',
                '市盈率-动态': 'pe_ratio',
                '市净率': 'pb_ratio',
                '总市值': 'total_market_cap',
                '流通市值': 'float_market_cap',
            }
            df = df.rename(columns=rename_map)
            logger.info(f"获取实时行情成功，共 {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()

    def fetch_financial(
        self,
        stock_code: str,
        start_year: int = None,
        end_year: int = None
    ) -> pd.DataFrame:
        try:
            if start_year is None:
                start_year = datetime.now().year - 2
            if end_year is None:
                end_year = datetime.now().year

            df = ak.stock_financial_analysis_indicator_em(
                symbol=stock_code
            )
            df = self._normalize_financial(df, stock_code)
            logger.info(f"获取 {stock_code} 财务数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取 {stock_code} 财务数据失败: {e}")
            return pd.DataFrame()

    def _normalize_daily_bar(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        if df.empty:
            return df

        rename_map = {
            '日期': 'trade_date',
            'date': 'trade_date',
            '开盘': 'open',
            'open': 'open',
            '收盘': 'close',
            'close': 'close',
            '最高': 'high',
            'high': 'high',
            '最低': 'low',
            'low': 'low',
            '成交量': 'volume',
            'volume': 'volume',
            '成交额': 'amount',
            'amount': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change_amount',
            '换手率': 'turnover_rate',
            'turnover': 'turnover_rate'
        }
        df = df.rename(columns=rename_map)
        df['stock_code'] = stock_code
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        if 'pre_close' not in df.columns:
            df['pre_close'] = df['close'].shift(1)

        if 'change_pct' not in df.columns:
            df['change_pct'] = (df['close'] - df['pre_close']) / df['pre_close'] * 100

        if 'change_amount' not in df.columns:
            df['change_amount'] = df['close'] - df['pre_close']

        if 'amplitude' not in df.columns:
            df['amplitude'] = (df['high'] - df['low']) / df['low'] * 100

        periods = [5, 10, 20, 30, 60, 120, 250]
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        if 'volume_ratio' not in df.columns:
            df['volume_ratio'] = df['volume'] / df['volume'].shift(1)

        return df

    def calculate_ma(self, df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        if periods is None:
            periods = [5, 10, 20, 30, 60, 120, 250]
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()
        return df

    def _normalize_financial(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        rename_map = {
            '日期': 'report_date',
            '股票代码': 'stock_code',
            '股票简称': 'stock_name',
            '营业总收入': 'revenue',
            '总收入同比增长': 'revenue_yoy',
            '净利润': 'net_profit',
            '净利润同比增长': 'net_profit_yoy',
            '总资产': 'total_assets',
            '总负债': 'total_liabilities',
            '所有者权益': 'equity',
            '净资产收益率': 'roe',
            '销售毛利率': 'gross_margin',
            '销售净利率': 'net_margin',
            '基本每股收益': 'eps',
            '每股净资产': 'bps',
            '市盈率': 'pe_ratio',
            '市净率': 'pb_ratio',
            '市销率': 'ps_ratio',
        }
        df = df.rename(columns=rename_map)
        if 'stock_code' not in df.columns:
            df['stock_code'] = stock_code
        return df


class IndexFetcher:
    def __init__(self):
        self.source = "akshare"

    def fetch_index_list(self) -> pd.DataFrame:
        try:
            df = ak.index_zh_a_hist_sina()
            df = df.rename(columns={
                '代码': 'index_code',
                '名称': 'index_name'
            })
            logger.info(f"获取指数列表成功，共 {len(df)} 个")
            return df
        except Exception as e:
            logger.error(f"获取指数列表失败: {e}")
            return pd.DataFrame()

    def fetch_index_bar(
        self,
        index_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        try:
            df = ak.index_zh_a_hist(
                symbol=index_code,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", "")
            )
            df = self._normalize_index_bar(df, index_code)
            logger.info(f"获取 {index_code} 指数数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取 {index_code} 指数数据失败: {e}")
            return pd.DataFrame()

    def fetch_index_components(self, index_code: str = "000300") -> pd.DataFrame:
        try:
            df = ak.index_weight_cons(index_code=index_code)
            df = df.rename(columns={
                '品种代码': 'stock_code',
                '品种名称': 'stock_name',
                '权重': 'weight'
            })
            logger.info(f"获取 {index_code} 成分股成功，共 {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取 {index_code} 成分股失败: {e}")
            return pd.DataFrame()

    def _normalize_index_bar(self, df: pd.DataFrame, index_code: str) -> pd.DataFrame:
        df = df.rename(columns={
            '日期': 'trade_date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'change_pct'
        })
        df['index_code'] = index_code
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        for period in [5, 10, 20, 60]:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        return df


class FundFetcher:
    def __init__(self):
        self.source = "akshare"

    def fetch_fund_list(self, fund_type: str = "全部") -> pd.DataFrame:
        try:
            if fund_type == "股票型":
                df = ak.fund_open_fund_info_em()
            elif fund_type == "混合型":
                df = ak.fund_open_fund_info_em()
            elif fund_type == "债券型":
                df = ak.fund_open_fund_info_em()
            elif fund_type == "指数型":
                df = ak.fund_etf_fund_info_sina()
            else:
                df = ak.fund_open_fund_info_em()

            df = df.rename(columns={
                '基金代码': 'fund_code',
                '基金简称': 'fund_name',
                '基金经理': 'manager',
                '成立日期': 'listing_date',
                '最新规模': 'scale',
                '类型': 'fund_type'
            })
            logger.info(f"获取基金列表成功，共 {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"获取基金列表失败: {e}")
            return pd.DataFrame()

    def fetch_fund_nav(
        self,
        fund_code: str,
        start_date: str = None,
        end_date: str = None
    ) -> pd.DataFrame:
        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            if end_date is None:
                end_date = datetime.now().strftime("%Y-%m-%d")

            df = ak.fund_open_fund_info_em(fund=fund_code, indicator="单位净值走势")
            df = df.rename(columns={
                '日期': 'trade_date',
                '单位净值': 'unit_nav',
                '累计净值': 'accum_nav',
                '日增长率': 'change_pct'
            })
            df['fund_code'] = fund_code
            logger.info(f"获取 {fund_code} 净值数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取 {fund_code} 净值数据失败: {e}")
            return pd.DataFrame()

    def fetch_fund_holding(self, fund_code: str, year: int = None) -> pd.DataFrame:
        try:
            if year is None:
                year = datetime.now().year

            df = ak.fund_report_stock(fund=fund_code, year=year)
            df = df.rename(columns={
                '股票代码': 'stock_code',
                '股票名称': 'stock_name',
                '持仓比例': 'holding_ratio',
                '持股数': 'holding_shares',
                '持仓市值': 'market_value',
                '季度': 'report_date'
            })
            df['fund_code'] = fund_code
            logger.info(f"获取 {fund_code} 持仓数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取 {fund_code} 持仓数据失败: {e}")
            return pd.DataFrame()


class MacroFetcher:
    def __init__(self):
        self.source = "akshare"

    def fetch_money_supply(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_money_supply()
            df = df.rename(columns={
                '月份': 'period_value',
                '广义货币(M2)': 'm2',
                '狭义货币(M1)': 'm1',
                '流通中货币(M0)': 'm0',
                '社会融资规模': 'total_social_financing'
            })
            df['indicator_code'] = 'money_supply'
            df['indicator_name'] = '货币供应量'
            df['period'] = 'M'
            logger.info(f"获取货币供应量数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取货币供应量数据失败: {e}")
            return pd.DataFrame()

    def fetch_gdp(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_gdp()
            df = df.rename(columns={
                '季度': 'period_value',
                '国内生产总值': 'gdp',
                'GDP同比增长': 'gdp_yoy'
            })
            df['indicator_code'] = 'gdp'
            df['indicator_name'] = '国内生产总值'
            df['period'] = 'Q'
            logger.info(f"获取GDP数据成功，共 {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取GDP数据失败: {e}")
            return pd.DataFrame()


stock_fetcher = StockFetcher()
index_fetcher = IndexFetcher()
fund_fetcher = FundFetcher()
macro_fetcher = MacroFetcher()
