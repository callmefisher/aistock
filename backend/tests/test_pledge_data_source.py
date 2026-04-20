"""阶段3 - PledgeDataSource 测试（mock HTTP + fakeredis）。"""
import json
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
import requests

from services.pledge_data_source import (
    MAX_CONSECUTIVE_FAILURES, PledgeDataSource,
)


def _mock_eastmoney_response(items: list[dict], total: int = None):
    m = MagicMock()
    m.status_code = 200
    m.raise_for_status = MagicMock()
    m.json.return_value = {
        "result": {"data": items, "count": total if total is not None else len(items)}
    }
    return m


def _fake_east_item(notice_date, accum_after, accum_before, pf_num=100000):
    return {
        "SECURITY_CODE": "002768",
        "NOTICE_DATE": notice_date + " 00:00:00",
        "HOLDER_NAME": "王爱国",
        "IS_CONTROL_SHAREHOLDER": True,
        "PF_NUM": pf_num,
        "PF_TSR": 1.43,
        "ACCUM_PLEDGE_TSR": accum_after,
        "PRE_ACCUM_PLEDGE_TSR": accum_before,
        "PF_START_DATE": None,
        "ACTUAL_UNFREEZE_DATE": None,
        "UNFREEZE_STATE": "未解押",
    }


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def ds_no_sleep(fake_redis):
    session = MagicMock()
    ds = PledgeDataSource(
        redis_client=fake_redis,
        akshare_fallback=False,
        sleep_fn=lambda s: None,
        time_fn=lambda: 0.0,
        http_session=session,
    )
    return ds, session, fake_redis


def test_eastmoney_success_normalizes(ds_no_sleep):
    """东财成功 → 标准化字段 + 升序。"""
    ds, session, _ = ds_no_sleep
    session.get.return_value = _mock_eastmoney_response([
        _fake_east_item("2026-04-14", 8.14, 9.78),
        _fake_east_item("2025-08-30", 13.73, 17.74),
    ])
    records, source = ds.get_history("002768", "2026-04-20", window_days=365)
    assert source == "eastmoney"
    # 升序返回
    assert [r["公告日期"] for r in records] == ["2025-08-30", "2026-04-14"]
    assert records[0]["累计质押比例"] == 13.73
    assert records[0]["前次累计质押比例"] == 17.74
    assert records[1]["累计变化"] == pytest.approx(8.14 - 9.78)
    assert records[0]["证券代码"] == "002768"
    assert records[0]["股东名称"] == "王爱国"


def test_cache_hit_second_call(ds_no_sleep):
    """第二次同 (symbol, anchor) 调用 → 命中缓存，不再打 HTTP。"""
    ds, session, _ = ds_no_sleep
    session.get.return_value = _mock_eastmoney_response([
        _fake_east_item("2026-04-14", 8.14, 9.78)
    ])
    _, src1 = ds.get_history("002768", "2026-04-20")
    _, src2 = ds.get_history("002768", "2026-04-20")
    assert src1 == "eastmoney"
    assert src2 == "cache"
    assert session.get.call_count == 1


def test_eastmoney_4xx_falls_to_empty(ds_no_sleep):
    """东财 4xx / 超时 且无降级 → empty。"""
    ds, session, _ = ds_no_sleep
    ds.akshare_fallback = False
    err = MagicMock()
    err.raise_for_status.side_effect = requests.HTTPError("404")
    session.get.return_value = err
    records, source = ds.get_history("000000", "2026-04-20")
    assert source == "empty"
    assert records == []


def test_consecutive_failures_trigger_source_down(ds_no_sleep):
    """连续 MAX_CONSECUTIVE_FAILURES 次失败 → 设 source:down。"""
    ds, session, redis = ds_no_sleep
    err = MagicMock()
    err.raise_for_status.side_effect = requests.ConnectionError("net down")
    session.get.return_value = err
    for _ in range(MAX_CONSECUTIVE_FAILURES):
        ds.get_history(f"00{_:04d}", "2026-04-20")
    assert redis.get("pledge:source:down") == "1"


def test_source_down_skips_eastmoney(ds_no_sleep):
    """source:down 已标记 → 不再调用 HTTP 直接走降级（此处 akshare_fallback=False → empty）。"""
    ds, session, redis = ds_no_sleep
    redis.setex("pledge:source:down", 60, "1")
    records, source = ds.get_history("002768", "2026-04-20")
    assert source == "empty"
    session.get.assert_not_called()


def test_window_filter_respects_anchor_minus_365(ds_no_sleep):
    """1 年窗口过滤：超出 [anchor-365, anchor] 的记录被剔除。"""
    ds, session, _ = ds_no_sleep
    session.get.return_value = _mock_eastmoney_response([
        _fake_east_item("2018-01-01", 5.0, 6.0),  # 超范围
        _fake_east_item("2025-10-01", 10.0, 11.0),  # 在 2025-04-20~2026-04-20 内
        _fake_east_item("2027-01-01", 99.0, 98.0),  # 未来（超范围）
    ])
    records, _ = ds.get_history("002768", "2026-04-20", window_days=365)
    assert [r["公告日期"] for r in records] == ["2025-10-01"]


def test_akshare_fallback_used_after_eastmoney_fail(ds_no_sleep):
    """东财失败 + akshare_fallback=True → 走 AkShare 路径。"""
    ds, session, _ = ds_no_sleep
    ds.akshare_fallback = True
    err = MagicMock()
    err.raise_for_status.side_effect = requests.HTTPError("500")
    session.get.return_value = err

    # mock akshare
    import pandas as pd
    fake_df = pd.DataFrame([{
        "股票代码": "002768",
        "股票简称": "国恩股份",
        "股东名称": "王爱国",
        "质押股份数量": 4300000,
        "占总股本比例": 1.43,
        "质押开始日期": "2026-04-09",
        "质押结束日期": None,
        "状态": "未解押",
        "公告日期": "2026-04-14",
    }])
    with patch("akshare.stock_gpzy_pledge_ratio_detail_em", return_value=fake_df):
        records, source = ds.get_history("002768", "2026-04-20")
    assert source == "akshare"
    assert len(records) == 1
    assert records[0]["累计质押比例"] is None  # AkShare 封装没有此字段


def test_ua_rotation(ds_no_sleep):
    """每次请求的 UA 来自 UA_POOL。"""
    ds, session, _ = ds_no_sleep
    session.get.return_value = _mock_eastmoney_response([])
    ds.get_history("002768", "2026-04-20")
    _, kwargs = session.get.call_args
    ua = kwargs["headers"]["User-Agent"]
    from services.pledge_data_source import UA_POOL
    assert ua in UA_POOL
    assert kwargs["headers"]["Referer"] == "https://data.eastmoney.com/gpzy/pledgeDetail.aspx"
