import os
from datetime import datetime
from typing import Optional

from config.workflow_type_config import get_type_config


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

    def get_match_source_directory(self, step_type: str) -> str:
        match_sources = self.config.get("match_sources", {})
        source_dir = match_sources.get(step_type, step_type)
        return os.path.join(self.base_dir, source_dir)

    def get_daily_dir(self, date_str: str = None) -> str:
        return self.get_upload_directory(date_str)


_resolvers = {}


def get_resolver(base_dir: str, workflow_type: str = "") -> WorkflowPathResolver:
    key = f"{base_dir}_{workflow_type}"
    if key not in _resolvers:
        _resolvers[key] = WorkflowPathResolver(base_dir, workflow_type)
    return _resolvers[key]
