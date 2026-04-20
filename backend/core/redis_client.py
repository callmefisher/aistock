"""进程级单例同步 Redis 客户端。失败时返回 None，调用方自行降级为"无缓存"模式。

熔断恢复：连接失败后 RETRY_INTERVAL 秒内返回 None 不重试；超期后允许再试一次，
避免 Redis 瞬时抖动导致整个进程生命周期都走无缓存模式。
"""
import logging
import time
from typing import Optional

import redis

from core.config import settings

logger = logging.getLogger(__name__)

RETRY_INTERVAL = 300  # 5 分钟

_client: Optional[redis.Redis] = None
_last_failure_ts: float = 0.0


def get_redis() -> Optional[redis.Redis]:
    """返回单例 Redis 客户端；连接失败返回 None，调用方应容错。

    熔断：5 分钟内连续失败直接返回 None；超过 5 分钟自动尝试重连。
    """
    global _client, _last_failure_ts
    if _client is not None:
        return _client
    now = time.time()
    if _last_failure_ts and (now - _last_failure_ts) < RETRY_INTERVAL:
        return None
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _client = client
        _last_failure_ts = 0.0
        logger.info(f"Redis 连接成功: {settings.REDIS_URL}")
        return _client
    except Exception as e:
        _last_failure_ts = now
        logger.warning(f"Redis 连接失败（{RETRY_INTERVAL}s 内降级为无缓存模式）: {e}")
        return None


def reset_for_tests():
    """仅测试用：清理单例状态。"""
    global _client, _last_failure_ts
    _client = None
    _last_failure_ts = 0.0
