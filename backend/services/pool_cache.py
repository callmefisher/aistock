"""选股池代码集合缓存。

缓存结构：{date_str: set(证券代码)}，按 is_active=1 的 stock_pools 聚合。
供"新增行高亮"的 baseline 查询使用。

策略：
- 进程内存缓存，启动时加载一次
- 后台任务每 10 分钟自动刷新
- 入库选股池时调 invalidate()，下一次查询触发 refresh
- 查询接口：get_codes_union(start, end) 返回 [start, end] 闭区间内所有日期代码并集
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Dict, Optional, Set

from sqlalchemy import text

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SEC = 600  # 10 分钟

_cache: Dict[str, Set[str]] = {}
_last_refresh_ts: float = 0.0
_last_refresh_ok: bool = False  # 上次刷新是否成功
_lock = asyncio.Lock()
_refresh_lock = asyncio.Lock()  # 防止并发重复 refresh
_refresh_task: Optional[asyncio.Task] = None


async def refresh_cache() -> int:
    """全量从 DB 加载，按 date_str 聚合 证券代码 集合。"""
    global _cache, _last_refresh_ts, _last_refresh_ok
    from core.database import AsyncSessionLocal

    new_cache: Dict[str, Set[str]] = {}
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(text(
                "SELECT date_str, data FROM stock_pools WHERE is_active = 1"
            ))
            for r in rows.fetchall():
                ds = r[0]
                raw = r[1]
                if not ds or not raw:
                    continue
                try:
                    records = raw if isinstance(raw, list) else json.loads(raw) if isinstance(raw, str) else []
                except Exception:
                    records = []
                if not records:
                    continue
                codes = new_cache.setdefault(ds, set())
                for rec in records:
                    code = str(rec.get("证券代码", "")).strip()
                    if code:
                        codes.add(code)
    except Exception as e:
        logger.exception(f"[pool_cache] refresh 失败: {e}")
        async with _lock:
            _last_refresh_ok = False
        return -1

    async with _lock:
        _cache = new_cache
        _last_refresh_ts = time.time()
        _last_refresh_ok = True
    total_codes = sum(len(v) for v in new_cache.values())
    logger.info(f"[pool_cache] refreshed: {len(new_cache)} dates, {total_codes} codes")
    return len(new_cache)


def invalidate() -> None:
    """标记缓存为过期；下次 get_* 会触发 refresh。"""
    global _last_refresh_ts
    _last_refresh_ts = 0.0


async def _ensure_fresh() -> None:
    """若缓存过期，触发刷新；多个并发调用只有一个真正刷新，其他等待其完成。"""
    if time.time() - _last_refresh_ts <= REFRESH_INTERVAL_SEC:
        return
    async with _refresh_lock:
        # 二次检查：可能上一个等锁期间已经刷好
        if time.time() - _last_refresh_ts <= REFRESH_INTERVAL_SEC:
            return
        await refresh_cache()


async def _db_fallback_union(start_date: str, end_date: str) -> Set[str]:
    """缓存未就绪时的 DB 兜底：直接查 [start, end] 的代码并集。"""
    from core.database import AsyncSessionLocal
    result: Set[str] = set()
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(text(
                "SELECT data FROM stock_pools WHERE is_active=1 "
                "AND date_str >= :s AND date_str <= :e"
            ), {"s": start_date, "e": end_date})
            for r in rows.fetchall():
                raw = r[0]
                if not raw:
                    continue
                try:
                    records = raw if isinstance(raw, list) else json.loads(raw) if isinstance(raw, str) else []
                except Exception:
                    records = []
                for rec in records:
                    code = str(rec.get("证券代码", "")).strip()
                    if code:
                        result.add(code)
    except Exception as e:
        logger.exception(f"[pool_cache] DB 兜底失败: {e}")
    return result


async def _db_fallback_map(start_date: str, end_date: str) -> Dict[str, Set[str]]:
    """DB 兜底：返回 {date_str: set(codes)}"""
    from core.database import AsyncSessionLocal
    result: Dict[str, Set[str]] = {}
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(text(
                "SELECT date_str, data FROM stock_pools WHERE is_active=1 "
                "AND date_str >= :s AND date_str <= :e"
            ), {"s": start_date, "e": end_date})
            for r in rows.fetchall():
                ds = r[0]; raw = r[1]
                if not ds or not raw:
                    continue
                try:
                    records = raw if isinstance(raw, list) else json.loads(raw) if isinstance(raw, str) else []
                except Exception:
                    records = []
                codes = result.setdefault(ds, set())
                for rec in records:
                    code = str(rec.get("证券代码", "")).strip()
                    if code:
                        codes.add(code)
    except Exception as e:
        logger.exception(f"[pool_cache] DB 兜底(map) 失败: {e}")
    return result


async def get_codes_union(start_date: str, end_date: str) -> Set[str]:
    """返回 [start_date, end_date] 闭区间所有日期的代码并集。空则返回空集。"""
    await _ensure_fresh()
    if not start_date or not end_date or start_date > end_date:
        return set()
    # 缓存未就绪 → DB 兜底
    if not _last_refresh_ok:
        logger.info(f"[pool_cache] 缓存未就绪，走 DB 兜底: {start_date}~{end_date}")
        return await _db_fallback_union(start_date, end_date)
    result: Set[str] = set()
    for ds, codes in _cache.items():
        if start_date <= ds <= end_date:
            result |= codes
    return result


async def get_codes_before(date_str: str) -> Set[str]:
    """返回 date_str < 当前日期的所有代码并集（不含当天）。"""
    await _ensure_fresh()
    if not date_str:
        return set()
    if not _last_refresh_ok:
        logger.info(f"[pool_cache] 缓存未就绪，走 DB 兜底 (<{date_str})")
        return await _db_fallback_union("0001-01-01", _prev_day(date_str))
    result: Set[str] = set()
    for ds, codes in _cache.items():
        if ds < date_str:
            result |= codes
    return result


async def get_date_codes_map(start_date: str, end_date: str) -> Dict[str, Set[str]]:
    """返回 [start_date, end_date] 区间内 {date_str: set(codes)} 副本。"""
    await _ensure_fresh()
    if not start_date or not end_date or start_date > end_date:
        return {}
    if not _last_refresh_ok:
        logger.info(f"[pool_cache] 缓存未就绪，走 DB 兜底 map: {start_date}~{end_date}")
        return await _db_fallback_map(start_date, end_date)
    return {ds: codes.copy() for ds, codes in _cache.items()
            if start_date <= ds <= end_date}


def _prev_day(date_str: str) -> str:
    from datetime import datetime as _dt, timedelta as _td
    try:
        d = _dt.strptime(date_str, "%Y-%m-%d").date() - _td(days=1)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return date_str


async def _periodic_refresh_loop() -> None:
    """后台定时刷新循环。"""
    while True:
        try:
            await asyncio.sleep(REFRESH_INTERVAL_SEC)
            await refresh_cache()
        except asyncio.CancelledError:
            logger.info("[pool_cache] periodic refresh cancelled")
            raise
        except Exception as e:
            logger.warning(f"[pool_cache] periodic refresh error: {e}")


def start_background_refresh() -> None:
    """在 FastAPI startup 调用：加载一次 + 启动后台循环。"""
    global _refresh_task

    async def _init():
        await refresh_cache()

    asyncio.create_task(_init())
    if _refresh_task is None or _refresh_task.done():
        _refresh_task = asyncio.create_task(_periodic_refresh_loop())
        logger.info("[pool_cache] background refresh started")


def stop_background_refresh() -> None:
    """在 FastAPI shutdown 调用。"""
    global _refresh_task
    if _refresh_task and not _refresh_task.done():
        _refresh_task.cancel()
        _refresh_task = None
