"""板块信号榜配置（权重/窗口/阈值）。

支持通过环境变量覆盖，便于调参：
- SECTOR_SIGNAL_WINDOW_RECENT, SECTOR_SIGNAL_WINDOW_LONG
- SECTOR_SIGNAL_TOP_THRESHOLD, SECTOR_SIGNAL_MIN_RECENT_VALID, SECTOR_SIGNAL_MIN_LONG_VALID
"""
import os

WEIGHTS_STRONG = {
    "long_rank": 0.35,
    "recent_rank": 0.25,
    "mtd": 0.20,
    "ytd": 0.10,
    "stability": 0.10,
}

WEIGHTS_REVERSAL = {
    "reversal": 0.40,
    "recent_rank": 0.30,
    "ytd_low": 0.20,
    "mtd": 0.10,
}

WINDOW_RECENT = int(os.getenv("SECTOR_SIGNAL_WINDOW_RECENT", "5"))
WINDOW_LONG = int(os.getenv("SECTOR_SIGNAL_WINDOW_LONG", "20"))
TOP_THRESHOLD = int(os.getenv("SECTOR_SIGNAL_TOP_THRESHOLD", "20"))
MIN_RECENT_VALID = int(os.getenv("SECTOR_SIGNAL_MIN_RECENT_VALID", "3"))
MIN_LONG_VALID = int(os.getenv("SECTOR_SIGNAL_MIN_LONG_VALID", "10"))

TOP_N_CHOICES = {10, 20, 30}
TOP_N_DEFAULT = 20
TOP_N_STORE = 30  # DB 预存 Top 30，前端本地切片


def snapshot() -> dict:
    """返回当前生效的配置快照，写入 DB 的 config_snapshot 字段。"""
    return {
        "weights_strong": dict(WEIGHTS_STRONG),
        "weights_reversal": dict(WEIGHTS_REVERSAL),
        "window_recent": WINDOW_RECENT,
        "window_long": WINDOW_LONG,
        "top_threshold": TOP_THRESHOLD,
        "min_recent_valid": MIN_RECENT_VALID,
        "min_long_valid": MIN_LONG_VALID,
    }
