"""质押缓存清理：删除锚点日期早于 cutoff 的 pledge:detail:* key。

工作在 Redis SCAN 上，不会阻塞 server；按照锚点日期（key 的最后一段）做字典序比较。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_expired_pledge_cache(redis_client, max_age_days: int = 370) -> int:
    """删除 pledge:detail:{symbol}:{anchor_date} 中 anchor_date 早于
    now - max_age_days 的 key。返回已删除数量。

    redis_client 为 None 或调用异常时：返回 0（不抛）。
    """
    if redis_client is None:
        return 0

    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")
    deleted = 0
    try:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="pledge:detail:*", count=500)
            for key in keys:
                k = key.decode() if isinstance(key, (bytes, bytearray)) else key
                parts = k.rsplit(":", 1)
                if len(parts) == 2:
                    anchor = parts[1]
                    if len(anchor) == 10 and anchor < cutoff:
                        redis_client.delete(key)
                        deleted += 1
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"[质押缓存清理] 执行失败（不影响主流程）: {e}")
        return deleted
    logger.info(f"[质押缓存清理] cutoff={cutoff}, 已删除 {deleted} 个 key")
    return deleted
