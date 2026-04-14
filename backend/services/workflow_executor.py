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

from services.path_resolver import get_resolver
from utils.stock_code_normalizer import (
    normalize_stock_code,
    extract_numeric_code,
    match_stock_code_flexible,
    is_public_file as check_is_public_file
)

logger = logging.getLogger(__name__)

# 模块级缓存：只读匹配源数据 + 公共文件
# key: (dir_path, max_mtime) → value: cached data
_match_source_cache: Dict[str, tuple] = {}  # dir_path → (max_mtime, stock_dict)
_public_file_cache: Dict[str, tuple] = {}   # file_path → (mtime, DataFrame)


def _get_dir_mtime(dir_path: str) -> float:
    """获取目录下所有 Excel 文件的最大修改时间"""
    max_mtime = 0.0
    for ext in ("*.xlsx", "*.xls"):
        for f in glob.glob(os.path.join(dir_path, ext)):
            mt = os.path.getmtime(f)
            if mt > max_mtime:
                max_mtime = mt
    return max_mtime


def invalidate_public_cache(dir_path: str = None):
    """清除公共文件缓存，上传/删除文件后调用"""
    if dir_path:
        keys_to_remove = [k for k in _public_file_cache if k.startswith(dir_path)]
        for k in keys_to_remove:
            del _public_file_cache[k]
        logger.info(f"已清除公共文件缓存: {dir_path} ({len(keys_to_remove)}个)")
    else:
        _public_file_cache.clear()
        logger.info("已清除所有公共文件缓存")


def invalidate_match_source_cache(dir_path: str = None):
    """清除匹配源缓存，上传/删除文件后调用"""
    if dir_path:
        keys_to_remove = [k for k in _match_source_cache if k.startswith(dir_path)]
        for k in keys_to_remove:
            del _match_source_cache[k]
        logger.info(f"已清除匹配源缓存: {dir_path} ({len(keys_to_remove)}个)")
    else:
        _match_source_cache.clear()
        logger.info("已清除所有匹配源缓存")


def auto_adjust_excel_width(output_path: str, fixed_width: int = 20):
    """设置固定列宽（不遍历单元格，极快）"""
    try:
        wb = load_workbook(output_path)
        ws = wb.active
        ws.auto_filter.ref = ws.dimensions
        for col_idx in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = fixed_width
        wb.save(output_path)
    except Exception as e:
        logger.warning(f"设置列宽失败: {output_path}, {e}")


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
    def __init__(self, base_dir: str = None, workflow_type: str = ""):
        if base_dir is None:
            import platform
            system = platform.system()
            if system == "Darwin" or os.path.exists("/Users/xiayanji"):
                base_dir = "/Users/xiayanji/qbox/aistock/data/excel"
            else:
                base_dir = "/app/data/excel"
        self.base_dir = base_dir
        self.workflow_type = workflow_type
        self.resolver = get_resolver(base_dir, workflow_type)
        self.today = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(self.base_dir, exist_ok=True)

    def _load_match_source(self, source_path: str, code_col_candidates: List[str], name_col_candidates: List[str]) -> Dict[str, str]:
        """加载匹配源数据，带 mtime 缓存。支持逐行多列回退取值。"""
        current_mtime = _get_dir_mtime(source_path)
        cached = _match_source_cache.get(source_path)
        if cached and cached[0] == current_mtime:
            logger.info(f"匹配源缓存命中: {source_path} ({len(cached[1])}条)")
            return cached[1]

        stock_dict = {}
        excel_files = self._get_excel_files_in_dir(source_path)
        for excel_file in excel_files:
            try:
                src_df = pd.read_excel(excel_file, dtype=str)
                code_cols = [c for c in code_col_candidates if c in src_df.columns]
                name_col = next((c for c in name_col_candidates if c in src_df.columns), None)
                if not code_cols or not name_col:
                    continue

                # 向量化 coalesce：按优先级从多个代码列中取第一个非空值
                combined_code = pd.Series('', index=src_df.index)
                for cc in reversed(code_cols):
                    vals = src_df[cc].fillna('').astype(str).str.strip()
                    mask = vals != ''
                    combined_code[mask] = vals[mask]

                names = src_df[name_col].fillna('').astype(str)
                for code_val, name_val in zip(combined_code, names):
                    nc = normalize_stock_code(code_val)
                    if nc:
                        stock_dict[nc] = normalize_stock_code(name_val)
            except Exception as e:
                logger.warning(f"读取{excel_file}失败: {e}")

        # 预建反向索引：同时存 原始key 和 纯数字key，让匹配 O(1)
        expanded = {}
        for key, val in stock_dict.items():
            expanded[key] = val
            numeric = extract_numeric_code(key)
            if numeric and numeric != key:
                expanded[numeric] = val

        _match_source_cache[source_path] = (current_mtime, expanded)
        logger.info(f"匹配源加载并缓存: {source_path} ({len(stock_dict)}条, 索引{len(expanded)}条)")
        return expanded

    def _read_public_file_cached(self, filepath: str, skiprows: int = 1) -> pd.DataFrame:
        """读取公共文件，带 mtime 缓存"""
        current_mtime = os.path.getmtime(filepath)
        cached = _public_file_cache.get(filepath)
        if cached and cached[0] == current_mtime:
            logger.info(f"公共文件缓存命中: {os.path.basename(filepath)}")
            return cached[1].copy()

        df = pd.read_excel(filepath, skiprows=skiprows)
        _public_file_cache[filepath] = (current_mtime, df)
        logger.info(f"公共文件加载并缓存: {os.path.basename(filepath)} ({len(df)}行)")
        return df.copy()

    def _get_daily_dir(self, date_str: Optional[str] = None) -> str:
        return self.resolver.get_daily_dir(date_str)

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
            elif step_type == "match_ma20":
                return await self._match_ma20(step_config, input_data, date_str)
            elif step_type == "match_soe":
                return await self._match_soe(step_config, input_data, date_str)
            elif step_type == "match_sector":
                return await self._match_sector(step_config, input_data, date_str)
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
        daily_dir = self.resolver.get_upload_directory(date_str)
        files = self._get_excel_files_in_dir(daily_dir)

        public_dir = self.resolver.get_public_directory()
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
            exclude_patterns = config.get("exclude_patterns", ["total_", "output_", "deduped"])
            import re
            output_filename = config.get("output_filename", "")
            extra_excludes = []
            if output_filename:
                base_name = os.path.splitext(output_filename)[0]
                if base_name not in [p for p in exclude_patterns]:
                    extra_excludes.append(base_name)
            # 排除所有步骤可能产生的输出文件
            for step_type in ["merge_excel", "smart_dedup", "extract_columns",
                              "match_high_price", "match_ma20", "match_soe", "match_sector"]:
                auto_name = self.resolver.get_output_filename(step_type, date_str)
                if auto_name:
                    bn = os.path.splitext(auto_name)[0]
                    if bn not in exclude_patterns and bn not in extra_excludes:
                        extra_excludes.append(bn)

            for filepath in all_files:
                filename = os.path.basename(filepath)
                should_exclude = False
                all_patterns = exclude_patterns + extra_excludes
                for pattern in all_patterns:
                    if filename.startswith(pattern) or pattern in filename:
                        should_exclude = True
                        break
                if should_exclude:
                    continue

                is_public_file = check_is_public_file(filepath, public_dir)

                try:
                    if is_public_file:
                        df = self._read_public_file_cached(filepath, skiprows=1)
                    else:
                        df_all = pd.read_excel(filepath)
                        if len(df_all) > 0:
                            start_idx = 0
                            seq_col = None
                            for col in df_all.columns:
                                if '序号' in str(col):
                                    seq_col = col
                                    break

                            if seq_col:
                                for idx in range(len(df_all)):
                                    val = df_all.iloc[idx][seq_col]
                                    try:
                                        if pd.notna(val) and int(float(str(val).strip())) == 1:
                                            start_idx = idx
                                            break
                                    except (ValueError, TypeError):
                                        continue

                            if start_idx > 0:
                                header_row = df_all.iloc[start_idx - 1]
                                known_col_names = {"证券代码", "证券简称", "最新公告日", "公告日期", "代码", "名称", "首次公告日", "交易概述"}
                                header_values = set()
                                for val in header_row:
                                    if pd.notna(val) and isinstance(val, str) and val.strip():
                                        header_values.add(val.strip())

                                if header_values & known_col_names:
                                    new_columns = []
                                    for orig_col, new_name in zip(df_all.columns, header_row):
                                        if pd.notna(new_name) and isinstance(new_name, str) and new_name.strip():
                                            new_columns.append(new_name.strip())
                                        else:
                                            new_columns.append(orig_col)
                                    # 去重列名：重复的追加后缀（如 名称→名称_1），仅保留首次出现的
                                    seen = {}
                                    unique_columns = []
                                    for col in new_columns:
                                        if col in seen:
                                            seen[col] += 1
                                            unique_columns.append(f"{col}_{seen[col]}")
                                        else:
                                            seen[col] = 0
                                            unique_columns.append(col)
                                    df = df_all.iloc[start_idx:].copy()
                                    df.columns = unique_columns
                                    logger.info(f"双行表头，列名重映射({len(unique_columns)}列): {filepath}")
                                else:
                                    df = df_all.iloc[start_idx:].copy()
                                    logger.info(f"跳过前{start_idx}行元数据: {filepath}")
                            else:
                                df = df_all.copy()
                        else:
                            continue

                    df["_source_file"] = filename
                    # 提前过滤到需要的列，减少 concat 内存（55列→4列）
                    target_cols = ["序号", "证券代码", "证券简称", "最新公告日", "代码", "名称", "公告日期", "_source_file"]
                    available = [c for c in target_cols if c in df.columns]
                    if available:
                        df = df[available]
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

            if self.workflow_type == "股权转让":
                column_mapping = {
                    "代码": "证券代码",
                    "名称": "证券简称",
                    "公告日期": "最新公告日"
                }
                merged_df = merged_df.rename(columns=column_mapping)
                logger.info(f"股权转让类型：列名映射完成 - {column_mapping}")

            keep_columns = ["序号", "证券代码", "证券简称", "最新公告日"]
            existing_columns = [col for col in keep_columns if col in merged_df.columns]
            merged_df = merged_df[existing_columns]
            # 去除重复列名（concat 不同格式文件 + rename 可能产生重复列）
            merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]

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

            if "序号" in merged_df.columns:
                merged_df["序号"] = pd.to_numeric(merged_df["序号"], errors='coerce')
                merged_df = merged_df.dropna(subset=["序号"])
                merged_df["序号"] = range(1, len(merged_df) + 1)

            output_filename = config.get("output_filename") or self.resolver.get_output_filename("merge_excel", date_str)
            output_path = os.path.join(daily_dir, output_filename)
            merged_df.to_excel(output_path, index=False)

            return {
                "success": True,
                "message": f"合并完成: {len(dfs)}个文件, 共{len(merged_df)}行",
                "data": clean_df_for_json(merged_df),
                "file_path": output_path,
                "rows": len(merged_df),
                "files_merged": len(dfs),
                "date_str": date_str or self.today,
                "_df": merged_df
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

        df_deduped = df_deduped[~df_deduped[stock_code_col].astype(str).str.upper().str.endswith('.NQ')]

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

        daily_dir = self.resolver.get_upload_directory(date_str)
        deduped_filename = self.resolver.get_output_filename("smart_dedup", date_str, config.get("output_filename"))
        deduped_path = os.path.join(daily_dir, deduped_filename)
        df_deduped.to_excel(deduped_path, index=False)

        return {
            "success": True,
            "message": f"智能去重完成: {original_rows} -> {len(df_deduped)} (删除{removed_rows}行重复数据)",
            "data": clean_df_for_json(df_deduped),
            "file_path": deduped_path,
            "original_rows": original_rows,
            "deduped_rows": len(df_deduped),
            "removed_rows": removed_rows,
            "stock_code_column": stock_code_col,
            "date_column": date_col,
            "_df": df_deduped
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
            daily_dir = self.resolver.get_upload_directory(date_str)
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

        filename = config.get("output_filename") or self.resolver.get_output_filename("export_excel", date_str)
        daily_dir = self.resolver.get_upload_directory(date_str)
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

        source_dir = config.get("source_dir") or self.resolver.get_match_source_directory("match_high_price")
        new_column_name = config.get("new_column_name", "百日新高")

        source_path = os.path.join(self.base_dir, source_dir)
        if not os.path.exists(source_path):
            return {
                "success": False,
                "message": f"目录不存在: {source_path}"
            }

        all_high_stocks = self._load_match_source(
            source_path,
            code_col_candidates=['股票代码', '股票代码.1', '证券代码'],
            name_col_candidates=['股票简称', '证券简称']
        )

        logger.info(f"从{source_dir}目录共加载{len(all_high_stocks)}只新高股票")

        df[new_column_name] = df['证券代码'].apply(
            lambda code: match_stock_code_flexible(code, all_high_stocks)
        )

        matched_count = (df[new_column_name] != '').sum()
        logger.info(f"匹配完成，共匹配{matched_count}条记录")

        output_filename = config.get("output_filename") or self.resolver.get_output_filename("match_high_price", date_str)
        output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
        df.to_excel(output_path, index=False)
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
            "file_path": output_path,
            "_df": df
        }

    async def _match_ma20(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可匹配的数据"
            }

        source_dir = config.get("source_dir") or self.resolver.get_match_source_directory("match_ma20")
        new_column_name = config.get("new_column_name", "20日均线")

        source_path = os.path.join(self.base_dir, source_dir)
        if not os.path.exists(source_path):
            return {
                "success": False,
                "message": f"目录不存在: {source_path}"
            }

        all_ma20_stocks = self._load_match_source(
            source_path,
            code_col_candidates=['股票代码', '股票代码.1', '证券代码'],
            name_col_candidates=['股票简称', '证券简称']
        )

        logger.info(f"从{source_dir}目录共加载{len(all_ma20_stocks)}只股票")

        try:
            if '证券代码' not in df.columns:
                return {"success": False, "message": f"输入数据缺少'证券代码'列, 可用列: {list(df.columns)}"}

            df = df.copy()
            df[new_column_name] = df['证券代码'].apply(
                lambda code: match_stock_code_flexible(code, all_ma20_stocks)
            )

            matched_count = (df[new_column_name] != '').sum()
            logger.info(f"匹配完成，共匹配{matched_count}条记录")

            output_filename = config.get("output_filename") or self.resolver.get_output_filename("match_ma20", date_str)
            output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
            df.to_excel(output_path, index=False)
            logger.info(f"结果已保存到: {output_path}")
        except Exception as e:
            logger.error(f"匹配20日均线执行失败: {e}")
            return {"success": False, "message": f"匹配20日均线失败: {str(e)}"}

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
            "file_path": output_path,
            "_df": df
        }

    async def _match_soe(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可匹配的数据"
            }

        source_dir = config.get("source_dir") or self.resolver.get_match_source_directory("match_soe")
        new_column_name = config.get("new_column_name", "国企")

        source_path = os.path.join(self.base_dir, source_dir)
        if not os.path.exists(source_path):
            return {
                "success": False,
                "message": f"目录不存在: {source_path}"
            }

        all_soe_stocks = self._load_match_source(
            source_path,
            code_col_candidates=['股票代码.1', '股票代码', '证券代码'],
            name_col_candidates=['股票简称', '证券简称']
        )

        logger.info(f"从{source_dir}目录共加载{len(all_soe_stocks)}只国企股票")

        df[new_column_name] = df['证券代码'].apply(
            lambda code: match_stock_code_flexible(code, all_soe_stocks)
        )

        matched_count = (df[new_column_name] != '').sum()
        logger.info(f"匹配完成，共匹配{matched_count}条记录")

        output_filename = config.get("output_filename") or self.resolver.get_output_filename("match_soe", date_str)
        output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
        df.to_excel(output_path, index=False)
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
            "file_path": output_path,
            "_df": df
        }

    async def _match_sector(self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None) -> Dict[str, Any]:
        if df is None:
            return {
                "success": False,
                "message": "没有可匹配的数据"
            }

        source_dir = config.get("source_dir") or self.resolver.get_match_source_directory("match_sector")
        new_column_name = config.get("new_column_name", "一级板块")

        source_path = os.path.join(self.base_dir, source_dir)
        if not os.path.exists(source_path):
            return {
                "success": False,
                "message": f"目录不存在: {source_path}"
            }

        all_sector_stocks = self._load_match_source(
            source_path,
            code_col_candidates=['股票代码.1', '股票代码', '证券代码'],
            name_col_candidates=['所属一级板块', '所属板块', '一级板块', '板块']
        )

        logger.info(f"从{source_dir}目录共加载{len(all_sector_stocks)}只股票")

        df[new_column_name] = df['证券代码'].apply(
            lambda code: match_stock_code_flexible(code, all_sector_stocks)
        )

        matched_count = (df[new_column_name] != '').sum()
        logger.info(f"匹配完成，共匹配{matched_count}条记录")

        output_filename = config.get("output_filename") or self.resolver.get_output_filename("match_sector", date_str)
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
            "file_path": output_path,
            "_df": df
        }


workflow_executor = WorkflowExecutor()
