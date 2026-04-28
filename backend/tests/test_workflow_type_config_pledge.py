"""阶段1 验收：质押工作流类型注册 + PathResolver 输出文件名。"""
from config.workflow_type_config import (
    WORKFLOW_TYPE_CONFIG, get_type_config, get_available_types,
)
from services.path_resolver import WorkflowPathResolver


def test_pledge_type_registered():
    """质押类型必须存在于 WORKFLOW_TYPE_CONFIG。"""
    assert "质押" in WORKFLOW_TYPE_CONFIG
    cfg = WORKFLOW_TYPE_CONFIG["质押"]
    assert cfg["display_name"] == "质押"
    assert cfg["base_subdir"] == "质押"
    assert cfg["directories"]["upload_date"] == "质押/{date}"
    assert cfg["directories"]["public"] == "质押/public"
    assert cfg["naming"]["output_template"] == "5质押{date}.xlsx"


def test_pledge_match_sources_inherit_standard():
    """质押的 match_sources 与其他类型一致（百日新高/20日均线/国企/一级板块）。
    百日新高/20日均线 升级为 dict 形态以支持 auto_copy=False（禁用历史回溯复制）。
    """
    cfg = WORKFLOW_TYPE_CONFIG["质押"]
    assert cfg["match_sources"] == {
        "match_high_price": {"dir": "百日新高", "auto_copy": False},
        "match_ma20": {"dir": "20日均线", "auto_copy": False},
        "match_soe": "国企",
        "match_sector": "一级板块",
    }


def test_pledge_allowed_steps_includes_trend_analysis():
    """质押的 allowed_steps 含 pledge_trend_analysis。"""
    cfg = WORKFLOW_TYPE_CONFIG["质押"]
    assert "pledge_trend_analysis" in cfg["allowed_steps"]
    for base in ["merge_excel", "smart_dedup", "extract_columns",
                 "match_high_price", "match_ma20", "match_soe", "match_sector"]:
        assert base in cfg["allowed_steps"]


def test_get_type_config_returns_pledge():
    """get_type_config('质押') 返回正确配置。"""
    cfg = get_type_config("质押")
    assert cfg["display_name"] == "质押"


def test_default_type_order_contains_pledge_between_reduce_and_bid():
    """条件交集 default_type_order 中，质押位于减持叠加 之后、招投标 之前。"""
    order = WORKFLOW_TYPE_CONFIG["条件交集"]["default_type_order"]
    assert "质押" in order
    assert order.index("减持叠加质押和大宗交易") < order.index("质押")
    assert order.index("质押") < order.index("招投标")


def test_available_types_includes_pledge():
    """get_available_types() 返回列表含 质押。"""
    types = get_available_types()
    values = [t["value"] for t in types]
    assert "质押" in values


def test_path_resolver_final_output_filename():
    """PathResolver 针对质押的最终输出文件名 = 5质押{date_nohyphen}.xlsx。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake_base", workflow_type="质押")
    fname = resolver.get_output_filename("match_sector", date_str="2026-04-20")
    assert fname == "5质押20260420.xlsx"


def test_path_resolver_upload_directory():
    """PathResolver 上传目录 = 质押/{date}。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake_base", workflow_type="质押")
    d = resolver.get_upload_directory(date_str="2026-04-20")
    assert d.endswith("/质押/2026-04-20")


def test_path_resolver_public_directory():
    """PathResolver public 目录 = 质押/public。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake_base", workflow_type="质押")
    d = resolver.get_public_directory(date_str="2026-04-20")
    assert d.endswith("/质押/public")


def test_path_resolver_match_sector_user_specified_takes_precedence():
    """修正前 match_sector 忽略 user_specified；修正后 user_specified 生效。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake_base", workflow_type="质押")
    # 无 user_specified → 模板生成
    assert resolver.get_output_filename("match_sector", "2026-04-20") == "5质押20260420.xlsx"
    # 有 user_specified → 返回用户自定义
    assert resolver.get_output_filename("match_sector", "2026-04-20",
                                         user_specified="自定义.xlsx") == "自定义.xlsx"
    # 空白 user_specified 被忽略，走模板
    assert resolver.get_output_filename("match_sector", "2026-04-20",
                                         user_specified="   ") == "5质押20260420.xlsx"


def test_path_resolver_match_sector_user_specified_other_type():
    """同样的 user_specified 规则对并购重组/股权转让/增发实现 等其他类型也生效。"""
    resolver = WorkflowPathResolver(base_dir="/tmp/fake_base", workflow_type="股权转让")
    assert resolver.get_output_filename("match_sector", "2026-04-20") == "2股权转让20260420.xlsx"
    assert resolver.get_output_filename("match_sector", "2026-04-20",
                                         user_specified="myfile.xlsx") == "myfile.xlsx"
