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

        # 用 asyncio 原生 subprocess：避免 run_in_executor+subprocess.run(input=...)
        # 在 uvicorn 线程池里 stdin 不能正确关闭导致 mysql CLI 卡住等 EOF（实测 300s 超时）
        with open(sql_path, "rb") as f_in:
            sql_bytes = f_in.read()

        proc = await asyncio.create_subprocess_exec(
            "mysql",
            f"--host={db['host']}",
            f"--port={db['port']}",
            f"--user={db['user']}",
            db["database"],
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "MYSQL_PWD": db["password"]},
        )
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(input=sql_bytes), timeout=300
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise HTTPException(status_code=504, detail="数据库恢复超时（300 秒）")

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"数据库恢复失败: {stderr_data.decode(errors='replace')}",
            )

        return {"success": True, "message": "数据库恢复成功"}

    finally:
        if os.path.exists(sql_path):
            os.unlink(sql_path)
