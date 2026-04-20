"""质押数据源：东方财富 datacenter-web 直连（主） + AkShare（降级） + Redis 缓存。

标准化字段（内部统一）：
  证券代码 / 公告日期 / 股东名称 / 是否控股股东 /
  质押股数 / 占总股本比例 / 累计质押比例 / 前次累计质押比例 / 累计变化 /
  质押开始日期 / 解押日期 / 状态

Key 设计：pledge:detail:{symbol}:{anchor_date}  TTL 7 天
         pledge:source:down = "1"               TTL 30 分钟（东财连续 5 次失败时设）
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REFERER = "https://data.eastmoney.com/gpzy/pledgeDetail.aspx"
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:121.0) Gecko/20100101 Firefox/121.0",
]
CACHE_TTL = 7 * 86400
SOURCE_DOWN_TTL = 30 * 60
MIN_INTERVAL = 1.0
MAX_INTERVAL = 1.8
MAX_CONSECUTIVE_FAILURES = 5


class PledgeDataSource:
    """东财直连 + AkShare 降级 + Redis 缓存。"""

    def __init__(self, redis_client=None, akshare_fallback: bool = True,
                 sleep_fn=time.sleep, time_fn=time.time,
                 http_session=None):
        self.redis = redis_client
        self.akshare_fallback = akshare_fallback
        self._sleep = sleep_fn
        self._time = time_fn
        self.session = http_session or requests.Session()
        self.last_call_ts = 0.0
        self.consecutive_failures = 0

    # ---------- 缓存辅助 ----------

    def _cache_key(self, symbol: str, anchor_date: str) -> str:
        return f"pledge:detail:{symbol}:{anchor_date}"

    def _get_from_cache(self, symbol: str, anchor_date: str):
        if self.redis is None:
            return None
        try:
            raw = self.redis.get(self._cache_key(symbol, anchor_date))
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis 读取失败，降级为无缓存: {e}")
        return None

    def _set_cache(self, symbol: str, anchor_date: str, records: list):
        if self.redis is None:
            return
        try:
            self.redis.setex(
                self._cache_key(symbol, anchor_date),
                CACHE_TTL,
                json.dumps(records, ensure_ascii=False, default=str),
            )
        except Exception as e:
            logger.warning(f"Redis 写入失败: {e}")

    def _is_source_down(self) -> bool:
        if self.redis is None:
            return False
        try:
            return bool(self.redis.get("pledge:source:down"))
        except Exception:
            return False

    def _mark_source_down(self):
        if self.redis is None:
            return
        try:
            self.redis.setex("pledge:source:down", SOURCE_DOWN_TTL, "1")
            logger.warning(f"[PledgeDataSource] 东财连续 {MAX_CONSECUTIVE_FAILURES} 次失败，"
                           f"标记 source:down 冷却 {SOURCE_DOWN_TTL // 60} 分钟")
        except Exception:
            pass

    # ---------- 节流 ----------

    def _throttle(self):
        elapsed = self._time() - self.last_call_ts
        wait = max(MIN_INTERVAL + random.uniform(0.0, MAX_INTERVAL - MIN_INTERVAL) - elapsed, 0)
        if wait > 0:
            self._sleep(wait)

    # ---------- 东财主源 ----------

    def _fetch_eastmoney(self, symbol: str) -> list[dict]:
        """返回东财原始 items；异常上抛。"""
        self._throttle()
        headers = {"User-Agent": random.choice(UA_POOL), "Referer": REFERER}
        params = {
            "sortColumns": "NOTICE_DATE",
            "sortTypes": "-1",
            "pageSize": "500",
            "pageNumber": "1",
            "reportName": "RPTA_APP_ACCUMDETAILS",
            "columns": "ALL",
            "quoteColumns": "",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE="{symbol}")',
        }
        r = self.session.get(URL, params=params, headers=headers, timeout=15)
        self.last_call_ts = self._time()
        r.raise_for_status()
        data = r.json()
        result = data.get("result") or {}
        items = result.get("data") or []
        return items

    def _normalize_eastmoney(self, items: list[dict]) -> list[dict]:
        """东财原始 items → 标准化字段。"""
        norm = []
        for it in items:
            try:
                accum_after = float(it["ACCUM_PLEDGE_TSR"]) if it.get("ACCUM_PLEDGE_TSR") is not None else None
                accum_before = float(it["PRE_ACCUM_PLEDGE_TSR"]) if it.get("PRE_ACCUM_PLEDGE_TSR") is not None else None
                change = (accum_after - accum_before) if (accum_after is not None and accum_before is not None) else None
                notice_date = str(it.get("NOTICE_DATE", ""))[:10]
                norm.append({
                    "证券代码": it.get("SECURITY_CODE", ""),
                    "公告日期": notice_date,
                    "股东名称": it.get("HOLDER_NAME", ""),
                    "是否控股股东": bool(it.get("IS_CONTROL_SHAREHOLDER")),
                    "质押股数": it.get("PF_NUM"),
                    "占总股本比例": it.get("PF_TSR"),
                    "累计质押比例": accum_after,
                    "前次累计质押比例": accum_before,
                    "累计变化": change,
                    "质押开始日期": str(it.get("PF_START_DATE", ""))[:10] if it.get("PF_START_DATE") else None,
                    "解押日期": str(it.get("ACTUAL_UNFREEZE_DATE", ""))[:10] if it.get("ACTUAL_UNFREEZE_DATE") else None,
                    "状态": it.get("UNFREEZE_STATE", ""),
                })
            except Exception as e:
                logger.warning(f"[PledgeDataSource] 东财字段解析失败（跳过 1 条）: {e}")
                continue
        return norm

    # ---------- AkShare 降级 ----------

    def _fetch_akshare(self, symbol: str) -> list[dict]:
        """降级源：akshare.stock_gpzy_pledge_ratio_detail_em()。

        注意：这个接口是全市场快照，速度慢（3+ 分钟）。作为兜底，实际工程中
        应通过个股级 akshare 接口或自行 filter 后缓存。
        """
        import akshare as ak
        df = ak.stock_gpzy_pledge_ratio_detail_em()
        # 过滤本股
        mask = df["股票代码"].astype(str).str.zfill(6) == symbol.zfill(6)
        sub = df[mask]
        norm = []
        for _, row in sub.iterrows():
            try:
                # AkShare 封装没有 累计质押比例/前次累计质押比例 两列，置 None
                # 此时异动判定会返回空 —— 可接受的降级行为
                notice_date = str(row.get("公告日期", ""))[:10]
                norm.append({
                    "证券代码": str(row.get("股票代码", "")).zfill(6),
                    "公告日期": notice_date,
                    "股东名称": row.get("股东名称", ""),
                    "是否控股股东": False,
                    "质押股数": row.get("质押股份数量"),
                    "占总股本比例": row.get("占总股本比例"),
                    "累计质押比例": None,
                    "前次累计质押比例": None,
                    "累计变化": None,
                    "质押开始日期": str(row.get("质押开始日期", ""))[:10] if row.get("质押开始日期") else None,
                    "解押日期": str(row.get("质押结束日期", ""))[:10] if row.get("质押结束日期") else None,
                    "状态": row.get("状态", ""),
                })
            except Exception as e:
                logger.warning(f"[PledgeDataSource] AkShare 字段解析失败（跳过 1 条）: {e}")
                continue
        return norm

    # ---------- 窗口过滤 ----------

    @staticmethod
    def _filter_window(records: list[dict], anchor_date: str, window_days: int) -> list[dict]:
        """保留 [anchor - window_days, anchor] 内的记录；按公告日期升序返回。"""
        try:
            anchor_dt = datetime.strptime(anchor_date[:10], "%Y-%m-%d")
        except Exception:
            return sorted(records, key=lambda r: str(r.get("公告日期", "")))
        start_dt = anchor_dt - timedelta(days=window_days)
        kept = []
        for r in records:
            try:
                d = datetime.strptime(str(r.get("公告日期", ""))[:10], "%Y-%m-%d")
            except Exception:
                continue
            if start_dt <= d <= anchor_dt:
                kept.append(r)
        kept.sort(key=lambda r: r["公告日期"])
        return kept

    # ---------- 对外入口 ----------

    def get_history(self, symbol: str, anchor_date: str,
                    window_days: int = 365) -> tuple[list[dict], str]:
        """返回 (records 升序, source_name ∈ {eastmoney, cache, akshare, empty})。"""
        # 1. 缓存
        cached = self._get_from_cache(symbol, anchor_date)
        if cached is not None:
            filtered = self._filter_window(cached, anchor_date, window_days)
            return filtered, "cache"

        # 2. source_down 时直接走降级
        if self._is_source_down():
            if self.akshare_fallback:
                try:
                    records = self._fetch_akshare(symbol)
                    filtered = self._filter_window(records, anchor_date, window_days)
                    self._set_cache(symbol, anchor_date, records)
                    return filtered, "akshare"
                except Exception as e:
                    logger.warning(f"[PledgeDataSource] AkShare 降级失败: {e}")
            return [], "empty"

        # 3. 东财主源
        try:
            items = self._fetch_eastmoney(symbol)
            records = self._normalize_eastmoney(items)
            self.consecutive_failures = 0
            self._set_cache(symbol, anchor_date, records)
            filtered = self._filter_window(records, anchor_date, window_days)
            return filtered, "eastmoney"
        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(f"[PledgeDataSource] 东财拉取失败 ({self.consecutive_failures}/"
                           f"{MAX_CONSECUTIVE_FAILURES}): {e}")
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                self._mark_source_down()

        # 4. 降级 AkShare
        if self.akshare_fallback:
            try:
                records = self._fetch_akshare(symbol)
                self._set_cache(symbol, anchor_date, records)
                filtered = self._filter_window(records, anchor_date, window_days)
                return filtered, "akshare"
            except Exception as e:
                logger.warning(f"[PledgeDataSource] AkShare 降级失败: {e}")

        return [], "empty"
