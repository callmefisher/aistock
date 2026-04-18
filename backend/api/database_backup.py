import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from urllib.parse import urlparse, unquote
import subprocess
import tempfile
import os
import logging
from datetime import datetime

from core.config import settings
from core.database import async_engine, sync_engine
from api.auth import get_current_user
from models.models import User

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_IMPORT_SIZE = 500 * 1024 * 1024  # 500 MB


def _parse_db_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "mysql",
        "port": str(parsed.port or 3306),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/"),
    }


@router.get("/export")
async def export_database(current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    db = _parse_db_url(settings.DATABASE_URL_SYNC)
    date_str = datetime.now().strftime("%Y-%m-%d")

    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        sql_path = tmp.name

    # --hex-blob: 把 BLOB/BINARY 列编码成十六进制字符串 (0xAABBCC)，
    #   避免导出文件含二进制字节（workflow_results.data_compressed 是 zlib 压缩的 LONGBLOB），
    #   否则 mysql/mariadb client 读 stdin 恢复时会卡在某些字节上
    # --single-transaction: InnoDB 下获取一致快照而不锁表
    # --routines --events --triggers: 导出存储过程/事件/触发器
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: subprocess.run(
            [
                "mysqldump",
                "--hex-blob",
                "--single-transaction",
                "--routines",
                "--events",
                "--triggers",
                f"--host={db['host']}",
                f"--port={db['port']}",
                f"--user={db['user']}",
                db["database"],
            ],
            capture_output=True,
            timeout=300,
            env={**os.environ, "MYSQL_PWD": db["password"]},
        )
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"mysqldump 执行失败: {result.stderr.decode(errors='replace')}",
        )

    with open(sql_path, "wb") as f:
        f.write(result.stdout)

    return FileResponse(
        sql_path,
        filename=f"aistock_backup_{date_str}.sql",
        media_type="application/octet-stream",
        background=BackgroundTask(os.unlink, sql_path),
    )


@router.post("/import")
async def import_database(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")

    if not (file.filename or "").endswith(".sql"):
        raise HTTPException(status_code=400, detail="仅接受 .sql 文件")

    # 校验 SQL 文件头部：接受常见 SQL 起始格式
    #   --   行注释（mysqldump 传统格式）
    #   /*   块注释（现代 mysqldump 的 /*M!999999...*/ sandbox 头）
    #   SET/USE/CREATE/INSERT/DROP   直接 DDL/DML
    header = await file.read(128)
    await file.seek(0)
    stripped = header.lstrip()
    valid_prefixes = (b"--", b"/*", b"SET ", b"USE ", b"CREATE", b"INSERT", b"DROP", b"ALTER")
    if not any(stripped.upper().startswith(p.upper()) if p[0:1].isalpha() else stripped.startswith(p) for p in valid_prefixes):
        raise HTTPException(status_code=400, detail="文件内容不符合 SQL 格式")

    db = _parse_db_url(settings.DATABASE_URL_SYNC)

    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
        sql_path = tmp.name

    try:
        total = 0
        with open(sql_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IMPORT_SIZE:
                    raise HTTPException(status_code=413, detail="文件过大，最大支持 500MB")
                f.write(chunk)

        # 关键：mysql import 要执行 DROP/CREATE TABLE，凡是此时对这些表还「持有过事务」的
        # 连接都会让 DDL 卡在 metadata lock（处于 Sleep 的连接也算，MySQL 以 trx 为界释放锁）。
        # FastAPI 这次请求本身已经通过 get_current_user 开过 session 查 users 表，
        # 加上 pool_size=10 连接池还有别的空闲连接 → mysql 会永久等锁。
        #
        # 做法：用一个独立的 pymysql 连接查 information_schema.processlist，
        # KILL 掉所有同用户的其他连接。这些连接被 KILL 后，SQLAlchemy 下次用到时
        # pool_pre_ping=True 会自动重建，对业务无感。
        #
        # 注意：必须是「新连接」去 KILL，不能复用 SQLAlchemy 的池（池里的连接就是我们要杀的目标）。
        import pymysql
        kill_conn = pymysql.connect(
            host=db["host"],
            port=int(db["port"]),
            user=db["user"],
            password=db["password"],
            database=db["database"],
            connect_timeout=5,
        )
        try:
            with kill_conn.cursor() as cur:
                cur.execute("SELECT CONNECTION_ID()")
                my_id = cur.fetchone()[0]
                cur.execute(
                    "SELECT id FROM information_schema.processlist "
                    "WHERE user=%s AND id <> %s",
                    (db["user"], my_id),
                )
                victims = [row[0] for row in cur.fetchall()]
                for vid in victims:
                    try:
                        cur.execute(f"KILL {int(vid)}")
                    except Exception as e:
                        logger.warning("KILL %s failed: %s", vid, e)
            logger.info("killed %d stock_user connections before import: %s", len(victims), victims)
        finally:
            kill_conn.close()

        # 顺手 dispose 一下，让池里那些已被 server 侧 KILL 的 socket 被回收。
        await async_engine.dispose()
        sync_engine.dispose()

        import shlex
        cmd_str = " ".join([
            "mysql",
            f"--host={shlex.quote(db['host'])}",
            f"--port={shlex.quote(str(db['port']))}",
            f"--user={shlex.quote(db['user'])}",
            shlex.quote(db["database"]),
            "<",
            shlex.quote(sql_path),
        ])
        proc = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MYSQL_PWD": db["password"]},
        )
        try:
            _, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(status_code=504, detail="数据库恢复超时（300 秒）")

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"数据库恢复失败: {stderr_data.decode(errors='replace')}",
            )

        # 导入成功后再 dispose 一次：restore 中 DROP/CREATE 会让连接 ping 失败，
        # 提前清掉避免下一次请求拿到坏连接。
        await async_engine.dispose()
        sync_engine.dispose()

        return {"success": True, "message": "数据库恢复成功"}

    finally:
        if os.path.exists(sql_path):
            os.unlink(sql_path)
