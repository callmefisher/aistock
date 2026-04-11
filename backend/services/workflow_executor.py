import pandas as pd
import numpy as np
import os
import glob
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def auto_adjust_excel_width(output_path: str):
    try:
        wb = load_workbook(output_path)
        ws = wb.active
        for col_idx, column in enumerate(ws.columns, 1):
            max_length = 0
            column_letter = get_column_letter(col_idx)
            for cell in column:
                try:
                    if cell.value:
                        cell_len = len(str(cell.value))
                        if cell_len > max_length:
                            max_length = cell_len
                except:
                    pass
            adjusted_width = min(max(max_length + 4, 15), 200)
            ws.column_dimensions[column_letter].width = adjusted_width
        wb.save(output_path)
    except Exception as e:
        logger.warning(f"自动调整列宽失败: {output_path}, {e}")


def clean_df_for_json(df: pd.DataFrame) -> List[Dict]:
    df_clean = df.fillna('')
    records = df_clean.head(100).to_dict('records')
    for record in records:
        for k, v in record.items():
            if isinstance(v, (float, np.floating)) and (np.isnan(v) or np.isinf(v)):
                record[k] = ''
            elif isinstance(v, (float, int)) and (v != v or abs(v) == float('inf')):
                record[k] = ''
    return records


class WorkflowExecutor:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            import platform
            system = platform.system()
            if system == "Darwin" or os.path.exists("/Users/xiayanji"):
                base_dir = "/Users/xiayanji/qbox/aistock/data/excel"
            else:
                base_dir = "/app/data/excel"
        self.base_dir = base_dir
        self.today = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_daily_dir(self, date_str: Optional[str] = None) -> str:
        if date_str is None:
            date_str = self.today
        daily_dir = os.path.join(self.base_dir, date_str)
        os.makedirs(daily_dir, exist_ok=True)
        return daily_dir

    def _resolve_path(self, file_path: str, date_str: Optional[str] = None) -> str:
        if os.path.isabs(file_path):
            return file_path
        daily_dir = self._get_daily_dir(date_str)
        return os.path.join(daily_dir, file_path)

    def _get_excel_files_in_dir(self, daily_dir: str) -> List[str]:
        pattern = os.path.join(daily_dir, "*.xlsx")
        files = glob.glob(pattern)
        pattern = os.path.join(daily_dir, "*.xls")
        files.extend(glob.glob(pattern))
        return sorted(files)

    async def execute_step(
        self,
        step_type: str,
        step_config: Dict,
        input_data: Optional[pd.DataFrame] = None,
        date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            if step_type == "import_excel":
                return await self._import_excel(step_config, date_str)
            elif step_type == "merge_excel":
                return await self._merge_excel(step_config, date_str)
            elif step_type == "dedup":
                return await self._dedup(step_config, input_data, date_str)
            elif step_type == "smart_dedup":
                return await self._smart_dedup(step_config, input_data, date_str)
            elif step_type == "extract_columns":
                return await self._extract_columns(step_config, input_data, date_str)
            elif step_type == "export_excel":
                return await self._export_excel(step_config, input_data, date_str)
            elif step_type == "match_high_price":
                return await self._match_high_price(step_config, input_data, date_str)
            elif step_type == "pending":
                return {
                    "success": True,
                    "message": "步骤待定，跳过执行",
                    "data": input_data
                }
            else:
                return {
                    "success": False,
                    "message": f"未知步骤类型: {step_type}"
                }
        except Exception as e:
            logger.error(f"步骤执行失败: {step_type}, {str(e)}")
            return {
                "success": False,
                "message": f"步骤执行失败: {str(e)}"
            }

    async def _import_excel(self, config: Dict, date_str: Optional[str] = None) -> Dict[str, Any]:
        file_path = config.get("file_path")

        if not file_path:
            daily_dir = self._get_daily_dir(date_str)
            return {
                "success": False,
                "message": f"未指定文件路径，请将文件放入: {daily_dir}"
            }

        resolved_path = self._resolve_path(file_path, date_str)

        if not os.path.exists(resolved_path):
            return {
                "success": False,
                "message": f"文件不存在: {resolved_path}"
            }

        try:
            df = pd.read_excel(resolved_path)
            return {
                "success": True,
                "message": f"成功导入Excel，共{len(df)}行",
                "data": clean_df_for_json(df),
                "rows": len(df),
                "columns": list(df.columns),
                "file_path": resolved_path
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Excel读取失败: {str(e)}"
            }

    async def _merge_excel(self, config: Dict, date_str: Optional[str] = None) -> Dict[str, Any]:
        daily_dir = self._get_daily_dir(date_str)
        files = self._get_excel_files_in_dir(daily_dir)

        public_dir = os.path.join(self.base_dir, "2025public")
        public_files = []
        if os.path.exists(public_dir):
            public_files = self._get_excel_files_in_dir(public_dir)

        all_files = files + public_files

        if not all_files:
            return {
                "success": False,
                "message": f"目录下没有找到Excel文件: {daily_dir} 和 {public_dir}"
            }

        try:
            dfs = []
            exclude_patterns = config.get("exclude_patterns", ["total_", "output_"])

            for filepath in all_files:
                filename = os.path.basename(filepath)
                should_exclude = False
                for pattern in exclude_patterns:
                    if filename.startswith(pattern) or pattern in filename:
                        should_exclude = True
                        break
                if should_exclude:
                    continue

                is_public_file = "2025public" in filepath

                try:
                    if is_public_file:
                        df = pd.read_excel(filepath, skiprows=1)
                    else:
                        df_all = pd.read_excel(filepath)
                        if len(df_all) > 0:
                            first_row = df_all.iloc[[0]]
                            df = df_all.iloc[1:]
                            dfs.append(first_row)
                            logger.info(f"保留首行: {filepath}")
                        else:
                            continue

                    df["_source_file"] = filename
                    dfs.append(df)
                    logger.info(f"读取文件: {filepath}, 行数: {len(df)}")
                except Exception as e:
                    logger.warning(f"读取文件失败: {filepath}, 错误: {str(e)}")

            if not dfs:
                return {
                    "success": False,
                    "message": "没有可合并的数据"
                }

            merged_df = pd.concat(dfs, ignore_index=True)

            date_col = None
            for col in ["最新公告日", "公告日", "日期", "date"]:
                if col in merged_df.columns:
                    date_col = col
                    break

            if date_col:
                def parse_date(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, str):
                        val = val.strip()
                        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"]:
                            try:
                                return pd.to_datetime(val, format=fmt)
                            except:
                                continue
                    try:
                        return pd.to_datetime(val)
                    except:
                        return None

                merged_df["_sort_date"] = merged_df[date_col].apply(parse_date)
                merged_df = merged_df.sort_values("_sort_date", ascending=False)
                merged_df = merged_df.drop(columns=["_sort_date"])
                merged_df[date_col] = pd.to_datetime(merged_df[date_col], errors="coerce")
                merged_df[date_col] = merged_df[date_col].dt.strftime("%Y-%m-%d")

            stock_code_col = None
            for col in ["证券代码", "股票代码", "代码"]:
                if col in merged_df.columns:
                    stock_code_col = col
                    break

            if stock_code_col:
                merged_df = merged_df.dropna(subset=[stock_code_col])

            if "序号" in merged_df.columns:
                merged_df["序号"] = pd.to_numeric(merged_df["序号"], errors='coerce')
                merged_df = merged_df.dropna(subset=["序号"])
                merged_df["序号"] = range(1, len(merged_df) + 1)

            output_filename = config.get("output_filename", "total_1.xlsx")
            output_path = os.path.join(daily_dir, output_filename)
            merged_df.to_excel(output_path, index=False)
            auto_adjust_excel_width(output_path)

            return {
                "success": True,
                "message": f"合并完成: {len(dfs)}个文件, 共{len(merged_df)}行",
                "data": clean_df_for_json(merged_df),
                "file_path": output_path,
                "rows": len(merged_df),
                "files_merged": len(dfs),
                "date_str": date_str or self.today
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"合并Excel失败: {str(e)}"
            }

    async def _dedup(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可处理的数据"
            }

        original_rows = len(df)
        df_deduped = df.drop_duplicates()

        return {
            "success": True,
            "message": f"去除重复行完成: {original_rows} -> {len(df_deduped)}",
            "data": clean_df_for_json(df_deduped),
            "original_rows": original_rows,
            "deduped_rows": len(df_deduped),
            "removed_rows": original_rows - len(df_deduped)
        }

    async def _smart_dedup(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可处理的数据"
            }

        stock_code_col = config.get("stock_code_column")
        date_col = config.get("date_column")

        available_columns = [str(c) for c in df.columns.tolist()]

        if not stock_code_col:
            stock_code_candidates = ["证券代码", "股票代码", "代码", "code", "stock_code", "symbol"]
            for candidate in stock_code_candidates:
                for col in available_columns:
                    if candidate.lower() in col.lower():
                        stock_code_col = col
                        break
                if stock_code_col:
                    break

        if not date_col:
            date_candidates = ["最新公告日", "公告日", "日期", "date", "announcement_date", "report_date"]
            for candidate in date_candidates:
                for col in available_columns:
                    if candidate.lower() in col.lower():
                        date_col = col
                        break
                if date_col:
                    break

        if not stock_code_col:
            return {
                "success": False,
                "message": f"未找到证券代码列，请手动指定。可用列: {available_columns}"
            }

        if not date_col:
            return {
                "success": False,
                "message": f"未找到日期列，请手动指定。可用列: {available_columns}"
            }

        original_rows = len(df)

        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        except Exception:
            pass

        df_sorted = df.sort_values(date_col, ascending=False)
        df_deduped = df_sorted.drop_duplicates(subset=[stock_code_col], keep="first")

        df_deduped[date_col] = pd.to_datetime(df_deduped[date_col], errors="coerce")
        df_deduped[date_col] = df_deduped[date_col].dt.strftime("%Y-%m-%d")

        df_deduped = df_deduped.sort_values(date_col, ascending=False).reset_index(drop=True)

        if "序号" in df_deduped.columns:
            df_deduped["序号"] = range(1, len(df_deduped) + 1)
        elif date_col in df_deduped.columns:
            df_deduped.insert(0, "序号", range(1, len(df_deduped) + 1))

        if "_source_file" in df_deduped.columns:
            df_deduped = df_deduped.drop(columns=["_source_file"])

        removed_rows = original_rows - len(df_deduped)

        daily_dir = self._get_daily_dir(date_str)
        deduped_path = os.path.join(daily_dir, "deduped.xlsx")
        df_deduped.to_excel(deduped_path, index=False)
        auto_adjust_excel_width(deduped_path)

        return {
            "success": True,
            "message": f"智能去重完成: {original_rows} -> {len(df_deduped)} (删除{removed_rows}行重复数据)",
            "data": clean_df_for_json(df_deduped),
            "file_path": deduped_path,
            "original_rows": original_rows,
            "deduped_rows": len(df_deduped),
            "removed_rows": removed_rows,
            "stock_code_column": stock_code_col,
            "date_column": date_col
        }

    async def _extract_columns(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可处理的数据"
            }

        available_columns = [str(c) for c in df.columns.tolist()]
        selected_columns = []

        columns_config = config.get("columns")
        if columns_config and len(columns_config) > 0:
            for col_name in columns_config:
                col_name_str = str(col_name)
                for avail_col in available_columns:
                    if col_name_str in avail_col or avail_col in col_name_str:
                        selected_columns.append(avail_col)
                        break
                else:
                    return {
                        "success": False,
                        "message": f"未找到列: {col_name}，可用列: {available_columns}"
                    }
        else:
            fixed_columns = ["序号", "证券代码", "证券简称", "最新公告日"]
            for fixed_col in fixed_columns:
                found = False
                for avail_col in available_columns:
                    if fixed_col in avail_col or avail_col in fixed_col:
                        selected_columns.append(avail_col)
                        found = True
                        break
                if not found:
                    for avail_col in available_columns:
                        if "序号" in avail_col and "证券" not in avail_col:
                            selected_columns.append(avail_col)
                            found = True
                            break

            if len(selected_columns) < len(fixed_columns):
                missing = []
                for i, col in enumerate(fixed_columns):
                    col_str = str(col)
                    found = any(col_str in str(c) or str(c) in col_str for c in available_columns)
                    if not found:
                        missing.append(col)
                if missing:
                    return {
                        "success": False,
                        "message": f"未找到以下列: {missing}，可用列: {available_columns}"
                    }

        df_extracted = df[selected_columns].copy()

        if '最新公告日' in df_extracted.columns:
            df_extracted = df_extracted.sort_values('最新公告日', ascending=False)

        if '序号' in df_extracted.columns:
            df_extracted['序号'] = range(1, len(df_extracted) + 1)
        elif selected_columns and '序号' in selected_columns[0]:
            df_extracted.iloc[:, 0] = range(1, len(df_extracted) + 1)

        if '最新公告日' in df_extracted.columns:
            df_extracted['最新公告日'] = pd.to_datetime(df_extracted['最新公告日']).dt.strftime('%Y-%m-%d')

        output_filename = config.get("output_filename")
        file_path = None
        if output_filename:
            daily_dir = self._get_daily_dir(date_str)
            file_path = os.path.join(daily_dir, output_filename)

            from openpyxl import Workbook
            from openpyxl.utils.dataframe import dataframe_to_rows

            wb = Workbook()
            ws = wb.active

            for r in dataframe_to_rows(df_extracted, index=False, header=True):
                ws.append(r)

            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value is not None and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = max(max_length + 4, 15)
                ws.column_dimensions[column_letter].width = adjusted_width

            wb.save(file_path)

        return {
            "success": True,
            "message": f"成功提取列: {selected_columns}",
            "data": clean_df_for_json(df_extracted),
            "columns": selected_columns,
            "file_path": file_path,
            "rows": len(df_extracted)
        }

    async def _export_excel(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可导出的数据"
            }

        filename = config.get("output_filename", "excel_2.xlsx")
        daily_dir = self._get_daily_dir(date_str)
        filepath = os.path.join(daily_dir, filename)

        try:
            df.to_excel(filepath, index=False)
            auto_adjust_excel_width(filepath)
            return {
                "success": True,
                "message": f"成功导出Excel: {filepath}",
                "file_path": filepath,
                "rows": len(df),
                "date_str": date_str or self.today
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Excel导出失败: {str(e)}"
            }

    async def _match_high_price(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可匹配的数据"
            }

        source_dir = config.get("source_dir", "百日新高")
        new_column_name = config.get("new_column_name", "50日新高")

        source_path = os.path.join(self.base_dir, source_dir)
        if not os.path.exists(source_path):
            return {
                "success": False,
                "message": f"目录不存在: {source_path}"
            }

        all_high_stocks = {}
        excel_files = self._get_excel_files_in_dir(source_path)
        for excel_file in excel_files:
            try:
                hf_df = pd.read_excel(excel_file)
                for _, row in hf_df.iterrows():
                    stock_code = str(row.get('股票代码', '')).strip()
                    stock_name = str(row.get('股票简称', '')).strip()
                    if stock_code and stock_code != 'nan':
                        all_high_stocks[stock_code] = stock_name
            except Exception as e:
                logger.warning(f"读取{excel_file}失败: {e}")

        logger.info(f"从{source_dir}目录共加载{len(all_high_stocks)}只新高股票")

        df[new_column_name] = df.apply(
            lambda row: all_high_stocks.get(str(row.get('证券代码', '')).strip(), ''),
            axis=1
        )

        matched_count = (df[new_column_name] != '').sum()
        logger.info(f"匹配完成，共匹配{matched_count}条记录")

        output_filename = config.get("output_filename", "output_2.xlsx")
        output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
        df.to_excel(output_path, index=False)
        auto_adjust_excel_width(output_path)
        logger.info(f"结果已保存到: {output_path}")

        df_clean = df.fillna('')
        records = df_clean.head(100).to_dict('records')
        for record in records:
            for k, v in record.items():
                if isinstance(v, (float, int)) and (v != v or abs(v) == float('inf')):
                    record[k] = ''

        return {
            "success": True,
            "message": f"匹配完成，匹配{matched_count}条记录，已保存到{output_filename}",
            "data": records,
            "columns": df.columns.tolist(),
            "rows": len(df),
            "file_path": output_path
        }


workflow_executor = WorkflowExecutor()
