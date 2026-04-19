from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from core.config import settings
from core.database import async_engine, Base
from api import auth, data_sources, rules, tasks, stock_pools, workflows, statistics_api, trend_api, database_backup
from services.task_scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

scheduler = TaskScheduler(settings.DATABASE_URL_SYNC)


async def seed_default_admin_if_empty(session) -> bool:
    """users 表为空时创建默认 admin/admin123 superuser。返回是否实际创建。"""
    from models.models import User
    from sqlalchemy import select, func as sqlfunc
    from api.auth import get_password_hash

    total = (await session.execute(select(sqlfunc.count(User.id)))).scalar() or 0
    if total > 0:
        return False

    session.add(User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        is_active=True,
        is_superuser=True,
    ))
    await session.commit()
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在启动应用...")
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    from sqlalchemy import text
    from core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT COUNT(*)
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'workflows'
                AND COLUMN_NAME = 'workflow_type'
            """))
            count = result.scalar()
            if count == 0:
                await session.execute(text("""
                    ALTER TABLE workflows
                    ADD COLUMN workflow_type VARCHAR(50) DEFAULT ''
                    COMMENT '工作流类型'
                    AFTER description
                """))
                await session.commit()
                logger.info("已自动添加 workflow_type 字段")
            else:
                logger.info("workflow_type 字段已存在")
    except Exception as e:
        logger.warning(f"数据库迁移检查: {e}")

    # 空库 seed：users 表为空时自动创建 admin/admin123 作为 superuser
    # 场景：全新部署，避免用户面对空登录页不知道怎么进去
    # 注意：只在 "一条记录都没有" 时触发；导入备份（即使 admin 密码未知）不处理
    try:
        async with AsyncSessionLocal() as session:
            created = await seed_default_admin_if_empty(session)
            if created:
                logger.warning(
                    "空库 seed：已创建默认管理员 admin / admin123 (superuser)。"
                    "请首次登录后立即修改密码。"
                )
    except Exception as e:
        logger.warning(f"空库 seed 检查失败: {e}")

    # 自愈：若库里没有 superuser，把最早注册的用户提升为 superuser
    # 场景：老用户在 superuser 检查加入前注册，升级后没人能访问需要管理员权限的功能
    try:
        async with AsyncSessionLocal() as session:
            from models.models import User
            from sqlalchemy import select, func as sqlfunc
            count_row = await session.execute(
                select(sqlfunc.count(User.id)).where(User.is_superuser == True)
            )
            if (count_row.scalar() or 0) == 0:
                oldest = await session.execute(
                    select(User).order_by(User.id.asc()).limit(1)
                )
                first_user = oldest.scalar_one_or_none()
                if first_user is not None:
                    first_user.is_superuser = True
                    await session.commit()
                    logger.info(f"无 superuser：已自动提升用户 '{first_user.username}' 为管理员")
    except Exception as e:
        logger.warning(f"superuser 自愈检查失败: {e}")

    from service.scheduler_service import scheduler_service
    await scheduler_service.start()
    
    scheduler.start()
    logger.info("数据库表创建完成，调度器已启动")
    
    yield
    
    logger.info("正在关闭应用...")
    await scheduler_service.stop()
    scheduler.shutdown()
    logger.info("应用已关闭")


logger.info("选股池自动化系统启动中...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="自动化股票筛选和数据分析系统",
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["认证"])
app.include_router(data_sources.router, prefix=f"{settings.API_PREFIX}/data-sources", tags=["数据源"])
app.include_router(rules.router, prefix=f"{settings.API_PREFIX}/rules", tags=["规则"])
app.include_router(tasks.router, prefix=f"{settings.API_PREFIX}/tasks", tags=["任务"])
app.include_router(stock_pools.router, prefix=f"{settings.API_PREFIX}/stock-pools", tags=["选股池"])
app.include_router(workflows.router, prefix=f"{settings.API_PREFIX}/workflows", tags=["工作流"])
app.include_router(statistics_api.router, prefix=f"{settings.API_PREFIX}/statistics", tags=["统计分析"])
app.include_router(trend_api.router, prefix=f"{settings.API_PREFIX}/statistics/trend", tags=["趋势统计"])
app.include_router(database_backup.router, prefix=f"{settings.API_PREFIX}/database", tags=["数据库备份"])


@app.get("/")
async def root():
    return {
        "message": f"欢迎使用{settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误",
            "error": str(exc)
        }
    )
