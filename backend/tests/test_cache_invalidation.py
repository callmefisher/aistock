import pytest
import os
import tempfile
import pandas as pd

from services.workflow_executor import (
    _match_source_cache,
    _public_file_cache,
    invalidate_public_cache,
    invalidate_match_source_cache,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """每个测试前后清空缓存"""
    _match_source_cache.clear()
    _public_file_cache.clear()
    yield
    _match_source_cache.clear()
    _public_file_cache.clear()


class TestInvalidatePublicCache:

    def test_clear_specific_dir(self):
        _public_file_cache["/data/public/a.xlsx"] = (1.0, pd.DataFrame())
        _public_file_cache["/data/public/b.xlsx"] = (2.0, pd.DataFrame())
        _public_file_cache["/data/other/c.xlsx"] = (3.0, pd.DataFrame())

        invalidate_public_cache("/data/public")

        assert "/data/public/a.xlsx" not in _public_file_cache
        assert "/data/public/b.xlsx" not in _public_file_cache
        assert "/data/other/c.xlsx" in _public_file_cache

    def test_clear_all(self):
        _public_file_cache["/a.xlsx"] = (1.0, pd.DataFrame())
        _public_file_cache["/b.xlsx"] = (2.0, pd.DataFrame())

        invalidate_public_cache()

        assert len(_public_file_cache) == 0

    def test_clear_empty_cache(self):
        invalidate_public_cache("/nonexistent")
        assert len(_public_file_cache) == 0

    def test_clear_none_on_empty(self):
        invalidate_public_cache(None)
        assert len(_public_file_cache) == 0


class TestInvalidateMatchSourceCache:

    def test_clear_specific_dir(self):
        _match_source_cache["/data/百日新高"] = (1.0, {"002128": "露天煤业"})
        _match_source_cache["/data/20日均线"] = (2.0, {"600519": "贵州茅台"})

        invalidate_match_source_cache("/data/百日新高")

        assert "/data/百日新高" not in _match_source_cache
        assert "/data/20日均线" in _match_source_cache

    def test_clear_all(self):
        _match_source_cache["/a"] = (1.0, {})
        _match_source_cache["/b"] = (2.0, {})

        invalidate_match_source_cache()

        assert len(_match_source_cache) == 0

    def test_clear_empty_cache(self):
        invalidate_match_source_cache("/nonexistent")
        assert len(_match_source_cache) == 0

    def test_startswith_matching(self):
        """确保 startswith 匹配子目录"""
        _match_source_cache["/data/excel/百日新高"] = (1.0, {})
        _match_source_cache["/data/excel/百日新高/sub"] = (2.0, {})
        _match_source_cache["/data/excel/20日均线"] = (3.0, {})

        invalidate_match_source_cache("/data/excel/百日新高")

        assert "/data/excel/百日新高" not in _match_source_cache
        assert "/data/excel/百日新高/sub" not in _match_source_cache
        assert "/data/excel/20日均线" in _match_source_cache
