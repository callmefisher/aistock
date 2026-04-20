"""阶段3 - Redis 缓存清理测试。"""
from datetime import datetime, timedelta

import fakeredis
import pytest

from services.pledge_cache_cleanup import cleanup_expired_pledge_cache


@pytest.fixture
def rd():
    return fakeredis.FakeRedis(decode_responses=True)


def test_deletes_keys_older_than_cutoff(rd):
    """anchor 早于 cutoff 的 key 被删除；之后的保留。"""
    old_anchor = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    new_anchor = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    rd.setex(f"pledge:detail:002768:{old_anchor}", 999999, "[]")
    rd.setex(f"pledge:detail:002768:{new_anchor}", 999999, "[]")
    rd.setex(f"pledge:detail:000001:{old_anchor}", 999999, "[]")

    deleted = cleanup_expired_pledge_cache(rd, max_age_days=370)
    assert deleted == 2
    assert rd.exists(f"pledge:detail:002768:{old_anchor}") == 0
    assert rd.exists(f"pledge:detail:002768:{new_anchor}") == 1
    assert rd.exists(f"pledge:detail:000001:{old_anchor}") == 0


def test_keeps_keys_within_window(rd):
    """边界：正好 max_age_days-1 天的 key 不删。"""
    within = (datetime.now() - timedelta(days=369)).strftime("%Y-%m-%d")
    rd.setex(f"pledge:detail:002768:{within}", 999999, "[]")
    deleted = cleanup_expired_pledge_cache(rd, max_age_days=370)
    assert deleted == 0
    assert rd.exists(f"pledge:detail:002768:{within}") == 1


def test_scan_handles_many_keys(rd):
    """200+ key 的场景：SCAN 分批正常处理。"""
    old_anchor = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    for i in range(250):
        rd.setex(f"pledge:detail:sym{i:04d}:{old_anchor}", 999999, "[]")
    deleted = cleanup_expired_pledge_cache(rd, max_age_days=370)
    assert deleted == 250


def test_empty_redis_no_error(rd):
    """Redis 为空不报错。"""
    assert cleanup_expired_pledge_cache(rd, max_age_days=370) == 0


def test_redis_none_returns_zero():
    """redis_client 为 None 时静默返回 0。"""
    assert cleanup_expired_pledge_cache(None) == 0


def test_unrelated_keys_not_touched(rd):
    """其他命名空间的 key 不被误删。"""
    old_anchor = (datetime.now() - timedelta(days=500)).strftime("%Y-%m-%d")
    rd.setex(f"other:namespace:foo", 999999, "bar")
    rd.setex(f"pledge:source:down", 999999, "1")
    rd.setex(f"pledge:detail:002768:{old_anchor}", 999999, "[]")
    deleted = cleanup_expired_pledge_cache(rd, max_age_days=370)
    assert deleted == 1
    assert rd.exists("other:namespace:foo") == 1
    assert rd.exists("pledge:source:down") == 1
