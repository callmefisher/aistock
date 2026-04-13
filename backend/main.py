from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from core.config import settings
from core.database import async_engine, Base
from api import auth, data_sources, rules, tasks, stock_pools, workflows, data_api
from services.task_scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

scheduler = TaskScheduler(settings.DATABASE_URL_SYNC)


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
app.include_router(data_api.router, prefix=f"{settings.API_PREFIX}/data", tags=["金融数据"])


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
