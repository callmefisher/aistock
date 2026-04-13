"""
数据库迁移脚本：添加 workflow_type 字段到 workflows 表

执行方法：
    python scripts/migrate_add_workflow_type.py

说明：
    - 支持工作流类型系统
    - 允许不同类型的工作流使用不同的目录和命名规则
    - 向后兼容：默认值为空字符串，表示使用默认流程
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import engine, AsyncSessionLocal
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_column_exists():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'workflows'
            AND COLUMN_NAME = 'workflow_type'
        """))
        count = result.scalar()
        return count > 0


async def add_workflow_type_column():
    exists = await check_column_exists()

    if exists:
        logger.info("✓ workflow_type 字段已存在，跳过迁移")
        return

    logger.info("开始添加 workflow_type 字段...")

    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("""
                ALTER TABLE workflows
                ADD COLUMN workflow_type VARCHAR(50) DEFAULT ''
                COMMENT '工作流类型: 空/并购重组/股权转让/...'
                AFTER description
            """))
            await session.commit()
            logger.info("✓ 成功添加 workflow_type 字段")

            result = await session.execute(text("""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'workflows'
                AND COLUMN_NAME = 'workflow_type'
            """))
            row = result.fetchone()
            if row:
                logger.info(f"字段信息: {row}")

        except Exception as e:
            logger.error(f"✗ 迁移失败: {e}")
            await session.rollback()
            raise


async def verify_migration():
    logger.info("\n验证迁移结果...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'workflows'
            AND COLUMN_NAME = 'workflow_type'
        """))
        row = result.fetchone()

        if row:
            logger.info("✓ 迁移验证成功")
            logger.info(f"  字段名: {row[0]}")
            logger.info(f"  类型: {row[1]}")
            logger.info(f"  允许空: {row[2]}")
            logger.info(f"  默认值: {row[3]}")
            logger.info(f"  注释: {row[4]}")
            return True
        else:
            logger.error("✗ 迁移验证失败：字段不存在")
            return False


async def main():
    logger.info("=" * 60)
    logger.info("工作流类型系统 - 数据库迁移")
    logger.info("=" * 60)

    try:
        await add_workflow_type_column()
        success = await verify_migration()

        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 迁移完成！")
            logger.info("=" * 60)
            logger.info("\n可用的工作流类型：")
            logger.info("  - 空字符串或'并购重组': 默认流程")
            logger.info("  - '股权转让': 股权转让流程")
            logger.info("\n下一步：")
            logger.info("  1. 重启后端服务")
            logger.info("  2. 在前端UI中创建/编辑工作流时选择类型")
            logger.info("  3. 调用 GET /api/workflows/types/ 获取可用类型列表")
        else:
            sys.exit(1)

    except Exception as e:
        logger.error(f"\n✗ 迁移过程出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
