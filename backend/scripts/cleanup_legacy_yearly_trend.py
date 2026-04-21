"""一次性清理脚本：删除 metric_type='ma20' 且 workflow_type 为
'并购重组' / '股权转让' / '招投标' 无年份后缀的老记录。

这些类型改为按 最新公告日 所在年份拆为 `{类型}(YYYY)` 双线存储，
老的无后缀记录口径不同（全表统计），保留会导致图表跨迁移日阶跃。

幂等可重复执行。
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, bindparam  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402


TARGET_TYPES = ["并购重组", "股权转让", "招投标"]


async def main():
    async with AsyncSessionLocal() as session:
        stmt = text(
            "DELETE FROM trend_statistics "
            "WHERE metric_type = 'ma20' AND workflow_type IN :types"
        ).bindparams(bindparam("types", expanding=True))
        result = await session.execute(stmt, {"types": TARGET_TYPES})
        await session.commit()
        deleted = result.rowcount if hasattr(result, "rowcount") else -1
        print(f"Deleted {deleted} legacy ma20 records (types={TARGET_TYPES})")


if __name__ == "__main__":
    asyncio.run(main())
