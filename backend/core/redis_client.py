"""进程级单例同步 Redis 客户端。失败时返回 None，调用方自行降级为"无缓存"模式。"""
import logging
from typing import Optional

import redis

from core.config import settings

logger = logging.getLogger(__name__)

_client: Optional[redis.Redis] = None
_connect_failed = False


def get_redis() -> Optional[redis.Redis]:
    """返回单例 Redis 客户端；连接失败返回 None，调用方应容错。"""
    global _client, _connect_failed
    if _connect_failed:
        return None
    if _client is not None:
        return _client
    try:
        _client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _client.ping()
        logger.info(f"Redis 连接成功: {settings.REDIS_URL}")
        return _client
    except Exception as e:
        logger.warning(f"Redis 连接失败（将降级为无缓存模式）: {e}")
        _connect_failed = True
        _client = None
        return None


def reset_for_tests():
    """仅测试用：清理单例状态。"""
    global _client, _connect_failed
    _client = None
    _connect_failed = False
