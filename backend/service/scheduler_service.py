import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd

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

    def _should_update_full_history(self, stock_code: str, now: datetime) -> bool:
        try:
            last_date = self._get_last_update_date(stock_code)
            if last_date is None:
                return True
            return (now - last_date).days > 365
        except Exception:
            return True

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "active_tasks": len([t for t in self.tasks.values() if not t.done()]),
            "last_run": {k: v.isoformat() if v else None for k, v in self.last_run.items()}
        }


scheduler_service = SchedulerService()
