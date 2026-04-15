import os
import glob
import shutil
import logging
from datetime import datetime, timedelta
from typing import Optional

from config.workflow_type_config import get_type_config

logger = logging.getLogger(__name__)


class WorkflowPathResolver:
    def __init__(self, base_dir: str, workflow_type: str = ""):
        self.base_dir = base_dir
        self.workflow_type = workflow_type
        self.config = get_type_config(workflow_type)

    def get_base_dir(self) -> str:
        base_subdir = self.config.get("base_subdir", "")
        if base_subdir:
            return os.path.join(self.base_dir, base_subdir)
        return self.base_dir

    def get_upload_directory(self, date_str: str = None) -> str:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        dir_template = self.config["directories"]["upload_date"]
        dir_path = dir_template.format(date=date_str)

        return os.path.join(self.base_dir, dir_path)

    def get_public_directory(self) -> str:
        public_template = self.config["directories"]["public"]
        return os.path.join(self.base_dir, public_template)

    def get_output_filename(
        self,
        step_type: str,
        date_str: str = None,
        user_specified: str = None
    ) -> str:
        if step_type == "match_sector":
            return self._generate_final_output_name(date_str)

        if user_specified and user_specified.strip():
            return user_specified.strip()

        naming_config = self.config.get("naming", {})
        output_map = {
            "merge_excel": naming_config.get("merge_output", "total_1.xlsx"),
            "smart_dedup": naming_config.get("dedup_output", "deduped.xlsx"),
            "extract_columns": naming_config.get("extract_output", "output_2.xlsx"),
            "match_high_price": naming_config.get("match_high_price_output", "output_3.xlsx"),
            "match_ma20": naming_config.get("match_ma20_output", "output_4.xlsx"),
            "match_soe": naming_config.get("match_soe_output", "output_5.xlsx"),
        }

        return output_map.get(step_type, f"output_{step_type}.xlsx")

    def _generate_final_output_name(self, date_str: str = None) -> str:
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        template = self.config["naming"].get("output_template", "{date}.xlsx")
        display_name = self.config.get("display_name", "")

        return template.format(
            type_display=display_name,
            date=date_str.replace("-", "")
        )

    def get_match_source_directory(self, step_type: str, date_str: str = None) -> str:
        match_sources = self.config.get("match_sources", {})
        source_dir = match_sources.get(step_type, step_type)
        if date_str:
            return os.path.join(self.base_dir, date_str, source_dir)
        return os.path.join(self.base_dir, source_dir)

    def get_daily_dir(self, date_str: str = None) -> str:
        return self.get_upload_directory(date_str)

    def ensure_match_source_files(self, step_type: str, date_str: str) -> str:
        """确保匹配源目录存在且有文件。目录不存在时自动创建并从历史复制；已存在则不动。"""
        target_dir = self.get_match_source_directory(step_type, date_str)

        # 目录已存在 → 不论是否有文件，都不自动复制（用户可能主动清空过）
        if os.path.isdir(target_dir):
            existing = glob.glob(os.path.join(target_dir, "*.xlsx")) + glob.glob(os.path.join(target_dir, "*.xls"))
            if existing:
                logger.info(f"匹配源目录已有文件: {target_dir} ({len(existing)}个)")
            return target_dir

        # 目录不存在 → 创建并从历史日期递减查找复制
        os.makedirs(target_dir, exist_ok=True)

        # 从历史日期递减查找
        match_sources = self.config.get("match_sources", {})
        source_name = match_sources.get(step_type, step_type)
        try:
            base_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"日期格式无效: {date_str}")
            return target_dir

        for i in range(1, 31):
            prev_date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
            prev_dir = os.path.join(self.base_dir, prev_date, source_name)
            if not os.path.isdir(prev_dir):
                continue
            prev_files = glob.glob(os.path.join(prev_dir, "*.xlsx")) + glob.glob(os.path.join(prev_dir, "*.xls"))
            if prev_files:
                for f in prev_files:
                    shutil.copy2(f, target_dir)
                logger.info(f"从 {prev_dir} 复制 {len(prev_files)} 个文件到 {target_dir}")
                return target_dir

        logger.warning(f"匹配源目录为空且30天内无历史数据可复制: {target_dir} (step={step_type}, date={date_str})")
        return target_dir


_resolvers = {}


def get_resolver(base_dir: str, workflow_type: str = "") -> WorkflowPathResolver:
    key = f"{base_dir}_{workflow_type}"
    if key not in _resolvers:
        _resolvers[key] = WorkflowPathResolver(base_dir, workflow_type)
    return _resolvers[key]
