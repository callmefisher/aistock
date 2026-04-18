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
    db = _parse_db_url(settings.DATABASE_URL_SYNC)
    date_str = datetime.now().strftime("%Y-%m-%d")
    sql_path = tempfile.mktemp(suffix=".sql")

    result = subprocess.run(
        [
            "mysqldump",
            f"--host={db['host']}",
            f"--port={db['port']}",
            f"--user={db['user']}",
            f"--password={db['password']}",
            db["database"],
        ],
        capture_output=True,
        timeout=300,
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
    if not (file.filename or "").endswith(".sql"):
        raise HTTPException(status_code=400, detail="仅接受 .sql 文件")

    db = _parse_db_url(settings.DATABASE_URL_SYNC)
    sql_path = tempfile.mktemp(suffix=".sql")

    try:
        with open(sql_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)

        with open(sql_path, "rb") as f:
            result = subprocess.run(
                [
                    "mysql",
                    f"--host={db['host']}",
                    f"--port={db['port']}",
                    f"--user={db['user']}",
                    f"--password={db['password']}",
                    db["database"],
                ],
                stdin=f,
                capture_output=True,
                timeout=300,
            )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"数据库恢复失败: {result.stderr.decode(errors='replace')}",
            )

        return {"success": True, "message": "数据库恢复成功"}

    finally:
        if os.path.exists(sql_path):
            os.unlink(sql_path)
