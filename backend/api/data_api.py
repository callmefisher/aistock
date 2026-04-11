from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class StockQueryRequest(BaseModel):
    stock_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    indicators: Optional[List[str]] = None


class StocksFilterRequest(BaseModel):
    exchange: Optional[str] = None
    industry: Optional[str] = None
    pe_min: Optional[float] = None
    pe_max: Optional[float] = None
    pb_min: Optional[float] = None
    pb_max: Optional[float] = None
    sort_by: Optional[str] = "stock_code"
    order: Optional[str] = "asc"
    limit: Optional[int] = 100


class AIQueryRequest(BaseModel):
    query: str
    mode: Optional[str] = "nl2sql"


class DataFetchRequest(BaseModel):
    data_type: str
    stock_code: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/query/sql")
async def query_sql(sql_request: Dict[str, Any]):
    from service.query_service import query_service
    sql = sql_request.get("sql")
    params = sql_request.get("params", {})
    if not sql:
        raise HTTPException(status_code=400, detail="SQL语句不能为空")
    return await query_service.execute_sql(sql, params)


@router.post("/query/stock-daily")
async def query_stock_daily(request: StockQueryRequest):
    from service.query_service import query_service
    result = await query_service.query_stock_daily(
        stock_code=request.stock_code,
        start_date=request.start_date,
        end_date=request.end_date,
        indicators=request.indicators
    )
    return result


@router.post("/query/stocks-filter")
async def query_stocks_filter(request: StocksFilterRequest):
    from service.query_service import query_service
    result = await query_service.query_stocks(
        exchange=request.exchange,
        industry=request.industry,
        pe_min=request.pe_min,
        pe_max=request.pe_max,
        pb_min=request.pb_min,
        pb_max=request.pb_max,
        sort_by=request.sort_by,
        order=request.order,
        limit=request.limit
    )
    return result


@router.post("/query/ai")
async def query_ai(request: AIQueryRequest):
    from service.query_service import ai_query_service, query_service

    parsed = ai_query_service.parse_query(request.query)

    if not parsed.get("success"):
        return parsed

    if parsed.get("sql"):
        result = await query_service.execute_sql(parsed["sql"])
        return {
            **parsed,
            "results": result.get("data", []),
            "columns": result.get("columns", []),
            "row_count": result.get("row_count", 0)
        }

    return parsed


@router.get("/stock/list")
async def get_stock_list():
    from fetcher.akshare_fetcher import stock_fetcher
    df = stock_fetcher.fetch_stock_list()
    if df.empty:
        return {"success": False, "message": "获取股票列表失败"}
    return {
        "success": True,
        "data": df.to_dict("records"),
        "row_count": len(df)
    }


@router.get("/industry/list")
async def get_industry_list():
    from fetcher.akshare_fetcher import stock_fetcher
    df = stock_fetcher.fetch_industry分类()
    if df.empty:
        return {"success": False, "message": "获取行业列表失败"}
    return {
        "success": True,
        "data": df.to_dict("records"),
        "row_count": len(df)
    }


@router.get("/stock/spot")
async def get_stock_spot():
    from fetcher.akshare_fetcher import stock_fetcher
    df = stock_fetcher.fetch_spot()
    if df.empty:
        return {"success": False, "message": "获取实时行情失败"}
    return {
        "success": True,
        "data": df.to_dict("records"),
        "row_count": len(df)
    }


@router.post("/fetch/daily-bar")
async def fetch_daily_bar(request: DataFetchRequest):
    from fetcher.akshare_fetcher import stock_fetcher
    from service.db_writer import db_writer

    logger.info(f"[DEBUG] fetch_daily_bar called: stock_code={request.stock_code}, start={request.start_date}, end={request.end_date}")

    if not request.start_date:
        raise HTTPException(status_code=400, detail="开始日期不能为空")
    if not request.end_date:
        raise HTTPException(status_code=400, detail="结束日期不能为空")

    if request.stock_code:
        logger.info(f"[DEBUG] Fetching single stock: {request.stock_code}")
        df = stock_fetcher.fetch_daily_bar(
            stock_code=request.stock_code,
            start_date=request.start_date,
            end_date=request.end_date
        )
        logger.info(f"[DEBUG] Single stock result: empty={df.empty}, rows={len(df)}")
        if df.empty:
            return {"success": False, "message": "获取数据失败"}
        count = await db_writer.write_daily_bar(df)
        return {
            "success": True,
            "message": f"成功获取并保存 {count} 条数据",
            "row_count": count
        }
    else:
        logger.info("[DEBUG] Fetching stock list...")
        stock_list = stock_fetcher.fetch_stock_list()
        logger.info(f"[DEBUG] Stock list result: empty={stock_list.empty}, rows={len(stock_list)}, columns={stock_list.columns.tolist()}")
        if stock_list.empty:
            logger.error("[DEBUG] Stock list is empty, returning error")
            return {"success": False, "message": "获取股票列表失败"}

        total_count = 0
        success_count = 0
        fail_count = 0
        max_stocks = 100

        for idx, (_, row) in enumerate(stock_list.iterrows()):
            if idx >= max_stocks:
                break
            stock_code = row['stock_code']
            try:
                df = stock_fetcher.fetch_daily_bar(
                    stock_code=stock_code,
                    start_date=request.start_date,
                    end_date=request.end_date
                )
                if not df.empty:
                    count = await db_writer.write_daily_bar(df)
                    total_count += count
                    success_count += 1
            except Exception as e:
                logger.error(f"获取 {stock_code} 数据失败: {e}")
                fail_count += 1

        return {
            "success": True,
            "message": f"成功 {success_count} 只，失败 {fail_count} 只，共 {total_count} 条数据 (限制{max_stocks}只)",
            "total_records": total_count,
            "success_stocks": success_count,
            "fail_stocks": fail_count
        }


@router.post("/fetch/bulk-daily-bar")
async def fetch_bulk_daily_bar(request: DataFetchRequest):
    from fetcher.akshare_fetcher import stock_fetcher
    from service.db_writer import db_writer

    if not request.start_date:
        raise HTTPException(status_code=400, detail="开始日期不能为空")
    if not request.end_date:
        raise HTTPException(status_code=400, detail="结束日期不能为空")

    logger.info(f"批量获取日线数据: {request.start_date} ~ {request.end_date}")

    stock_list = stock_fetcher.fetch_stock_list()
    if stock_list.empty:
        return {"success": False, "message": "获取股票列表失败"}

    total_count = 0
    success_count = 0
    fail_count = 0

    for _, row in stock_list.iterrows():
        stock_code = row['stock_code']
        try:
            df = stock_fetcher.fetch_daily_bar(
                stock_code=stock_code,
                start_date=request.start_date,
                end_date=request.end_date
            )
            if not df.empty:
                count = await db_writer.write_daily_bar(df)
                total_count += count
                success_count += 1
        except Exception as e:
            logger.error(f"获取 {stock_code} 数据失败: {e}")
            fail_count += 1

    return {
        "success": True,
        "message": f"成功 {success_count} 只，失败 {fail_count} 只，共 {total_count} 条数据",
        "total_records": total_count,
        "success_stocks": success_count,
        "fail_stocks": fail_count
    }


@router.get("/fetch/status")
async def get_fetch_status():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    try:
        engine = create_async_engine("mysql+aiomysql://stock_user:stock_password@stock_mysql:3306/stock_pool")
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM dim_stock) as stock_count,
                    (SELECT COUNT(*) FROM fact_daily_bar) as daily_bar_count,
                    (SELECT COUNT(*) FROM fact_financial) as financial_count,
                    (SELECT MAX(trade_date) FROM fact_daily_bar) as last_trade_date,
                    (SELECT MAX(report_date) FROM fact_financial) as last_report_date
            """))
            row = result.fetchone()

            return {
                "success": True,
                "data": {
                    "stock_count": row[0] if row else 0,
                    "daily_bar_count": row[1] if row else 0,
                    "financial_count": row[2] if row else 0,
                    "last_trade_date": row[3].strftime('%Y-%m-%d') if row and row[3] else None,
                    "last_report_date": row[4].strftime('%Y-%m-%d') if row and row[4] else None
                }
            }
    except Exception as e:
        logger.error(f"获取数据状态失败: {e}")
        return {"success": False, "message": str(e)}


@router.get("/config/list")
async def get_config_list():
    from service.retention_service import retention_service

    try:
        retention_config = await retention_service.get_retention_config()
        return {
            "success": True,
            "data": {
                "fetch_configs": [
                    {"data_type": "stock_daily", "fetch_frequency": "hourly", "last_fetch_time": None, "is_enabled": True},
                    {"data_type": "stock_spot", "fetch_frequency": "daily", "last_fetch_time": None, "is_enabled": True},
                    {"data_type": "financial", "fetch_frequency": "daily", "last_fetch_time": None, "is_enabled": True}
                ],
                "retention_configs": retention_config.get("rules", {})
            }
        }
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        return {"success": False, "message": str(e)}


class RetentionConfigRequest(BaseModel):
    data_type: str
    retention_days: int = 730


@router.post("/config/retention")
async def save_retention_config(request: RetentionConfigRequest):
    from service.retention_service import retention_service

    try:
        await retention_service.set_retention_policy(request.data_type, request.retention_days)
        return {"success": True, "message": "配置已保存"}
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return {"success": False, "message": str(e)}


@router.post("/config/cleanup")
async def execute_cleanup():
    from service.retention_service import retention_service

    try:
        result = await retention_service.cleanup_old_data()
        return {
            "success": True,
            "message": f"清理完成",
            "total_deleted": result.get("total_deleted", 0)
        }
    except Exception as e:
        logger.error(f"清理失败: {e}")
        return {"success": False, "message": str(e)}
