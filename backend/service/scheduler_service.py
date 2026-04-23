import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pandas as pd

from utils.beijing_time import BEIJING_TZ, beijing_today_str

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.running = False
        self.tasks: Dict[str, asyncio.Task] = {}
        self.last_run: Dict[str, datetime] = {}

    async def start(self):
        self.running = True
        logger.info("调度服务启动")
        asyncio.create_task(self._run_scheduler())

    async def stop(self):
        self.running = False
        for task_name, task in self.tasks.items():
            if not task.done():
                task.cancel()
        logger.info("调度服务停止")

    async def _run_scheduler(self):
        while self.running:
            try:
                now = datetime.now()
                await self._check_and_run_tasks(now)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"调度器执行错误: {e}")
                await asyncio.sleep(60)

    async def _check_and_run_tasks(self, now: datetime):
        pass

    def _determine_stocks_to_update(
        self,
        stock_list: pd.DataFrame,
        now: datetime
    ) -> List[str]:
        current_year = now.year
        last_year = current_year - 1
        current_month = now.month
        current_day = now.day

        stocks_to_update = []

        for _, row in stock_list.iterrows():
            stock_code = row['stock_code']
            last_date = self._get_last_update_date(stock_code)

            if last_date is None:
                stocks_to_update.append(stock_code)
                continue

            last_year = last_date.year
            days_since_update = (now - last_date).days

            if last_year == current_year:
                if days_since_update >= 1:
                    stocks_to_update.append(stock_code)
            elif last_year == current_year - 1:
                if days_since_update >= 5:
                    stocks_to_update.append(stock_code)
            else:
                stocks_to_update.append(stock_code)

        return stocks_to_update

    def _get_last_update_date(self, stock_code: str) -> Optional[datetime]:
        try:
            from service.db_writer import db_writer
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(db_writer.get_last_trade_date(stock_code))
                return loop.run_until_complete(future)
            else:
                return loop.run_until_complete(db_writer.get_last_trade_date(stock_code))
        except Exception as e:
            logger.error(f"获取股票 {stock_code} 最后更新日期失败: {e}")
            return None

    async def _update_stock_daily(self, stock_code: str, now: datetime):
        from fetcher.akshare_fetcher import stock_fetcher
        from service.db_writer import db_writer

        current_year = now.year
        last_year = current_year - 1

        end_date = now.strftime('%Y-%m-%d')

        if self._should_update_full_history(stock_code, now):
            start_date = f"{last_year}-01-01"
        else:
            if now.month <= 1 and now.day <= 5:
                start_date = f"{last_year}-12-01"
            else:
                start_date = now.strftime('%Y-%m-01')

        logger.info(f"更新股票 {stock_code}: {start_date} ~ {end_date}")

        df = stock_fetcher.fetch_daily_bar(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date
        )

        if df.empty:
            logger.warning(f"股票 {stock_code} 无新数据")
            return

        count = await db_writer.write_daily_bar(df)
        logger.info(f"股票 {stock_code} 更新成功: {count} 条数据")

    def _should_update_full_history(self, stock_code: str, now: datetime) -> bool:
        try:
            last_date = self._get_last_update_date(stock_code)
            if last_date is None:
                return True
            return (now - last_date).days > 365
        except Exception:
            return True

    async def run_manual_update(
        self,
        data_type: str,
        stock_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        from fetcher.akshare_fetcher import stock_fetcher, index_fetcher, fund_fetcher, macro_fetcher
        from service.db_writer import db_writer

        result = {
            "success": False,
            "data_type": data_type,
            "records_updated": 0,
            "stocks_updated": 0,
            "errors": []
        }

        try:
            if data_type == "stock_daily":
                if stock_code:
                    stocks_to_update = [stock_code]
                else:
                    stock_list = stock_fetcher.fetch_stock_list()
                    if stock_list.empty:
                        result["errors"].append("获取股票列表失败")
                        return result
                    stocks_to_update = stock_list['stock_code'].tolist()[:100]

                for code in stocks_to_update:
                    try:
                        df = stock_fetcher.fetch_daily_bar(
                            stock_code=code,
                            start_date=start_date or (datetime.now(BEIJING_TZ) - timedelta(days=30)).strftime('%Y-%m-%d'),
                            end_date=end_date or beijing_today_str()
                        )
                        if not df.empty:
                            count = await db_writer.write_daily_bar(df)
                            result["records_updated"] += count
                            result["stocks_updated"] += 1
                    except Exception as e:
                        result["errors"].append(f"{code}: {str(e)}")

                result["success"] = True

            elif data_type == "stock_spot":
                df = stock_fetcher.fetch_spot()
                if df.empty:
                    result["errors"].append("获取实时行情失败")
                else:
                    result["records_updated"] = len(df)
                    result["success"] = True

            elif data_type == "financial":
                stock_list = stock_fetcher.fetch_stock_list()
                for _, row in stock_list.iterrows():
                    try:
                        code = row['stock_code']
                        df = stock_fetcher.fetch_financial(code)
                        if not df.empty:
                            count = await db_writer.write_financial(df)
                            result["records_updated"] += count
                    except Exception as e:
                        result["errors"].append(f"{code}: {str(e)}")
                result["success"] = True

            elif data_type == "fund_nav":
                fund_list = fund_fetcher.fetch_fund_list()
                for _, row in fund_list.iterrows():
                    try:
                        code = row['fund_code']
                        df = fund_fetcher.fetch_fund_nav(code)
                        if not df.empty:
                            result["records_updated"] += len(df)
                    except Exception as e:
                        result["errors"].append(f"{code}: {str(e)}")
                result["success"] = True

            elif data_type == "index_bar":
                df = index_fetcher.fetch_index_bar(
                    index_code=stock_code or "000001",
                    start_date=start_date or (datetime.now(BEIJING_TZ) - timedelta(days=30)).strftime('%Y-%m-%d'),
                    end_date=end_date or beijing_today_str()
                )
                if not df.empty:
                    result["records_updated"] = len(df)
                result["success"] = True

            elif data_type == "macro":
                df = macro_fetcher.fetch_money_supply()
                if not df.empty:
                    result["records_updated"] = len(df)
                df = macro_fetcher.fetch_gdp()
                if not df.empty:
                    result["records_updated"] += len(df)
                result["success"] = True

            else:
                result["errors"].append(f"未知数据类型: {data_type}")

        except Exception as e:
            logger.error(f"手动更新 {data_type} 失败: {e}")
            result["errors"].append(str(e))

        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "active_tasks": len([t for t in self.tasks.values() if not t.done()]),
            "last_run": {k: v.isoformat() if v else None for k, v in self.last_run.items()}
        }


scheduler_service = SchedulerService()
