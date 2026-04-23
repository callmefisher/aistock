"""北京时区工具：专用于生成"今天的 date_str（YYYY-MM-DD）"等日期字符串。

# 为什么单独一个文件
后端容器默认 UTC（docker-compose 未设 TZ）。`datetime.now().strftime('%Y-%m-%d')`
在北京凌晨 0:00-8:00 会返回前一天，导致 merge_excel 目录、`condition_intersection`
输出文件名等落到前一天。

# 不影响 created_at / last_run_time
这些仍由 SQLAlchemy 写入为容器本地时间（UTC），前端 `formatBeijingTime` 把
字符串当 UTC +8 显示回北京时间。不要改容器 TZ，也不要把本模块用到时间戳字段，
否则前端显示会被双重偏移。
"""
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))


def beijing_today_str() -> str:
    """YYYY-MM-DD 格式的北京今日日期。"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
