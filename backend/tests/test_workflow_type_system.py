import pytest
import os
import tempfile
from datetime import datetime

from config.workflow_type_config import (
    WORKFLOW_TYPE_CONFIG,
    get_type_config,
    get_available_types,
    TYPE_ALIASES
)
from services.path_resolver import (
    WorkflowPathResolver,
    get_resolver
)


class TestWorkflowTypeConfig:
    def test_default_type_config_exists(self):
        assert "" in WORKFLOW_TYPE_CONFIG
        default_config = WORKFLOW_TYPE_CONFIG[""]
        assert default_config["display_name"] == "并购重组"
        assert default_config["base_subdir"] == ""

    def test_finance_type_config_exists(self):
        assert "股权转让" in WORKFLOW_TYPE_CONFIG
        finance_config = WORKFLOW_TYPE_CONFIG["股权转让"]
        assert finance_config["display_name"] == "股权转让"
        assert finance_config["base_subdir"] == "股权转让"

    def test_get_type_config_with_empty_string(self):
        config = get_type_config("")
        assert config["display_name"] == "并购重组"

    def test_get_type_config_with_none(self):
        config = get_type_config(None)
        assert config["display_name"] == "并购重组"

    def test_get_type_config_with_merge_reorg(self):
        config = get_type_config("并购重组")
        assert config["display_name"] == "并购重组"

    def test_get_type_config_with_finance(self):
        config = get_type_config("股权转让")
        assert config["display_name"] == "股权转让"

    def test_get_type_config_with_unknown_type_fallback(self):
        config = get_type_config("未知类型")
        assert config["display_name"] == "并购重组"

    def test_get_available_types(self):
        types = get_available_types()
        assert len(types) >= 1
        type_values = [t["value"] for t in types]
        assert "股权转让" in type_values

    def test_alias_mapping(self):
        TYPE_ALIASES["旧名称"] = "股权转让"
        config = get_type_config("旧名称")
        assert config["display_name"] == "股权转让"
        TYPE_ALIASES.pop("旧名称", None)


class TestPathResolverDefaultType:
    @pytest.fixture
    def resolver(self):
        return WorkflowPathResolver(base_dir="/test/base", workflow_type="")

    def test_get_base_dir(self, resolver):
        assert resolver.get_base_dir() == "/test/base"

    def test_get_upload_directory(self, resolver):
        upload_dir = resolver.get_upload_directory("2026-04-09")
        assert upload_dir == "/test/base/2026-04-09"

    def test_get_public_directory(self, resolver):
        public_dir = resolver.get_public_directory()
        assert public_dir == "/test/base/2025public"

    def test_get_match_source_directory(self, resolver):
        high_price_dir = resolver.get_match_source_directory("match_high_price")
        assert high_price_dir == "/test/base/百日新高"

        ma20_dir = resolver.get_match_source_directory("match_ma20")
        assert ma20_dir == "/test/base/20日均线"

    def test_get_output_filename_merge_excel_default(self, resolver):
        filename = resolver.get_output_filename("merge_excel", "2026-04-09")
        assert filename == "total_1.xlsx"

    def test_get_output_filename_smart_dedup_default(self, resolver):
        filename = resolver.get_output_filename("smart_dedup", "2026-04-09")
        assert filename == "deduped.xlsx"

    def test_get_output_filename_match_sector_final(self, resolver):
        filename = resolver.get_output_filename("match_sector", "2026-04-09")
        assert filename == "1并购重组20260409.xlsx"


class TestPathResolverFinanceType:
    @pytest.fixture
    def resolver(self):
        return WorkflowPathResolver(base_dir="/test/base", workflow_type="股权转让")

    def test_get_upload_directory(self, resolver):
        upload_dir = resolver.get_upload_directory("2026-04-09")
        assert upload_dir == "/test/base/股权转让/2026-04-09"

    def test_get_public_directory(self, resolver):
        public_dir = resolver.get_public_directory()
        assert public_dir == "/test/base/股权转让/public"

    def test_get_match_source_directory_same_as_default(self, resolver):
        high_price_dir = resolver.get_match_source_directory("match_high_price")
        assert high_price_dir == "/test/base/百日新高"

    def test_get_output_filename_match_sector_final(self, resolver):
        filename = resolver.get_output_filename("match_sector", "2026-04-09")
        assert filename == "2股权转让20260409.xlsx"

    def test_get_daily_dir_compatibility(self, resolver):
        daily_dir = resolver.get_daily_dir("2026-04-10")
        assert daily_dir == "/test/base/股权转让/2026-04-10"


class TestOutputFilenamePriority:
    @pytest.fixture
    def resolver(self):
        return WorkflowPathResolver(base_dir="/test/base", workflow_type="股权转让")

    def test_user_specified_takes_priority_for_intermediate_steps(self, resolver):
        user_filename = "custom_dedup_v2.xlsx"
        filename = resolver.get_output_filename(
            step_type="smart_dedup",
            date_str="2026-04-09",
            user_specified=user_filename
        )
        assert filename == user_filename

    def test_user_specified_ignored_for_final_step(self, resolver):
        """match_sector 的 user_specified 现也生效（与中间步骤一致）。"""
        user_filename = "custom_final.xlsx"
        filename = resolver.get_output_filename(
            step_type="match_sector",
            date_str="2026-04-09",
            user_specified=user_filename
        )
        assert filename == user_filename

    def test_empty_user_specified_uses_default(self, resolver):
        filename = resolver.get_output_filename(
            step_type="merge_excel",
            date_str="2026-04-09",
            user_specified=""
        )
        assert filename == "total_1.xlsx"

    def test_none_user_specified_uses_default(self, resolver):
        filename = resolver.get_output_filename(
            step_type="merge_excel",
            date_str="2026-04-09",
            user_specified=None
        )
        assert filename == "total_1.xlsx"


class TestGetResolverFactory:
    def test_resolver_caching(self):
        resolver1 = get_resolver("/test/base", "股权转让")
        resolver2 = get_resolver("/test/base", "股权转让")
        assert resolver1 is resolver2

    def test_different_types_different_resolvers(self):
        resolver1 = get_resolver("/test/base", "")
        resolver2 = get_resolver("/test/base", "股权转让")
        assert resolver1 is not resolver2


class TestIntegrationScenarios:
    def test_full_workflow_path_generation_default_type(self):
        resolver = WorkflowPathResolver("/data/excel", "")
        date = "2026-04-09"

        merge_input_dir = resolver.get_upload_directory(date)
        assert merge_input_dir == f"/data/excel/{date}"

        public_dir = resolver.get_public_directory()
        assert public_dir == "/data/excel/2025public"

        final_output = resolver.get_output_filename("match_sector", date)
        assert final_output == "1并购重组20260409.xlsx"

    def test_full_workflow_path_generation_finance_type(self):
        resolver = WorkflowPathResolver("/data/excel", "股权转让")
        date = "2026-04-09"

        merge_input_dir = resolver.get_upload_directory(date)
        assert merge_input_dir == f"/data/excel/股权转让/{date}"

        public_dir = resolver.get_public_directory()
        assert public_dir == "/data/excel/股权转让/public"

        final_output = resolver.get_output_filename("match_sector", date)
        assert final_output == "2股权转让20260409.xlsx"

    def test_match_sources_shared_between_types(self):
        default_resolver = WorkflowPathResolver("/data/excel", "")
        finance_resolver = WorkflowPathResolver("/data/excel", "股权转让")

        for step_type in ["match_high_price", "match_ma20", "match_soe", "match_sector"]:
            default_dir = default_resolver.get_match_source_directory(step_type)
            finance_dir = finance_resolver.get_match_source_directory(step_type)
            assert default_dir == finance_dir, f"{step_type} 源目录应该相同"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
