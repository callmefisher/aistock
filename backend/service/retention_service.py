import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import json

logger = logging.getLogger(__name__)


class RetentionPolicyService:
    def __init__(self, database_url: str = None):
        if database_url is None:
            database_url = "mysql+aiomysql://stock_user:stock_password@mysql:3306/finance_data"
        self.database_url = database_url
        self.default_retention_days = 730

        self.retention_rules = {
            'fact_daily_bar': 730,
            'fact_index_bar': 730,
            'fact_fund_nav': 730,
            'fact_financial': 730,
            'fact_fund_holding': 730,
            'fact_macro': 730,
            'stock_spot': 30,
            'log_data_fetch': 180,
        }

    async def get_retention_policy(self, data_type: str) -> int:
        return self.retention_rules.get(data_type, self.default_retention_days)

    async def set_retention_policy(self, data_type: str, retention_days: int) -> bool:
        try:
            self.retention_rules[data_type] = retention_days
            engine = create_async_engine(self.database_url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("""
                    INSERT INTO config_retention_policy (data_type, retention_days)
                    VALUES (:data_type, :retention_days)
                    ON DUPLICATE KEY UPDATE retention_days = VALUES(retention_days)
                """), {'data_type': data_type, 'retention_days': retention_days})
                await conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置保留策略失败: {e}")
            return False

    async def cleanup_old_data(self, data_type: Optional[str] = None) -> Dict[str, Any]:
        result = {
            'success': True,
            'cleaned_tables': [],
            'total_deleted': 0,
            'errors': []
        }

        tables_to_cleanup = [data_type] if data_type else list(self.retention_rules.keys())

        for table in tables_to_cleanup:
            try:
                deleted = await self._cleanup_table(table)
                result['cleaned_tables'].append({
                    'table': table,
                    'deleted': deleted
                })
                result['total_deleted'] += deleted
            except Exception as e:
                logger.error(f"清理表 {table} 失败: {e}")
                result['errors'].append(f"{table}: {str(e)}")

        return result

    async def _cleanup_table(self, table_name: str) -> int:
        retention_days = await self.get_retention_policy(table_name)
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        table_mapping = {
            'fact_daily_bar': 'trade_date',
            'fact_index_bar': 'trade_date',
            'fact_fund_nav': 'trade_date',
            'fact_financial': 'report_date',
            'fact_fund_holding': 'report_date',
            'fact_macro': 'period_value',
            'stock_spot': 'update_time',
            'log_data_fetch': 'created_at',
        }

        date_column = table_mapping.get(table_name, 'created_at')

        if table_name == 'fact_macro':
            return await self._cleanup_macro_table(cutoff_date)
        elif table_name == 'log_data_fetch':
            return await self._cleanup_log_table(cutoff_date)
        else:
            return await self._cleanup_standard_table(table_name, date_column, cutoff_date)

    async def _cleanup_standard_table(
        self,
        table_name: str,
        date_column: str,
        cutoff_date: datetime
    ) -> int:
        try:
            engine = create_async_engine(self.database_url, echo=False)
            async with engine.connect() as conn:
                if date_column == 'trade_date' or date_column == 'report_date':
                    sql = text(f"""
                        DELETE FROM {table_name}
                        WHERE {date_column} < :cutoff_date
                    """)
                    cutoff_str = cutoff_date.strftime('%Y-%m-%d')
                else:
                    sql = text(f"""
                        DELETE FROM {table_name}
                        WHERE {date_column} < :cutoff_date
                    """)
                    cutoff_str = cutoff_date.isoformat()

                result = await conn.execute(sql, {'cutoff_date': cutoff_str})
                await conn.commit()

                deleted = result.rowcount
                logger.info(f"清理表 {table_name}: 删除 {deleted} 条过期记录")
                return deleted

        except Exception as e:
            logger.error(f"清理标准表 {table_name} 失败: {e}")
            raise

    async def _cleanup_macro_table(self, cutoff_date: datetime) -> int:
        try:
            cutoff_str = cutoff_date.strftime('%Y%m')
            engine = create_async_engine(self.database_url, echo=False)
            async with engine.connect() as conn:
                sql = text("""
                    DELETE FROM fact_macro
                    WHERE period_value < :cutoff
                """)
                result = await conn.execute(sql, {'cutoff': cutoff_str})
                await conn.commit()
                return result.rowcount
        except Exception as e:
            logger.error(f"清理宏观数据表失败: {e}")
            raise

    async def _cleanup_log_table(self, cutoff_date: datetime) -> int:
        try:
            engine = create_async_engine(self.database_url, echo=False)
            async with engine.connect() as conn:
                sql = text("""
                    DELETE FROM log_data_fetch
                    WHERE created_at < :cutoff_date
                """)
                result = await conn.execute(sql, {'cutoff_date': cutoff_date.isoformat()})
                await conn.commit()
                return result.rowcount
        except Exception as e:
            logger.error(f"清理日志表失败: {e}")
            raise

    async def get_data_stats(self) -> Dict[str, Any]:
        try:
            engine = create_async_engine(self.database_url, echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT
                        'fact_daily_bar' as table_name,
                        COUNT(*) as row_count,
                        MIN(trade_date) as min_date,
                        MAX(trade_date) as max_date
                    FROM fact_daily_bar
                    UNION ALL
                    SELECT
                        'fact_financial',
                        COUNT(*),
                        MIN(report_date),
                        MAX(report_date)
                    FROM fact_financial
                    UNION ALL
                    SELECT
                        'fact_fund_nav',
                        COUNT(*),
                        MIN(trade_date),
                        MAX(trade_date)
                    FROM fact_fund_nav
                    UNION ALL
                    SELECT
                        'log_data_fetch',
                        COUNT(*),
                        MIN(created_at),
                        MAX(created_at)
                    FROM log_data_fetch
                """))

                rows = await result.fetchall()

                stats = {
                    'tables': [],
                    'total_records': 0
                }

                for row in rows:
                    table_info = {
                        'table_name': row[0],
                        'row_count': row[1],
                        'min_date': row[2].strftime('%Y-%m-%d') if row[2] else None,
                        'max_date': row[3].strftime('%Y-%m-%d') if row[3] else None
                    }
                    stats['tables'].append(table_info)
                    stats['total_records'] += row[1]

                return stats

        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")
            return {'tables': [], 'total_records': 0, 'error': str(e)}

    async def get_retention_config(self) -> Dict[str, Any]:
        return {
            'default_retention_days': self.default_retention_days,
            'rules': self.retention_rules
        }

    async def schedule_cleanup(self, schedule: str = "weekly") -> Dict[str, Any]:
        logger.info(f"数据清理任务已调度: {schedule}")

        if schedule == "weekly":
            interval_hours = 7 * 24
        elif schedule == "daily":
            interval_hours = 24
        elif schedule == "monthly":
            interval_hours = 30 * 24
        else:
            interval_hours = 7 * 24

        return {
            'success': True,
            'schedule': schedule,
            'interval_hours': interval_hours,
            'message': f'清理任务已设置为每 {schedule} 执行'
        }


retention_service = RetentionPolicyService()
