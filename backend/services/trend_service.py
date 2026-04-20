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

        # 解析日期（兼容 Excel 序列号、datetime 对象、字符串）
        try:
            if isinstance(date_val, (int, float)) and 30000 <= date_val <= 60000:
                # Excel 序列号 → 日期
                date_str = (pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(date_val))).strftime("%Y-%m-%d")
            else:
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
    """导出趋势数据到 Excel（xlsxwriter）：每个工作流类型的数据 + 双Y轴折线图，兼容 WPS 和 Excel

    质押类型特殊处理：DB 里的 '质押(中大盘)' 和 '质押(小盘)' 两个子类型在导出时
    合并成一个 '质押' 逻辑组，同一表格并列两套数据列，共享 1 个双曲线图表。
    """
    from config.workflow_type_config import WORKFLOW_TYPE_CONFIG

    # 按工作流类型分组；质押子类型先归入 pledge_sub 两个桶（不入 type_groups）
    type_groups = {}
    pledge_sub = {"中大盘": [], "小盘": []}
    for d in data:
        wt = d["workflow_type"]
        if wt == "质押(中大盘)":
            pledge_sub["中大盘"].append(d)
            continue
        if wt == "质押(小盘)":
            pledge_sub["小盘"].append(d)
            continue
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
    title_fmt = wb.add_format({'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter'})
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
    data_fmt = wb.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    pct_fmt = wb.add_format({'border': 1, 'num_format': '0.00', 'align': 'center', 'valign': 'vcenter'})

    # 列宽
    ws.set_column('A:A', 10)
    ws.set_column('B:B', 16)
    ws.set_column('C:C', 10)
    ws.set_column('D:D', 12)
    ws.set_column('E:E', 14)

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
        # 表格标题（不含后缀）
        table_title = f"【{prefix}{wt}】" if prefix else f"【{wt}】"
        # 图表标题（保留完整）
        chart_title = f"{prefix}{wt} - 站上20日均线占比趋势"

        # 标题（合并 A~E 列）
        ws.merge_range(current_row, 0, current_row, 4, table_title, title_fmt)
        current_row += 1

        # 表头
        for col_idx, h in enumerate(["日期", "站20均线数量", "总量", "占比(%)", "完整日期"]):
            ws.write(current_row, col_idx, h, header_fmt)
        header_row = current_row
        current_row += 1

        # 数据
        data_start_row = current_row
        for item in items:
            # 图表横坐标用短格式 M/D
            ds = item["date_str"]
            try:
                parts = ds.split('-')
                short_date = f"{int(parts[1])}/{int(parts[2])}"
            except Exception:
                short_date = ds
            ws.write(current_row, 0, short_date, data_fmt)
            ws.write(current_row, 1, item["count"], data_fmt)
            ws.write(current_row, 2, item["total"], data_fmt)
            ws.write(current_row, 3, round(item["ratio"] * 100, 2) if item.get("ratio") else 0, pct_fmt)
            ws.write(current_row, 4, ds, data_fmt)  # 完整日期备查
            current_row += 1
        data_end_row = current_row - 1

        # 图表：仅占比(%)折线
        chart = wb.add_chart({'type': 'line'})
        chart.set_title({'name': chart_title})
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

        ws.insert_chart(header_row - 1, 8, chart)

        # 间距
        chart_height_rows = 22
        data_rows_used = len(items) + 2
        current_row = header_row - 1 + max(chart_height_rows, data_rows_used) + 2

    # 质押：中大盘+小盘 合并成一个逻辑组 + 双曲线图表
    if pledge_sub["中大盘"] or pledge_sub["小盘"]:
        zdp_items = sorted(pledge_sub["中大盘"], key=lambda x: x["date_str"])
        xp_items = sorted(pledge_sub["小盘"], key=lambda x: x["date_str"])
        # x 轴 = 所有日期并集
        all_dates = sorted(set([d["date_str"] for d in zdp_items] + [d["date_str"] for d in xp_items]))
        zdp_map = {d["date_str"]: d for d in zdp_items}
        xp_map = {d["date_str"]: d for d in xp_items}

        table_title = "【5质押】"
        chart_title = "5质押 - 站上20日均线占比趋势（中大盘 vs 小盘）"

        # 留出顶部间距
        current_row += 1
        ws.merge_range(current_row, 0, current_row, 8, table_title, title_fmt)
        current_row += 1
        # 表头: 日期 | 中大盘数量 | 中大盘总量 | 中大盘占比% | 小盘数量 | 小盘总量 | 小盘占比% | 完整日期
        headers = ["日期", "中大盘数量", "中大盘总量", "中大盘占比(%)",
                   "小盘数量", "小盘总量", "小盘占比(%)", "完整日期"]
        for col_idx, h in enumerate(headers):
            ws.write(current_row, col_idx, h, header_fmt)
        header_row = current_row
        current_row += 1

        data_start_row = current_row
        for ds in all_dates:
            try:
                parts = ds.split('-')
                short_date = f"{int(parts[1])}/{int(parts[2])}"
            except Exception:
                short_date = ds
            zd = zdp_map.get(ds)
            xd = xp_map.get(ds)
            ws.write(current_row, 0, short_date, data_fmt)
            if zd:
                ws.write(current_row, 1, zd["count"], data_fmt)
                ws.write(current_row, 2, zd["total"], data_fmt)
                ws.write(current_row, 3, round(zd["ratio"] * 100, 2) if zd.get("ratio") else 0, pct_fmt)
            else:
                for c in (1, 2, 3):
                    ws.write(current_row, c, "", data_fmt)
            if xd:
                ws.write(current_row, 4, xd["count"], data_fmt)
                ws.write(current_row, 5, xd["total"], data_fmt)
                ws.write(current_row, 6, round(xd["ratio"] * 100, 2) if xd.get("ratio") else 0, pct_fmt)
            else:
                for c in (4, 5, 6):
                    ws.write(current_row, c, "", data_fmt)
            ws.write(current_row, 7, ds, data_fmt)
            current_row += 1
        data_end_row = current_row - 1

        chart = wb.add_chart({'type': 'line'})
        chart.set_title({'name': chart_title})
        chart.set_size({'width': 720, 'height': 380})

        chart.add_series({
            'name': '中大盘占比(%)',
            'categories': ['站上20日均线趋势', data_start_row, 0, data_end_row, 0],
            'values': ['站上20日均线趋势', data_start_row, 3, data_end_row, 3],
            'line': {'width': 2.5, 'color': '#409EFF'},
            'marker': {'type': 'circle', 'size': 4, 'fill': {'color': '#409EFF'}},
        })
        chart.add_series({
            'name': '小盘占比(%)',
            'categories': ['站上20日均线趋势', data_start_row, 0, data_end_row, 0],
            'values': ['站上20日均线趋势', data_start_row, 6, data_end_row, 6],
            'line': {'width': 2.5, 'color': '#E6A23C'},
            'marker': {'type': 'circle', 'size': 4, 'fill': {'color': '#E6A23C'}},
        })
        chart.set_y_axis({'name': '占比(%)', 'num_format': '0.00'})

        num_points = len(all_dates)
        x_axis_opts = {'name': '日期', 'label_position': 'low'}
        if num_points > 15:
            interval = max(1, num_points // 15)
            x_axis_opts['interval_unit'] = interval
            x_axis_opts['num_font'] = {'rotation': -45, 'size': 9}
        chart.set_x_axis(x_axis_opts)

        ws.insert_chart(header_row - 1, 10, chart)
        chart_height_rows = 22
        data_rows_used = len(all_dates) + 2
        current_row = header_row - 1 + max(chart_height_rows, data_rows_used) + 2

    wb.close()
    logger.info(
        f"趋势Excel已导出(xlsxwriter): {file_path}, {len(data)}条, "
        f"{len(type_names)}个类型"
        f"{'；质押(中大盘 '+str(len(pledge_sub['中大盘']))+' / 小盘 '+str(len(pledge_sub['小盘']))+')' if pledge_sub['中大盘'] or pledge_sub['小盘'] else ''}"
    )
