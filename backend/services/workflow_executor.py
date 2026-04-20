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
_public_file_cache: Dict[str, tuple] = {}   # file_path → (mtime, DataFrame/dict)
_PUBLIC_FILE_CACHE_MAX = 50  # 最大缓存条目数，超出时淘汰最早的条目


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


def auto_adjust_excel_width(output_path: str, fixed_width: int = 20, all_sheets: bool = False):
    """设置固定列宽（不遍历单元格，极快）"""
    try:
        wb = load_workbook(output_path)
        sheets = wb.worksheets if all_sheets else [wb.active]
        for ws in sheets:
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

    def _derive_pledge_source(self, sheet_name: str) -> str:
        """质押类型：Sheet 名以"中大盘"开头 → "中大盘"，否则 → "小盘"。"""
        return "中大盘" if str(sheet_name).strip().startswith("中大盘") else "小盘"

    def _detect_header_and_parse(self, df_all: pd.DataFrame, known_col_names: set, filepath: str) -> pd.DataFrame:
        """统一处理单行表头、双行表头、分组头三种情况。

        关键场景：部分列名在 Row1 就正确（如序号、证券代码），但另一部分列（如更新日期）
        在 Row1 是分组头（如"申报进程日期"），Row2 才是实际列名。
        策略：如果某个数据行包含列名中没有的已知列名，说明需要重映射。
        """
        # 收集当前列名中的已知列名
        col_name_set = set()
        for c in df_all.columns:
            s = str(c).strip()
            if s and not s.startswith('Unnamed'):
                col_name_set.add(s)
        cols_known = col_name_set & known_col_names

        # 扫描前10行数据，找包含已知列名的行（可能是真实表头行）
        best_row_idx = -1
        best_new_names = set()  # 该行提供的、列头中没有的已知列名
        best_total = 0
        for idx in range(min(10, len(df_all))):
            row_vals = set()
            for val in df_all.iloc[idx]:
                if pd.notna(val) and isinstance(val, str) and val.strip():
                    row_vals.add(val.strip())
            row_known = row_vals & known_col_names
            new_names = row_known - cols_known  # 该行带来的新列名
            total = len(row_known)
            # 优先选提供新列名最多的行；相同时选总匹配最多的
            if len(new_names) > len(best_new_names) or (len(new_names) == len(best_new_names) and total > best_total):
                best_new_names = new_names
                best_total = total
                best_row_idx = idx

        # 如果数据行提供了列头中没有的已知列名 → 需要重映射（限前3行，防止误匹配数据行）
        if len(best_new_names) >= 2 and best_total >= 2 and best_row_idx <= 3:
            header_row = df_all.iloc[best_row_idx]
            new_columns = []
            for orig_col, new_name in zip(df_all.columns, header_row):
                if pd.notna(new_name) and isinstance(new_name, str) and new_name.strip():
                    new_columns.append(new_name.strip())
                else:
                    new_columns.append(str(orig_col).strip())
            # 去重列名
            seen = {}
            unique_columns = []
            for col_name in new_columns:
                if col_name in seen:
                    seen[col_name] += 1
                    unique_columns.append(f"{col_name}_{seen[col_name]}")
                else:
                    seen[col_name] = 0
                    unique_columns.append(col_name)
            df = df_all.iloc[best_row_idx + 1:].copy()
            df.columns = unique_columns
            logger.info(f"表头重映射: 第{best_row_idx+2}行为实际表头(新增列名{best_new_names}), 最终列: {unique_columns}: {filepath}")
            return df

        # 列名已经正确，找数据起始行（序号=1）
        seq_col = None
        for col in df_all.columns:
            if '序号' in str(col):
                seq_col = col
                break
        if seq_col:
            for idx in range(min(20, len(df_all))):
                val = df_all.iloc[idx][seq_col]
                try:
                    if pd.notna(val) and int(float(str(val).strip())) == 1:
                        if idx > 0:
                            df = df_all.iloc[idx:].copy()
                            logger.info(f"跳过前{idx}行元数据: {filepath}")
                            return df
                        break
                except (ValueError, TypeError):
                    continue

        logger.info(f"普通表头，直接读取: {filepath}")
        return df_all.copy()

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
            elif step_type == "condition_intersection":
                return await self._condition_intersection(step_config, date_str)
            elif step_type == "export_ma20_trend":
                return await self._export_ma20_trend(step_config, date_str)
            elif step_type == "ranking_sort":
                return await self._ranking_sort(step_config, input_data, date_str)
            elif step_type == "pledge_trend_analysis":
                return await self._pledge_trend_analysis(step_config, input_data, date_str)
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

        public_dir = self.resolver.get_public_directory(date_str)
        public_files = []
        if not self.resolver.config.get("skip_public_in_merge") and os.path.exists(public_dir):
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
                    # 质押：多 Sheet 遍历，每 Sheet 单独检测表头并注入"来源"列
                    if self.workflow_type == "质押" and not is_public_file:
                        sheet_map = pd.read_excel(filepath, sheet_name=None)
                        known_col_names_pledge = {
                            "证券代码", "证券简称", "证券名称", "最新公告日",
                            "股权质押公告日期",
                        }
                        for sheet_name, df_sheet in sheet_map.items():
                            if df_sheet is None or len(df_sheet) == 0:
                                continue
                            df_parsed = self._detect_header_and_parse(
                                df_sheet, known_col_names_pledge,
                                f"{filepath}#{sheet_name}"
                            )
                            # 动态匹配"股权质押公告日期"前缀列（sheet 粒度，保证每个 sheet 独立生效）
                            pledge_date_cols = [
                                c for c in df_parsed.columns
                                if isinstance(c, str) and "股权质押公告日期" in c
                            ]
                            df_parsed["来源"] = self._derive_pledge_source(sheet_name)
                            df_parsed["_source_file"] = filename
                            # 提前列过滤（质押白名单）
                            target_cols_pledge = [
                                "序号", "证券代码", "证券简称", "证券名称",
                                "最新公告日", "来源", "_source_file",
                            ] + pledge_date_cols
                            available_p = [c for c in target_cols_pledge if c in df_parsed.columns]
                            if available_p:
                                df_parsed = df_parsed[available_p]
                            dfs.append(df_parsed)
                            logger.info(f"读取 sheet: {filepath}#{sheet_name}, 行数: {len(df_parsed)}, 来源: {df_parsed['来源'].iloc[0] if len(df_parsed) else '-'}")
                        continue

                    if is_public_file:
                        public_skiprows = self.resolver.config.get("public_skiprows", 1)
                        df = self._read_public_file_cached(filepath, skiprows=public_skiprows)
                    elif self.workflow_type == "申报并购重组":
                        # 申报并购重组源文件第1行是分组头（如"申报进程日期"），直接跳过
                        df = pd.read_excel(filepath, skiprows=1)
                        if len(df) == 0:
                            continue
                    else:
                        df_all = pd.read_excel(filepath)
                        if len(df_all) > 0:
                            if self.resolver.config.get("skip_public_in_merge"):
                                # 涨幅排名等类型：直接使用第一行作为列头，不做表头检测
                                df = df_all
                            else:
                                known_col_names = {"证券代码", "证券简称", "最新公告日", "公告日期", "代码", "名称",
                                                   "首次公告日", "交易概述", "上市公告日", "更新日期", "受理日期", "重组类型",
                                                   "证券名称", "最新大股东减持公告日期", "发生日期"}
                                df = self._detect_header_and_parse(df_all, known_col_names, filepath)
                        else:
                            continue

                    # 减持叠加质押和大宗交易：Wind 风格列名含 \n 后缀，剥离以匹配标准列名
                    if self.workflow_type == "减持叠加质押和大宗交易":
                        df.columns = [c.split('\n')[0] if isinstance(c, str) else c for c in df.columns]

                    df["_source_file"] = filename
                    # 提前过滤到需要的列，减少 concat 内存（55列→4列）
                    # 涨幅排名等类型保留所有列
                    if not self.resolver.config.get("skip_public_in_merge"):
                        target_cols = ["序号", "证券代码", "证券简称", "最新公告日", "代码", "名称", "公告日期", "上市公告日", "更新日期",
                                       "证券名称", "最新大股东减持公告日期", "发生日期", "_source_file"]
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

            if self.workflow_type == "增发实现" and "上市公告日" in merged_df.columns:
                if "最新公告日" in merged_df.columns:
                    merged_df["最新公告日"] = merged_df["最新公告日"].fillna(merged_df["上市公告日"])
                    merged_df = merged_df.drop(columns=["上市公告日"])
                else:
                    merged_df = merged_df.rename(columns={"上市公告日": "最新公告日"})
                logger.info(f"增发实现类型：上市公告日→最新公告日 映射完成")

            if self.workflow_type == "申报并购重组" and "更新日期" in merged_df.columns:
                # 源文件的"最新公告日"列多为"-"无效值，直接用"更新日期"替代
                if "最新公告日" in merged_df.columns:
                    merged_df = merged_df.drop(columns=["最新公告日"])
                merged_df = merged_df.rename(columns={"更新日期": "最新公告日"})
                logger.info(f"申报并购重组类型：更新日期→最新公告日 映射完成")

            if self.workflow_type == "减持叠加质押和大宗交易":
                # 清洗不规范字符：全角空格、不可见字符、前后空白
                for col in merged_df.columns:
                    if merged_df[col].dtype == object:
                        mask = merged_df[col].notna()
                        merged_df.loc[mask, col] = (merged_df.loc[mask, col]
                                                    .astype(str)
                                                    .str.replace('\u3000', ' ', regex=False)
                                                    .str.replace(r'[\x00-\x1f\x7f-\x9f]', '', regex=True)
                                                    .str.strip())

                # 列名映射：仅在目标列不存在时才做映射
                if "证券简称" not in merged_df.columns and "证券名称" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"证券名称": "证券简称"})
                    logger.info("减持叠加质押和大宗交易：证券名称→证券简称 映射完成")
                if "最新公告日" not in merged_df.columns and "最新大股东减持公告日期" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"最新大股东减持公告日期": "最新公告日"})
                    logger.info("减持叠加质押和大宗交易：最新大股东减持公告日期→最新公告日 映射完成")

            if self.workflow_type == "招投标":
                # 清洗不规范字符：全角空格、不可见字符、前后空白
                for col in merged_df.columns:
                    if merged_df[col].dtype == object:
                        mask = merged_df[col].notna()
                        merged_df.loc[mask, col] = (merged_df.loc[mask, col]
                                                    .astype(str)
                                                    .str.replace('\u3000', ' ', regex=False)
                                                    .str.replace(r'[\x00-\x1f\x7f-\x9f]', '', regex=True)
                                                    .str.strip())

                # 列名映射：仅在目标列不存在时才做映射
                if "证券简称" not in merged_df.columns and "证券名称" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"证券名称": "证券简称"})
                    logger.info("招投标：证券名称→证券简称 映射完成")
                if "最新公告日" not in merged_df.columns and "发生日期" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"发生日期": "最新公告日"})
                    logger.info("招投标：发生日期→最新公告日 映射完成")

            if self.workflow_type == "质押":
                # 清洗不规范字符
                for col in merged_df.columns:
                    if merged_df[col].dtype == object:
                        mask = merged_df[col].notna()
                        merged_df.loc[mask, col] = (merged_df.loc[mask, col]
                                                    .astype(str)
                                                    .str.replace('\u3000', ' ', regex=False)
                                                    .str.replace(r'[\x00-\x1f\x7f-\x9f]', '', regex=True)
                                                    .str.strip())

                # 证券名称 → 证券简称（仅在目标列不存在时）
                if "证券简称" not in merged_df.columns and "证券名称" in merged_df.columns:
                    merged_df = merged_df.rename(columns={"证券名称": "证券简称"})
                    logger.info("质押：证券名称→证券简称 映射完成")

                # 前缀含"股权质押公告日期" → 最新公告日
                if "最新公告日" not in merged_df.columns:
                    candidates = [c for c in merged_df.columns
                                  if isinstance(c, str) and "股权质押公告日期" in c]
                    if candidates:
                        primary = candidates[0]
                        for extra in candidates[1:]:
                            merged_df[primary] = merged_df[primary].fillna(merged_df[extra])
                            merged_df = merged_df.drop(columns=[extra])
                        merged_df = merged_df.rename(columns={primary: "最新公告日"})
                        logger.info(f"质押：{primary}→最新公告日 映射完成")

                # 若存在"股权质押公告日期"列 但 也存在"最新公告日"列，合并到最新公告日
                if "最新公告日" in merged_df.columns:
                    leftover = [c for c in merged_df.columns
                                if isinstance(c, str) and "股权质押公告日期" in c and c != "最新公告日"]
                    for extra in leftover:
                        merged_df["最新公告日"] = merged_df["最新公告日"].fillna(merged_df[extra])
                        merged_df = merged_df.drop(columns=[extra])

            # 删除内部辅助列
            if "_source_file" in merged_df.columns:
                merged_df = merged_df.drop(columns=["_source_file"])

            # skip_public_in_merge (涨幅排名): 跳过标准列提取、日期排序、序号处理，
            # 保留原始列结构供后续 ranking_sort 步骤使用
            if not self.resolver.config.get("skip_public_in_merge"):
                keep_columns = ["序号", "证券代码", "证券简称", "最新公告日"]
                # 质押类型额外保留"来源"列
                if self.workflow_type == "质押":
                    keep_columns.append("来源")
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
                else:
                    merged_df.insert(0, "序号", range(1, len(merged_df) + 1))

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
            date_candidates = ["最新公告日", "公告日", "更新日期", "日期", "date", "announcement_date", "report_date"]
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
            # 质押类型额外保留"来源"列
            if self.workflow_type == "质押":
                fixed_columns = fixed_columns + ["来源"]
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

        source_path = config.get("source_dir") or self.resolver.get_match_source_directory("match_high_price", date_str)
        new_column_name = config.get("new_column_name", "百日新高")

        # 确保目录存在且有文件（自动从历史日期复制）
        if date_str:
            source_path = self.resolver.ensure_match_source_files("match_high_price", date_str)

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

        logger.info(f"从{source_path}目录共加载{len(all_high_stocks)}只新高股票")

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

        source_path = config.get("source_dir") or self.resolver.get_match_source_directory("match_ma20", date_str)
        new_column_name = config.get("new_column_name", "20日均线")

        if date_str:
            source_path = self.resolver.ensure_match_source_files("match_ma20", date_str)

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

        logger.info(f"从{source_path}目录共加载{len(all_ma20_stocks)}只股票")

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

        source_path = config.get("source_dir") or self.resolver.get_match_source_directory("match_soe", date_str)
        new_column_name = config.get("new_column_name", "国企")

        if date_str:
            source_path = self.resolver.ensure_match_source_files("match_soe", date_str)

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

        logger.info(f"从{source_path}目录共加载{len(all_soe_stocks)}只国企股票")

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

        source_path = config.get("source_dir") or self.resolver.get_match_source_directory("match_sector", date_str)
        new_column_name = config.get("new_column_name", "一级板块")

        if date_str:
            source_path = self.resolver.ensure_match_source_files("match_sector", date_str)

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

        logger.info(f"从{source_path}目录共加载{len(all_sector_stocks)}只股票")

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

        # 自动采集20日均线趋势数据
        if '20日均线' in df.columns:
            try:
                ma20_count = int((df['20日均线'].fillna('').astype(str).str.strip() != '').sum())
                ma20_total = len(df)
                from services.trend_service import save_trend_data
                await save_trend_data(
                    metric_type='ma20',
                    workflow_type=self.workflow_type or '并购重组',
                    date_str=date_str or self.today,
                    count=ma20_count,
                    total=ma20_total,
                    source='auto'
                )
                logger.info(f"自动采集MA20趋势: type={self.workflow_type}, count={ma20_count}, total={ma20_total}")
            except Exception as e:
                logger.warning(f"自动采集MA20趋势失败: {e}")

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

    async def _condition_intersection(self, config: Dict, date_str: Optional[str] = None) -> Dict[str, Any]:
        """条件交集步骤：聚合所有工作流类型的最终数据，过滤后合并输出+交集选股池"""
        import zlib
        import json as json_mod
        from config.workflow_type_config import (
            WORKFLOW_TYPE_CONFIG, INTERSECTION_SOURCE_COLUMNS,
            INTERSECTION_COLUMN_RENAME, INTERSECTION_DISPLAY_COLUMNS
        )
        from core.database import AsyncSessionLocal
        from sqlalchemy import text

        date_str = config.get("date_str") or date_str or self.today
        filter_conditions = config.get("filter_conditions", [{"column": "百日新高", "enabled": True}])
        filter_logic = config.get("filter_logic", "AND")
        type_order = config.get("type_order", WORKFLOW_TYPE_CONFIG.get("条件交集", {}).get("default_type_order", []))
        output_filename = config.get("output_filename") or f"7条件交集{date_str.replace('-', '')}.xlsx"
        workflow_id = config.get("_workflow_id")

        logger.info(f"[条件交集] 开始执行: date={date_str}, filters={filter_conditions}, logic={filter_logic}")

        # 1. 从 DB 获取各类型 final 数据
        type_dataframes = {}
        async with AsyncSessionLocal() as session:
            for wtype in type_order:
                # 并购重组 type 可能为空字符串，用 IN 参数化查询
                if wtype == "并购重组":
                    query = text("""
                        SELECT data_compressed FROM workflow_results
                        WHERE workflow_type IN (:wtype_empty, :wtype_cn)
                          AND date_str = :date_str AND step_type = 'final'
                        ORDER BY created_at DESC LIMIT 1
                    """)
                    params = {"date_str": date_str, "wtype_empty": "", "wtype_cn": "并购重组"}
                else:
                    query = text("""
                        SELECT data_compressed FROM workflow_results
                        WHERE workflow_type = :wtype
                          AND date_str = :date_str AND step_type = 'final'
                        ORDER BY created_at DESC LIMIT 1
                    """)
                    params = {"date_str": date_str, "wtype": wtype}

                result = await session.execute(query, params)
                row = result.fetchone()
                if row and row[0]:
                    try:
                        decompressed = zlib.decompress(row[0])
                        records = json_mod.loads(decompressed.decode("utf-8"))
                        df = pd.DataFrame(records)
                        type_dataframes[wtype] = df
                        logger.info(f"[条件交集] 读取 {wtype}: {len(df)}行")
                    except Exception as e:
                        logger.warning(f"[条件交集] 解压 {wtype} 数据失败: {e}")
                else:
                    logger.info(f"[条件交集] {wtype} 无数据，跳过")

        if not type_dataframes:
            return {"success": False, "message": "所有工作流类型均无数据，无法执行条件交集"}

        # 2. 对每个类型应用过滤条件
        filtered_dfs = {}
        for wtype, df in type_dataframes.items():
            filtered = self._apply_filters(df, filter_conditions, filter_logic)
            if len(filtered) > 0:
                filtered_dfs[wtype] = filtered
                logger.info(f"[条件交集] {wtype} 过滤后: {len(filtered)}行 (原{len(df)}行)")
            else:
                logger.info(f"[条件交集] {wtype} 过滤后无数据")

        if not filtered_dfs:
            return {"success": False, "message": "所有工作流类型过滤后均无数据"}

        # 3. 合并数据，按 type_order 顺序
        combined_rows = []
        warnings_list = []   # 冒泡到返回值的警告
        for wtype in type_order:
            if wtype not in filtered_dfs:
                continue
            df = filtered_dfs[wtype]
            # 提取标准列
            extracted = pd.DataFrame()
            for col in INTERSECTION_SOURCE_COLUMNS:
                if col in df.columns:
                    extracted[col] = df[col]
                else:
                    extracted[col] = ""

            # 资本运作行为列：质押类型按"来源"细分为"质押中大盘"/"质押小盘"
            if wtype == "质押":
                if "来源" in df.columns:
                    source_series = df["来源"].fillna("").astype(str).str.strip()
                    missing_mask = ~source_series.isin(["中大盘", "小盘"])
                    missing_count = int(missing_mask.sum())
                    if missing_count > 0:
                        sample_codes = []
                        if "证券代码" in df.columns:
                            sample_codes = df.loc[missing_mask, "证券代码"].head(5).tolist()
                        warnings_list.append(
                            f"质押类型 {missing_count}/{len(df)} 行'来源'字段缺失或非法，"
                            f"已兜底为'质押小盘'。示例: {sample_codes}"
                        )
                        logger.warning(f"[条件交集] {warnings_list[-1]}")
                    extracted["资本运作行为"] = source_series.apply(
                        lambda s: "质押中大盘" if s == "中大盘" else "质押小盘"
                    ).values
                else:
                    warnings_list.append("质押类型 final 数据完全缺少'来源'列，全部归入'质押小盘'")
                    logger.warning(f"[条件交集] {warnings_list[-1]}")
                    extracted["资本运作行为"] = "质押小盘"
            else:
                display_name = WORKFLOW_TYPE_CONFIG.get(wtype, {}).get("display_name", wtype)
                extracted["资本运作行为"] = display_name
            combined_rows.append(extracted)

        combined_df = pd.concat(combined_rows, ignore_index=True)
        # 重新编号序号
        combined_df["序号"] = range(1, len(combined_df) + 1)

        # 4. 交集计算逻辑（暂保留，当前 Sheet2 直接复制 Sheet1）
        # code_sets = []
        # for wtype, df in filtered_dfs.items():
        #     if "证券代码" in df.columns:
        #         codes = set(df["证券代码"].dropna().astype(str).str.strip())
        #         codes.discard("")
        #         code_sets.append(codes)
        #     else:
        #         logger.warning(f"[条件交集] {wtype} 缺少证券代码列，跳过交集计算")
        # intersection_codes = set()
        # if code_sets:
        #     intersection_codes = code_sets[0]
        #     for s in code_sets[1:]:
        #         intersection_codes &= s
        # if intersection_codes and "证券代码" in combined_df.columns:
        #     mask = combined_df["证券代码"].astype(str).str.strip().isin(intersection_codes)
        #     pool_raw = combined_df[mask].drop_duplicates(subset=["证券代码"], keep="first").copy()
        #     pool_raw["序号"] = range(1, len(pool_raw) + 1)
        # else:
        #     pool_raw = pd.DataFrame(columns=INTERSECTION_SOURCE_COLUMNS + ["资本运作行为"])

        # 列名重映射（原始数据不变，只改最终输出的列名）
        combined_display = combined_df.rename(columns=INTERSECTION_COLUMN_RENAME)
        # 确保列顺序
        final_columns = [c for c in INTERSECTION_DISPLAY_COLUMNS if c in combined_display.columns]
        combined_display = combined_display[final_columns]

        # Sheet2（选股池）= Sheet1 数据的完整复制
        pool_df = combined_display.copy()

        # 5. 输出 Excel（双 Sheet）
        daily_dir = self._get_daily_dir(date_str)
        os.makedirs(daily_dir, exist_ok=True)
        output_path = os.path.join(daily_dir, output_filename)

        # 生成选股池名称
        try:
            from datetime import datetime as dt
            d = dt.strptime(date_str, "%Y-%m-%d")
            pool_name = f"{d.year}年{d.month:02d}月选股池"
        except Exception:
            pool_name = f"选股池_{date_str}"

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            combined_display.to_excel(writer, sheet_name="条件交集", index=False)
            pool_df.to_excel(writer, sheet_name=pool_name, index=False)

        auto_adjust_excel_width(output_path, all_sheets=True)
        logger.info(f"[条件交集] 输出文件: {output_path}")

        # 6. 保存选股池到 DB
        try:
            pool_records = pool_df.fillna("").to_dict("records")
            await self._save_stock_pool(
                name=pool_name,
                date_str=date_str,
                file_path=output_path,
                data=pool_records,
                total_stocks=len(pool_df),
                filter_conditions=filter_conditions,
                source_types=list(filtered_dfs.keys()),
                workflow_id=workflow_id
            )
            logger.info(f"[条件交集] 选股池已保存: {pool_name}, {len(pool_df)}条")
        except Exception as e:
            logger.error(f"[条件交集] 保存选股池失败: {e}")

        base_msg = f"条件交集完成: 合并{len(combined_display)}行, 选股池{len(pool_df)}条, 来源{len(filtered_dfs)}个类型"
        if warnings_list:
            base_msg += f"（{len(warnings_list)}条警告）"
        return {
            "success": True,
            "message": base_msg,
            "data": clean_df_for_json(combined_display),
            "columns": combined_display.columns.tolist(),
            "rows": len(combined_display),
            "file_path": output_path,
            "_df": combined_display,
            "pool_count": len(pool_df),
            "warnings": warnings_list,
        }

    async def _export_ma20_trend(self, config: Dict, date_str: Optional[str] = None) -> Dict[str, Any]:
        """导出20日均线趋势步骤：复用统计分析的趋势导出逻辑（含 Excel 折线图）"""
        from services.trend_service import get_trend_data, export_trend_excel_with_chart

        date_str = config.get("date_str") or date_str or self.today
        output_filename = config.get("output_filename") or "10站上20日均线趋势.xlsx"
        date_range_start = config.get("date_range_start")
        date_range_end = config.get("date_range_end")

        logger.info(f"[导出MA20趋势] date={date_str}, range={date_range_start}~{date_range_end}")

        # 获取趋势数据（已自动排除条件交集和导出20日均线趋势类型）
        data = await get_trend_data(
            metric_type="ma20",
            start_date=date_range_start,
            end_date=date_range_end
        )

        if not data:
            return {"success": False, "message": "指定时间范围内无趋势数据"}

        # 生成带图表的 Excel
        daily_dir = self._get_daily_dir(date_str)
        os.makedirs(daily_dir, exist_ok=True)
        output_path = os.path.join(daily_dir, output_filename)

        export_trend_excel_with_chart(data, output_path)
        # 注意：xlsxwriter 生成的文件不用 openpyxl 的 auto_adjust_excel_width，会破坏图表
        logger.info(f"[导出MA20趋势] 输出文件: {output_path}, {len(data)}条数据")

        return {
            "success": True,
            "message": f"20日均线趋势导出完成，{len(data)}条数据，含折线图",
            "data": data[:100],
            "columns": list(data[0].keys()) if data else [],
            "rows": len(data),
            "file_path": output_path,
        }

    def _apply_filters(self, df: pd.DataFrame, filter_conditions: list, filter_logic: str = "AND") -> pd.DataFrame:
        """应用过滤条件：非空即保留"""
        enabled = [f for f in filter_conditions if f.get("enabled")]
        if not enabled:
            return df

        masks = []
        for f in enabled:
            col = f["column"]
            if col in df.columns:
                mask = df[col].fillna("").astype(str).str.strip() != ""
                masks.append(mask)

        if not masks:
            return df

        if filter_logic == "OR":
            combined = masks[0]
            for m in masks[1:]:
                combined = combined | m
        else:  # AND
            combined = masks[0]
            for m in masks[1:]:
                combined = combined & m

        return df[combined].copy()

    async def _save_stock_pool(self, name: str, date_str: str, file_path: str,
                                data: list, total_stocks: int,
                                filter_conditions: list, source_types: list,
                                workflow_id: int = None):
        """保存选股池到数据库（atomic upsert by name + date_str）"""
        import json as json_mod
        from core.database import AsyncSessionLocal
        from sqlalchemy import text

        params = {
            "name": name,
            "workflow_id": workflow_id,
            "date_str": date_str,
            "file_path": file_path,
            "total_stocks": total_stocks,
            "data": json_mod.dumps(data, ensure_ascii=False, default=str),
            "filter_conditions": json_mod.dumps(filter_conditions, ensure_ascii=False),
            "source_types": json_mod.dumps(source_types, ensure_ascii=False),
        }

        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                INSERT INTO stock_pools (name, workflow_id, date_str, file_path, total_stocks, data,
                    filter_conditions, source_types, is_active, created_at, updated_at)
                VALUES (:name, :workflow_id, :date_str, :file_path, :total_stocks, :data,
                    :filter_conditions, :source_types, 1, NOW(), NOW())
                AS new_row
                ON DUPLICATE KEY UPDATE
                    workflow_id = new_row.workflow_id,
                    file_path = new_row.file_path,
                    total_stocks = new_row.total_stocks,
                    data = new_row.data,
                    filter_conditions = new_row.filter_conditions,
                    source_types = new_row.source_types,
                    is_active = 1,
                    updated_at = NOW()
            """), params)
            await session.commit()

    async def _ranking_sort(self, config: Dict, input_data: Optional[pd.DataFrame] = None,
                            date_str: Optional[str] = None) -> Dict[str, Any]:
        """涨幅排名排序步骤：排序→排名→历史对比→格式化输出→自动复制到public"""
        import shutil
        import re as re_mod
        from collections import OrderedDict
        from openpyxl.styles import PatternFill, Font, Alignment as openpyxl_Alignment

        date_str = config.get("date_str") or date_str or self.today
        logger.info(f"[涨幅排名] 开始执行: date={date_str}")

        # 1. 获取输入数据
        df = input_data
        if df is None or df.empty:
            return {"success": False, "message": "无输入数据，请先执行合并步骤"}

        cols = df.columns.tolist()
        if len(cols) < 2:
            return {"success": False, "message": f"输入数据至少需要2列，当前只有{len(cols)}列"}

        sector_col = cols[0]  # 板块名称（第1列）
        sort_col_raw = cols[1]    # 排序列（第2列，固定位置）
        # 多行列名只取第一行（如 "成份区间涨跌幅(算术平均)\n[起始交易日期]..." → "成份区间涨跌幅(算术平均)"）
        sort_col_display = str(sort_col_raw).split('\n')[0].strip()
        logger.info(f"[涨幅排名] 板块列={sector_col}, 排序列={sort_col_display}")

        # 2. 提取板块名称和排序列，过滤空行，转数值排序
        work_df = df[[sector_col, sort_col_raw]].copy()
        work_df = work_df.rename(columns={sort_col_raw: sort_col_display})
        sort_col = sort_col_display
        # 过滤板块名称为空/NaN/含"妙想Choice"的行
        sector_str = work_df[sector_col].astype(str).str.strip()
        work_df = work_df[
            work_df[sector_col].notna()
            & (sector_str != '')
            & (~sector_str.str.contains('妙想Choice', na=False, regex=False))
        ]
        work_df[sort_col] = pd.to_numeric(work_df[sort_col], errors='coerce')

        # 有效数字行：降序排列；非数字行（--等）：排到末尾
        valid_df = work_df.dropna(subset=[sort_col]).copy()
        valid_df[sort_col] = valid_df[sort_col].round(2)
        valid_df = valid_df.sort_values(by=sort_col, ascending=False).reset_index(drop=True)

        invalid_df = work_df[work_df[sort_col].isna()].copy()
        invalid_df[sort_col] = df.loc[invalid_df.index, sort_col_raw]  # 索引与 df 对齐（未 reset）

        work_df = pd.concat([valid_df, invalid_df], ignore_index=True)

        if work_df.empty:
            return {"success": False, "message": "过滤后无有效数据（所有行为空/妙想Choice或排序列无数值）"}

        # 3. 列名规范化函数 + 当日日期列名
        import re as re_mod
        _col_date_map = {}  # col_name → datetime, 用于后续 Excel 表头写入实际日期值

        def normalize_col_name(c):
            """Excel 日期对象/序列号/文本 → 'X月X日' 格式，同时记录原始日期"""
            dt_val = None
            if isinstance(c, (pd.Timestamp, datetime)):
                dt_val = c if isinstance(c, datetime) else c.to_pydatetime()
            elif isinstance(c, (int, float)) and 40000 <= c <= 50000:
                try:
                    dt_val = (pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(c))).to_pydatetime()
                except Exception:
                    pass
            elif isinstance(c, str):
                m = re_mod.match(r'^(\d+)月(\d+)日$', c)
                if m:
                    month, day = int(m.group(1)), int(m.group(2))
                    year = d.year if month <= d.month else d.year - 1
                    dt_val = datetime(year, month, day)

            if dt_val:
                name = f"{dt_val.month}月{dt_val.day}日"
                _col_date_map[name] = dt_val
                return name
            return str(c)

        d = datetime.strptime(date_str, "%Y-%m-%d")
        today_col = f"{d.month}月{d.day}日"
        _col_date_map[today_col] = d

        # 4. 查找上一个工作日的 public 文件（带 mtime 缓存）
        prev_file, prev_date = self.resolver.find_previous_public_file(date_str)
        prev_data = {}  # {板块名称: {top5_count, prev_rank, history}}
        prev_history_cols = []
        prev_all_sheets = None  # {sheet_name: DataFrame} 用于多 Sheet 输出

        if prev_file and os.path.exists(prev_file):
            try:
                # mtime 缓存: key=完整文件路径, 文件更新/覆盖后 mtime 变化自动失效
                # 缓存存储 (mtime, {sheet_name: DataFrame}) 格式，涨幅排名专用
                cache_key = f"{prev_file}::all_sheets"
                current_mtime = os.path.getmtime(prev_file)
                cached = _public_file_cache.get(cache_key)
                if cached and cached[0] == current_mtime:
                    prev_all_sheets = {k: v.copy() for k, v in cached[1].items()}
                    logger.info(f"[涨幅排名] 缓存命中: {os.path.basename(prev_file)} ({len(prev_all_sheets)} sheets)")
                else:
                    prev_all_sheets = pd.read_excel(prev_file, sheet_name=None, engine="openpyxl")
                    # 缓存淘汰：超过上限时移除最早的条目
                    if len(_public_file_cache) >= _PUBLIC_FILE_CACHE_MAX:
                        oldest_key = next(iter(_public_file_cache))
                        del _public_file_cache[oldest_key]
                    _public_file_cache[cache_key] = (current_mtime, prev_all_sheets)
                    logger.info(f"[涨幅排名] 加载并缓存: {os.path.basename(prev_file)} ({len(prev_all_sheets)} sheets)")

                # 用第一个 sheet 提取排名数据
                first_sheet_name = list(prev_all_sheets.keys())[0]
                prev_raw_df = prev_all_sheets[first_sheet_name]
                # 列名规范化
                prev_cols = [normalize_col_name(c) for c in prev_raw_df.columns.tolist()]
                prev_raw_df.columns = prev_cols
                # 列结构: [板块名称, 排序列, 迄今为止排进前5(次数), 上一日期列, ...]
                if len(prev_cols) >= 4:
                    prev_history_cols = prev_cols[3:]  # 从第4列开始都是历史日期列
                    for _, row in prev_raw_df.iterrows():
                        name = str(row[prev_cols[0]]).strip()
                        top5_count = int(row[prev_cols[2]]) if pd.notna(row[prev_cols[2]]) else 0
                        prev_rank = int(row[prev_cols[3]]) if pd.notna(row[prev_cols[3]]) else None
                        history = {c: row[c] for c in prev_history_cols}
                        prev_data[name] = {
                            "top5_count": top5_count,
                            "prev_rank": prev_rank,
                            "history": history,
                        }
                logger.info(f"[涨幅排名] 历史数据: {prev_file}, {len(prev_data)}个板块")
            except Exception as e:
                logger.warning(f"[涨幅排名] 读取上一工作日文件失败: {e}")

        # 5. 构建输出
        records = []
        for idx, row in work_df.iterrows():
            rank = idx + 1
            sector = str(row[sector_col]).strip()
            sort_val = row[sort_col]

            prev = prev_data.get(sector, {"top5_count": 0, "prev_rank": None, "history": {}})

            # 迄今为止排进前5(次数)
            if rank <= 5:
                new_top5 = prev["top5_count"] + 1
            else:
                new_top5 = prev["top5_count"]

            record = OrderedDict()
            record[sector_col] = sector
            record[sort_col] = sort_val
            record["迄今为止排进前5(次数)"] = new_top5
            record[today_col] = rank

            # 附加历史列
            for hcol in prev_history_cols:
                record[hcol] = prev["history"].get(hcol, "")

            records.append(record)

        result_df = pd.DataFrame(records)

        # 6. 生成文件名
        # 从上一工作日文件最后一列提取起始日期
        start_date_str = ""
        all_cols = result_df.columns.tolist()
        if len(all_cols) > 4:
            last_col = str(all_cols[-1])  # 最后一列 = 最早的日期列，转字符串防止整数列名
            m = re_mod.search(r'(\d+)月(\d+)日', last_col)
            if m:
                start_date_str = f"{int(m.group(1)):02d}{int(m.group(2)):02d}"
        if not start_date_str:
            start_date_str = f"{d.month:02d}{d.day:02d}"

        date_no_hyphens = date_str.replace("-", "")
        default_filename = f"8涨幅排名{start_date_str}-{date_no_hyphens}.xlsx"
        output_filename = config.get("output_filename") or default_filename
        if not output_filename.endswith(".xlsx"):
            output_filename += ".xlsx"

        daily_dir = self.resolver.get_upload_directory(date_str)
        os.makedirs(daily_dir, exist_ok=True)
        output_path = os.path.join(daily_dir, output_filename)

        # 7. 保存 Excel（多 Sheet: 当日结果 + 上一工作日文件的所有 sheet）并格式化
        today_sheet = f"{d.month:02d}{d.day:02d}"
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result_df.to_excel(writer, sheet_name=today_sheet, index=False)

        wb = load_workbook(output_path)

        DEEP_RED = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")
        DEEP_RED_FONT = Font(color="FFFFFF", bold=True)
        LIGHT_RED = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
        LIGHT_RED_FONT = Font(color="FFFFFF")
        GOLD_FILL = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

        # --- 辅助函数: 对 sheet 应用通用格式（表头、列宽、第3列金色、Top5、过滤） ---
        def apply_ranking_sheet_format(ws, col_start_for_top5, max_data_row):
            from openpyxl.utils import get_column_letter
            from openpyxl.worksheet.dimensions import ColumnDimension

            # 表头格式：加粗居中，仅第3列金色；日期列头写入实际日期值
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=1, column=col_idx)
                header_text = str(cell.value or '')
                # 日期列头: 写入实际日期值 + 自定义格式显示为 "X月X日"
                if header_text in _col_date_map:
                    cell.value = _col_date_map[header_text]
                    cell.number_format = 'm"月"d"日"'
                cell.font = Font(bold=True, size=11)
                cell.alignment = openpyxl_Alignment(horizontal="center", vertical="center")
            ws.cell(row=1, column=3).fill = GOLD_FILL
            ws.cell(row=1, column=3).font = Font(bold=True, size=11)

            # 列宽
            for col_idx in range(1, ws.max_column + 1):
                letter = get_column_letter(col_idx)
                ws.column_dimensions[letter].width = 35 if col_idx in (2, 3) else 25

            # 所有数据单元格居中
            center_align = openpyxl_Alignment(horizontal="center", vertical="center")
            for row_idx in range(2, max_data_row + 1):
                for col_idx in range(1, ws.max_column + 1):
                    ws.cell(row=row_idx, column=col_idx).alignment = center_align

            # 日期列 Top5 深红
            for col_idx in range(col_start_for_top5, ws.max_column + 1):
                for row_idx in range(2, max_data_row + 1):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    try:
                        val = int(cell.value) if cell.value is not None else None
                    except (ValueError, TypeError):
                        val = None
                    if val is not None and val <= 5:
                        cell.fill = DEEP_RED
                        cell.font = DEEP_RED_FONT

            # 自动过滤
            from openpyxl.utils import get_column_letter as gcl
            last_col_letter = gcl(ws.max_column)
            ws.auto_filter.ref = f"A1:{last_col_letter}{max_data_row}"

        # --- 当日 sheet ---
        ws_today = wb[today_sheet]
        today_col_idx = result_df.columns.tolist().index(today_col) + 1
        data_row_count = len(result_df) + 1

        apply_ranking_sheet_format(ws_today, 4, data_row_count)

        # 当日列追加排名提升浅红(仅非 Top5 行)
        for row_idx in range(2, data_row_count + 1):
            rank_cell = ws_today.cell(row=row_idx, column=today_col_idx)
            try:
                rank_val = int(rank_cell.value) if rank_cell.value is not None else None
            except (ValueError, TypeError):
                rank_val = None
            if rank_val is not None and rank_val > 5:
                sector_name = str(ws_today.cell(row=row_idx, column=1).value).strip()
                prev = prev_data.get(sector_name, {})
                prev_rank = prev.get("prev_rank")
                if prev_rank is not None and rank_val < prev_rank:
                    rank_cell.fill = LIGHT_RED
                    rank_cell.font = LIGHT_RED_FONT

        wb.save(output_path)

        logger.info(f"[涨幅排名] 输出文件: {output_path}")

        # 8. 复制到当日 public 目录（不清空旧文件，同名覆盖）
        public_dir = self.resolver.get_public_directory(date_str)
        os.makedirs(public_dir, exist_ok=True)
        shutil.copy2(output_path, public_dir)
        logger.info(f"[涨幅排名] 已复制到 public: {public_dir}")

        # 9. 返回结果
        clean_df = result_df.fillna("").copy()
        preview = clean_df.head(100).to_dict("records")

        return {
            "success": True,
            "message": f"涨幅排名完成，{len(result_df)}个板块，前5名已标红",
            "data": preview,
            "columns": result_df.columns.tolist(),
            "rows": len(result_df),
            "file_path": output_path,
            "_df": result_df,
        }

    async def _pledge_trend_analysis(
        self, config: Dict, df: Optional[pd.DataFrame], date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """质押异动和趋势步骤：为每只股票查询东财 1 年质押历史，判定 3 列。

        Required: df 必须含 证券代码 / 最新公告日。锚点缺失任一行 → 整步骤失败。
        """
        from services.pledge_data_source import PledgeDataSource
        from services.pledge_trend import compute_trend
        from services.pledge_cache_cleanup import cleanup_expired_pledge_cache
        from core.redis_client import get_redis
        from utils.stock_code_normalizer import normalize_stock_code

        # 1. 校验输入
        if df is None or "证券代码" not in df.columns:
            return {"success": False, "message": "需要包含'证券代码'列的输入数据"}
        if "最新公告日" not in df.columns:
            return {"success": False, "message":
                "质押异动趋势步骤失败：输入数据缺少'最新公告日'列（或前缀'股权质押公告日期'列未被正确映射）"}

        df = df.copy()
        # 锚点严格校验：任何行缺失即整步骤失败
        anchor_series = df["最新公告日"].astype(str).str.strip()
        missing_mask = df["最新公告日"].isna() | (anchor_series == "") | (anchor_series.str.lower() == "nan")
        if missing_mask.any():
            missing_cnt = int(missing_mask.sum())
            sample_cols = [c for c in ["证券代码", "证券简称"] if c in df.columns]
            sample = df.loc[missing_mask, sample_cols].head(5).to_dict("records")
            return {"success": False, "message":
                f"质押异动趋势步骤失败：{missing_cnt} 行缺少'最新公告日'锚点，无法执行。示例: {sample}"}

        # 2. 读取配置
        trend_algo       = config.get("trend_algo", "mann_kendall")
        mk_p             = float(config.get("mk_pvalue", 0.05))
        b_rev            = int(config.get("b_max_reversals", 2))
        c_r2             = float(config.get("c_min_r2", 0.7))
        event_no_change  = float(config.get("event_no_change_threshold", 0.5))
        event_large     = float(config.get("event_large_threshold", 3.0))
        window_days      = int(config.get("window_days", 365))

        # 3. 初始化数据源
        redis_cli = get_redis()
        ds = PledgeDataSource(redis_client=redis_cli, akshare_fallback=True)

        # 4. 逐股处理
        df["持续递增（一年内）"] = ""
        df["持续递减（一年内）"] = ""
        df["质押异动"] = ""
        stats = {
            "total": len(df), "ok": 0, "empty": 0, "fail": 0,
            "by_source": {"eastmoney": 0, "cache": 0, "akshare": 0, "empty": 0},
            "by_result": {
                "持续递增": 0, "持续递减": 0, "无趋势": 0,
                "小幅转增": 0, "小幅转减": 0, "大幅激增": 0, "大幅骤减": 0,
                "本次质押趋势无变化": 0, "空": 0,
            },
        }
        fail_samples: List[Dict[str, str]] = []

        for idx, row in df.iterrows():
            raw_code = str(row["证券代码"])
            symbol = normalize_stock_code(raw_code)
            # 取纯数字部分（东财 SECURITY_CODE 是 6 位数字）
            import re
            m = re.search(r'(\d{6})', symbol)
            numeric = m.group(1) if m else symbol
            anchor = str(row["最新公告日"]).strip()[:10]
            try:
                records, source = ds.get_history(numeric, anchor, window_days)
                stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
                result = compute_trend(
                    records, anchor, trend_algo, mk_p, b_rev, c_r2,
                    event_no_change, event_large
                )
                df.at[idx, "持续递增（一年内）"] = result["持续递增（一年内）"]
                df.at[idx, "持续递减（一年内）"] = result["持续递减（一年内）"]
                df.at[idx, "质押异动"] = result["质押异动"]
                if records:
                    stats["ok"] += 1
                else:
                    stats["empty"] += 1
                if result["持续递增（一年内）"] == "Y":
                    stats["by_result"]["持续递增"] += 1
                elif result["持续递减（一年内）"] == "Y":
                    stats["by_result"]["持续递减"] += 1
                else:
                    stats["by_result"]["无趋势"] += 1
                event_key = result["质押异动"] or "空"
                stats["by_result"][event_key] = stats["by_result"].get(event_key, 0) + 1

                logger.info(
                    f"[质押异动趋势] {idx+1}/{len(df)} {symbol} {row.get('证券简称','')} "
                    f"锚点={anchor} 源={source} 历史{len(records)}条 → "
                    f"递增={result['持续递增（一年内）'] or '-'} "
                    f"递减={result['持续递减（一年内）'] or '-'} "
                    f"异动={result['质押异动'] or '-'}"
                )
            except Exception as e:
                stats["fail"] += 1
                if len(fail_samples) < 10:
                    fail_samples.append({"symbol": symbol, "error": str(e)[:120]})
                logger.warning(f"[质押异动趋势] {symbol} 失败: {e}")

        # 5. 覆盖最终输出（复用 match_sector 的文件名）
        user_filename = config.get("output_filename")
        output_filename = self.resolver.get_output_filename(
            "match_sector", date_str, user_filename
        )
        output_path = os.path.join(self._get_daily_dir(date_str), output_filename)
        df.to_excel(output_path, index=False)
        try:
            auto_adjust_excel_width(output_path)
        except Exception as e:
            logger.warning(f"[质押异动趋势] 设置列宽失败: {e}")

        # 6. 缓存清理兜底
        try:
            cleanup_expired_pledge_cache(redis_cli, max_age_days=370)
        except Exception as e:
            logger.warning(f"[质押异动趋势] 缓存清理失败（不影响主流程）: {e}")

        summary = (
            f"质押异动趋势: 共{stats['total']}只, "
            f"成功{stats['ok']}, 无历史{stats['empty']}, 失败{stats['fail']} | "
            f"源: 东财{stats['by_source']['eastmoney']}, "
            f"缓存{stats['by_source']['cache']}, "
            f"降级AkShare{stats['by_source']['akshare']}, "
            f"空{stats['by_source']['empty']}"
        )
        logger.info(f"[质押异动趋势] {summary}")

        df_clean = df.fillna("").copy()
        records_preview = df_clean.head(100).to_dict("records")
        return {
            "success": True,
            "message": summary,
            "stats": stats,
            "fail_samples": fail_samples,
            "data": records_preview,
            "columns": df.columns.tolist(),
            "rows": len(df),
            "file_path": output_path,
            "_df": df,
        }


workflow_executor = WorkflowExecutor()
