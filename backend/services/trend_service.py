import logging
import pandas as pd
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from core.database import AsyncSessionLocal
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter
import xlsxwriter

logger = logging.getLogger(__name__)


async def save_trend_data(
    metric_type: str,
    workflow_type: str,
    date_str: str,
    count: int,
    total: int,
    source: str = "manual"
) -> bool:
    ratio = round(count / total, 4) if total > 0 else 0.0
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                INSERT INTO trend_statistics (metric_type, workflow_type, date_str, count, total, ratio, source, created_at, updated_at)
                VALUES (:metric_type, :workflow_type, :date_str, :count, :total, :ratio, :source, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    count = VALUES(count),
                    total = VALUES(total),
                    ratio = VALUES(ratio),
                    source = VALUES(source),
                    updated_at = NOW()
            """), {
                "metric_type": metric_type,
                "workflow_type": workflow_type,
                "date_str": date_str,
                "count": count,
                "total": total,
                "ratio": ratio,
                "source": source,
            })
            await session.commit()
            logger.info(f"趋势数据已保存: {metric_type}/{workflow_type}/{date_str} count={count} total={total} ratio={ratio}")
            return True
    except Exception as e:
        logger.error(f"保存趋势数据失败: {e}")
        return False


async def get_trend_data(
    metric_type: str,
    workflow_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    try:
        async with AsyncSessionLocal() as session:
            query = "SELECT id, metric_type, workflow_type, date_str, count, total, ratio, source, created_at FROM trend_statistics WHERE metric_type = :metric_type AND workflow_type NOT IN ('条件交集', '导出20日均线趋势')"
            params: Dict[str, Any] = {"metric_type": metric_type}

            if workflow_type:
                query += " AND workflow_type = :workflow_type"
                params["workflow_type"] = workflow_type
            if start_date:
                query += " AND date_str >= :start_date"
                params["start_date"] = start_date
            if end_date:
                query += " AND date_str <= :end_date"
                params["end_date"] = end_date

            query += " ORDER BY workflow_type, date_str ASC"
            result = await session.execute(text(query), params)
            rows = result.fetchall()

            return [
                {
                    "id": r[0], "metric_type": r[1], "workflow_type": r[2],
                    "date_str": r[3], "count": r[4], "total": r[5],
                    "ratio": r[6], "source": r[7],
                    "created_at": r[8].strftime("%Y-%m-%d %H:%M:%S") if r[8] else None
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"查询趋势数据失败: {e}")
        return []


async def delete_trend_data(record_id: int) -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM trend_statistics WHERE id = :id"), {"id": record_id})
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"删除趋势数据失败: {e}")
        return False


def parse_excel_for_trend(file_path: str, workflow_type: str) -> List[Dict[str, Any]]:
    """解析 Excel 文件为趋势数据记录列表，供前端预览确认"""
    df = pd.read_excel(file_path)

    # 归一化列名：去除空白、换行后缀
    col_map = {}
    for col in df.columns:
        clean = str(col).split('\n')[0].strip()
        col_map[col] = clean
    df = df.rename(columns=col_map)

    # 映射标准列名
    rename = {}
    for col in df.columns:
        cl = col.lower().strip()
        if cl in ("日期", "date", "数据日期"):
            rename[col] = "日期"
        elif "占20均线" in col or "站20日均线" in col or "20日均线数量" in cl:
            rename[col] = "站20日均线数量"
        elif "占比" in col or "比例" in col:
            rename[col] = "占比"
    df = df.rename(columns=rename)

    if "日期" not in df.columns:
        raise ValueError(f"未找到日期列，可用列: {list(df.columns)}")
    if "站20日均线数量" not in df.columns:
        raise ValueError(f"未找到数量列(占20均线数量/站20日均线数量)，可用列: {list(df.columns)}")

    records = []
    for _, row in df.iterrows():
        date_val = row["日期"]
        if pd.isna(date_val):
            continue

        # 解析日期
        try:
            date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d")
        except Exception:
            continue

        count = int(float(str(row["站20日均线数量"]).strip())) if pd.notna(row["站20日均线数量"]) else 0

        # 从占比反算总量
        total = 0
        if "占比" in df.columns and pd.notna(row.get("占比")):
            ratio_val = row["占比"]
            if isinstance(ratio_val, str):
                ratio_val = ratio_val.strip().rstrip('%')
                try:
                    ratio_float = float(ratio_val)
                    # 判断是百分比值还是小数值
                    if ratio_float > 1:
                        ratio_float = ratio_float / 100
                    total = round(count / ratio_float) if ratio_float > 0 else 0
                except ValueError:
                    pass
            elif isinstance(ratio_val, (int, float)):
                ratio_float = float(ratio_val)
                if ratio_float > 1:
                    ratio_float = ratio_float / 100
                total = round(count / ratio_float) if ratio_float > 0 else 0

        if "总量" in df.columns and pd.notna(row.get("总量")):
            total = int(float(str(row["总量"]).strip()))

        ratio = round(count / total, 4) if total > 0 else 0.0

        records.append({
            "workflow_type": workflow_type,
            "date_str": date_str,
            "count": count,
            "total": total,
            "ratio": ratio,
        })

    return records


async def batch_save_trend_data(metric_type: str, records: List[Dict[str, Any]], source: str = "excel") -> int:
    if not records:
        return 0
    try:
        async with AsyncSessionLocal() as session:
            for rec in records:
                count = rec["count"]
                total = rec["total"]
                ratio = round(count / total, 4) if total > 0 else 0.0
                await session.execute(text("""
                    INSERT INTO trend_statistics (metric_type, workflow_type, date_str, count, total, ratio, source, created_at, updated_at)
                    VALUES (:metric_type, :wt, :ds, :count, :total, :ratio, :source, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE
                        count = VALUES(count), total = VALUES(total), ratio = VALUES(ratio),
                        source = VALUES(source), updated_at = NOW()
                """), {
                    "metric_type": metric_type, "wt": rec["workflow_type"], "ds": rec["date_str"],
                    "count": count, "total": total, "ratio": ratio, "source": source,
                })
            await session.commit()
            logger.info(f"批量保存趋势数据: {len(records)}条")
            return len(records)
    except Exception as e:
        logger.error(f"批量保存趋势数据失败: {e}")
        return 0


def export_trend_excel_with_chart(data: List[Dict], file_path: str, single_type: str = None):
    """导出趋势数据到 Excel（xlsxwriter）：每个工作流类型的数据 + 双Y轴折线图，兼容 WPS 和 Excel"""
    from config.workflow_type_config import WORKFLOW_TYPE_CONFIG

    # 按工作流类型分组
    type_groups = {}
    for d in data:
        wt = d["workflow_type"]
        if wt not in type_groups:
            type_groups[wt] = []
        type_groups[wt].append(d)

    # 从 config 提取排序前缀和显示名
    def get_type_sort_key(wt):
        cfg = WORKFLOW_TYPE_CONFIG.get(wt, WORKFLOW_TYPE_CONFIG.get("", {}))
        tpl = cfg.get("naming", {}).get("output_template", "")
        # 提取开头数字如 "1并购重组{date}.xlsx" → 1
        import re
        m = re.match(r'^(\d+)', tpl)
        return int(m.group(1)) if m else 99

    def get_type_prefix(wt):
        cfg = WORKFLOW_TYPE_CONFIG.get(wt, WORKFLOW_TYPE_CONFIG.get("", {}))
        tpl = cfg.get("naming", {}).get("output_template", "")
        import re
        m = re.match(r'^(\d+)', tpl)
        return m.group(1) if m else ""

    type_names = sorted(type_groups.keys(), key=get_type_sort_key)

    wb = xlsxwriter.Workbook(file_path)
    ws = wb.add_worksheet("站上20日均线趋势")

    # 格式
    title_fmt = wb.add_format({'bold': True, 'font_size': 13})
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
    data_fmt = wb.add_format({'border': 1})
    pct_fmt = wb.add_format({'border': 1, 'num_format': '0.00'})

    # 列宽
    ws.set_column('A:A', 14)
    ws.set_column('B:B', 16)
    ws.set_column('C:C', 10)
    ws.set_column('D:D', 12)

    if not type_names:
        ws.write(0, 0, "暂无数据")
        wb.close()
        return

    current_row = 0

    for wt in type_names:
        items = sorted(type_groups[wt], key=lambda x: x["date_str"])
        if not items:
            continue

        prefix = get_type_prefix(wt)
        display_title = f"【{prefix}{wt}】站上20日均线趋势" if prefix else f"【{wt}】站上20日均线趋势"

        # 标题
        ws.write(current_row, 0, display_title, title_fmt)
        current_row += 1

        # 表头
        for col_idx, h in enumerate(["日期", "站20均线数量", "总量", "占比(%)"]):
            ws.write(current_row, col_idx, h, header_fmt)
        header_row = current_row
        current_row += 1

        # 数据
        data_start_row = current_row
        for item in items:
            ws.write(current_row, 0, item["date_str"], data_fmt)
            ws.write(current_row, 1, item["count"], data_fmt)
            ws.write(current_row, 2, item["total"], data_fmt)
            ws.write(current_row, 3, round(item["ratio"] * 100, 2) if item.get("ratio") else 0, pct_fmt)
            current_row += 1
        data_end_row = current_row - 1

        # 图表：仅占比(%)折线
        chart = wb.add_chart({'type': 'line'})
        chart.set_title({'name': f'{prefix}{wt} - 站上20日均线占比趋势'})
        chart.set_size({'width': 620, 'height': 360})
        chart.set_legend({'none': True})

        chart.add_series({
            'name': '占比(%)',
            'categories': ['站上20日均线趋势', data_start_row, 0, data_end_row, 0],
            'values': ['站上20日均线趋势', data_start_row, 3, data_end_row, 3],
            'line': {'width': 2.5, 'color': '#409EFF'},
            'marker': {'type': 'circle', 'size': 4, 'fill': {'color': '#409EFF'}},
        })

        chart.set_y_axis({'name': '占比(%)', 'num_format': '0.00'})

        # X轴：日期过多时间隔显示标签，保证最多约15个可见标签
        num_points = len(items)
        x_axis_opts = {'name': '日期', 'label_position': 'low'}
        if num_points > 15:
            interval = max(1, num_points // 15)
            x_axis_opts['interval_unit'] = interval
            x_axis_opts['label_position'] = 'low'
            x_axis_opts['num_font'] = {'rotation': -45, 'size': 9}
        chart.set_x_axis(x_axis_opts)

        ws.insert_chart(header_row - 1, 5, chart)

        # 间距
        chart_height_rows = 22
        data_rows_used = len(items) + 2
        current_row = header_row - 1 + max(chart_height_rows, data_rows_used) + 2

    wb.close()
    logger.info(f"趋势Excel已导出(xlsxwriter): {file_path}, {len(data)}条, {len(type_names)}个类型")
