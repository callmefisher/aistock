import zlib
import json
import os
import logging
import pandas as pd
from typing import Optional, Dict, Any
from sqlalchemy import text
from core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def save_workflow_result(
    workflow_id: int,
    workflow_type: str,
    workflow_name: str,
    date_str: str,
    file_path: str,
    step_type: str = "final"
) -> bool:
    """读取最终 Excel，压缩为 JSON 写入 DB。"""
    try:
        df = pd.read_excel(file_path)
        df = df.fillna('')
        records = df.to_dict('records')

        full_json = json.dumps(records, ensure_ascii=False, default=str)
        compressed = zlib.compress(full_json.encode('utf-8'), level=6)

        preview = records[:50]
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        source_filename = os.path.basename(file_path)

        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                INSERT INTO workflow_results
                (workflow_id, workflow_type, workflow_name, date_str, step_type,
                 row_count, columns_json, data_compressed, preview_json, file_size, source_filename, created_at)
                VALUES
                (:workflow_id, :workflow_type, :workflow_name, :date_str, :step_type,
                 :row_count, :columns_json, :data_compressed, :preview_json, :file_size, :source_filename, NOW())
                AS new_row
                ON DUPLICATE KEY UPDATE
                workflow_name = new_row.workflow_name,
                row_count = new_row.row_count,
                columns_json = new_row.columns_json,
                data_compressed = new_row.data_compressed,
                preview_json = new_row.preview_json,
                file_size = new_row.file_size,
                source_filename = new_row.source_filename,
                created_at = new_row.created_at
            """), {
                'workflow_id': workflow_id,
                'workflow_type': workflow_type or '',
                'workflow_name': workflow_name,
                'date_str': date_str,
                'step_type': step_type,
                'row_count': len(df),
                'columns_json': json.dumps(df.columns.tolist(), ensure_ascii=False),
                'data_compressed': compressed,
                'preview_json': json.dumps(preview, ensure_ascii=False, default=str),
                'file_size': file_size,
                'source_filename': source_filename,
            })
            await session.commit()

        logger.info(f"工作流结果已保存到DB: workflow_id={workflow_id}, rows={len(df)}, compressed={len(compressed)}bytes")
        return True
    except Exception as e:
        logger.error(f"保存工作流结果失败: {e}")
        return False


async def get_results_grouped() -> Dict[str, Any]:
    """按 workflow_type 分组，再按 date_str 降序返回。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT id, workflow_id, workflow_type, workflow_name, date_str,
                   step_type, row_count, columns_json, file_size, source_filename,
                   CONVERT_TZ(created_at, '+00:00', '+08:00') as created_at
            FROM workflow_results
            ORDER BY workflow_type, date_str DESC, created_at DESC
        """))
        rows = result.fetchall()

    grouped = {}
    for row in rows:
        wtype = row[2] or '并购重组'
        if wtype not in grouped:
            grouped[wtype] = []
        grouped[wtype].append({
            'id': row[0],
            'workflow_id': row[1],
            'workflow_type': row[2],
            'workflow_name': row[3],
            'date_str': row[4],
            'step_type': row[5],
            'row_count': row[6],
            'columns': json.loads(row[7]) if row[7] else [],
            'file_size': row[8],
            'source_filename': row[9] or '',
            'created_at': row[10].isoformat() if row[10] else None,
        })
    return grouped


async def get_result_preview(result_id: int) -> Optional[Dict]:
    """返回预览数据（前50行，未压缩）。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT id, workflow_type, workflow_name, date_str, row_count,
                   columns_json, preview_json, source_filename,
                   CONVERT_TZ(created_at, '+00:00', '+08:00') as created_at
            FROM workflow_results WHERE id = :id
        """), {'id': result_id})
        row = result.fetchone()
        if not row:
            return None

    return {
        'id': row[0],
        'workflow_type': row[1],
        'workflow_name': row[2],
        'date_str': row[3],
        'row_count': row[4],
        'columns': json.loads(row[5]) if row[5] else [],
        'data': json.loads(row[6]) if row[6] else [],
        'source_filename': row[7] or '',
        'created_at': row[8].isoformat() if row[8] else None,
    }


async def get_result_full(result_id: int) -> Optional[Dict]:
    """返回完整解压数据。"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT id, workflow_type, workflow_name, date_str, row_count,
                   columns_json, data_compressed, source_filename,
                   CONVERT_TZ(created_at, '+00:00', '+08:00') as created_at
            FROM workflow_results WHERE id = :id
        """), {'id': result_id})
        row = result.fetchone()
        if not row:
            return None

    data = []
    if row[6]:
        decompressed = zlib.decompress(row[6])
        data = json.loads(decompressed.decode('utf-8'))

    return {
        'id': row[0],
        'workflow_type': row[1],
        'workflow_name': row[2],
        'date_str': row[3],
        'row_count': row[4],
        'columns': json.loads(row[5]) if row[5] else [],
        'data': data,
        'source_filename': row[7] or '',
        'created_at': row[8].isoformat() if row[8] else None,
    }


async def delete_result(result_id: int) -> bool:
    """删除指定结果。"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text(
                "DELETE FROM workflow_results WHERE id = :id"
            ), {'id': result_id})
            await session.commit()
        return True
    except Exception as e:
        logger.error(f"删除结果失败: {e}")
        return False


async def get_available_types_for_date(date_str: str) -> dict:
    """查询指定日期哪些工作流类型有 final 结果"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT DISTINCT
                CASE WHEN workflow_type = '' THEN '并购重组' ELSE workflow_type END as wtype
            FROM workflow_results
            WHERE date_str = :date_str AND step_type = 'final'
        """), {'date_str': date_str})
        return {row[0] for row in result.fetchall()}
