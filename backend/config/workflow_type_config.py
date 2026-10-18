WORKFLOW_TYPE_CONFIG = {
    "": {
        "display_name": "并购重组",
        "base_subdir": "",
        "directories": {
            "upload_date": "{date}",
            "public": "2025public",
        },
        "naming": {
            "output_template": "1并购重组{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "并购重组": {
        "display_name": "并购重组",
        "base_subdir": "",
        "directories": {
            "upload_date": "{date}",
            "public": "2025public",
        },
        "naming": {
            "output_template": "1并购重组{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "股权转让": {
        "display_name": "股权转让",
        "base_subdir": "股权转让",
        "directories": {
            "upload_date": "股权转让/{date}",
            "public": "股权转让/public",
        },
        "naming": {
            "output_template": "2股权转让{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "增发实现": {
        "display_name": "增发实现",
        "base_subdir": "增发实现",
        "directories": {
            "upload_date": "增发实现/{date}",
            "public": "增发实现/public",
        },
        "naming": {
            "output_template": "3增发实现{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "申报并购重组": {
        "display_name": "申报并购重组",
        "base_subdir": "申报并购重组",
        "directories": {
            "upload_date": "申报并购重组/{date}",
            "public": "申报并购重组/public",
        },
        "naming": {
            "output_template": "4申报并购重组{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "质押": {
        "display_name": "质押",
        "base_subdir": "质押",
        "public_skiprows": 0,
        "directories": {
            "upload_date": "质押/{date}",
            "public": "质押/public",
        },
        "naming": {
            "output_template": "5质押{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        },
        "allowed_steps": [
            "merge_excel", "smart_dedup", "extract_columns",
            "match_high_price", "match_ma20", "match_soe", "match_sector",
            "pledge_trend_analysis",
        ],
    },

    "减持叠加质押和大宗交易": {
        "display_name": "减持叠加质押和大宗交易",
        "base_subdir": "减持叠加质押和大宗交易",
        "directories": {
            "upload_date": "减持叠加质押和大宗交易/{date}",
            "public": "减持叠加质押和大宗交易/public",
        },
        "naming": {
            "output_template": "6减持叠加质押和大宗交易{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "招投标": {
        "display_name": "招投标",
        "base_subdir": "招投标",
        "public_skiprows": 0,
        "directories": {
            "upload_date": "招投标/{date}",
            "public": "招投标/public",
        },
        "naming": {
            "output_template": "9招投标{date}.xlsx",
            "merge_output": "total_1.xlsx",
            "dedup_output": "deduped.xlsx",
            "extract_output": "output_2.xlsx",
            "match_high_price_output": "output_3.xlsx",
            "match_ma20_output": "output_4.xlsx",
            "match_soe_output": "output_5.xlsx",
        },
        "match_sources": {
            "match_high_price": {"dir": "百日新高", "auto_copy": False},
            "match_ma20": {"dir": "20日均线", "auto_copy": False},
            "match_soe": "国企",
            "match_sector": "一级板块",
        }
    },

    "条件交集": {
        "display_name": "条件交集",
        "base_subdir": "条件交集",
        "is_aggregation": True,
        "directories": {
            "upload_date": "条件交集/{date}",
            "public": "",
        },
        "naming": {
            "output_template": "7条件交集{date}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["condition_intersection"],
        "filter_columns": ["百日新高", "20日均线", "国企", "一级板块"],
        "default_filters": [{"column": "百日新高并行20日均线", "enabled": True}],
        "default_type_order": [
            "并购重组", "股权转让", "增发实现",
            "申报并购重组", "减持叠加质押和大宗交易",
            "质押",
            "招投标"
        ],
        "parallel_output_templates": {
            "main": "7条件交集{date}.xlsx",
            "high_price_codes": "7条件交集{date}百日新高证券代码.xlsx",
            "ma20_codes": "7条件交集{date}站上20日线证券代码.xlsx",
        },
    },

    "当月每日新增": {
        "display_name": "当月每日新增",
        "base_subdir": "当月每日新增",
        "is_aggregation": True,
        # 注意：不再 is_export_only —— 双 sheet 均写入 workflow_results：
        # 首 sheet「当月每日新增」存 step_type='final'（save_workflow_result 主流程，
        # 供「本月AI筛选汇总」读取）；第 2 个 sheet「20日线」存 step_type='final_ma20'
        # （save_workflow_result 追加写入，供「本月AI筛选20日线汇总」DB优先读取）
        "directories": {
            # 数据目录按月组织（非日期目录，由 monthly_daily_new 步骤内直接生成）：
            # 当月每日新增/2026年10月新增/17 10月新增1010.xlsx
            "upload_date": "当月每日新增/{month_dir}",
            "public": "",
        },
        "naming": {
            # 文档性配置：实际输出名由 monthly_daily_new 步骤生成
            # 默认 "17 {month}月新增{mmdd}.xlsx"（如 17 10月新增1010.xlsx），
            # 单文件双 sheet："当月每日新增"=百日新高新增（J列）、"20日线"=站上20日线新增（K列）
            "output_template": "17 {month}月新增{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["monthly_daily_new"],
    },

    "本月AI筛选汇总": {
        "display_name": "本月AI筛选汇总",
        "base_subdir": "本月AI筛选汇总",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            # 输出按月落到根目录 data/excel/{YYYY-MM}/（由 monthly_ai_summary 步骤内直接生成），
            # 如 data/excel/2026-10/16 10月AI筛选汇总1009.xlsx
            "upload_date": "{month_root}",
            "public": "",
        },
        "naming": {
            # 默认 "16 {month}月AI筛选汇总{mmdd}.xlsx"（月份不补零、MMDD补零），如 16 10月AI筛选汇总1009.xlsx
            "output_template": "16 {month}月AI筛选汇总{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["monthly_ai_summary"],
    },

    "本月AI筛选20日线汇总": {
        "display_name": "本月AI筛选20日线汇总",
        "base_subdir": "本月AI筛选20日线汇总",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            # 输出按月落到专属目录 data/excel/本月AI筛选20日线汇总/{YYYY-MM}/
            # （由 monthly_ai_ma20_summary 步骤内直接生成），
            # 如 data/excel/本月AI筛选20日线汇总/2026-10/19 10月AI筛选20日线汇总1012.xlsx
            "upload_date": "本月AI筛选20日线汇总/{month_root}",
            "public": "",
        },
        "naming": {
            # 默认 "19 {month}月AI筛选20日线汇总{mmdd}.xlsx"（月份不补零、MMDD补零），如 19 10月AI筛选20日线汇总1012.xlsx
            "output_template": "19 {month}月AI筛选20日线汇总{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["monthly_ai_ma20_summary"],
    },

    # ==============================================================
    # 本周类工作流（13/14/18号表）：执行顺序均在「条件交集」之后；
    # 输出目录为数据日期目录下的专属子目录（35天回溯编辑，见 services/weekly_common.py）
    # ==============================================================
    "本周20日线新高": {
        "display_name": "本周20日线新高",
        "base_subdir": "本周20日线新高",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            # 输出 data/excel/{date}/本周20日收盘价新高输出/13 占20日线无振幅{mmdd}.xlsx
            # 数据源为公共上传目录 data/excel/{date}/本周20日收盘价新高/
            "upload_date": "{date}/本周20日收盘价新高输出",
            "public": "",
        },
        "naming": {
            "output_template": "13 占20日线无振幅{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["weekly_ma20_close_high"],
    },

    "本周总市值千亿新高": {
        "display_name": "本周总市值千亿新高",
        "base_subdir": "本周总市值千亿新高",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            # 输出 data/excel/{date}/本周总市值千亿新高输出/14 总市值大于1000亿 本周最高价格大于上周最高价格{mmdd}.xlsx
            # 数据源为公共上传目录 data/excel/{date}/本周总市值千亿新高/
            # 附带输出 20号表 data/excel/{date}/20号表本周总市值千亿新高A列/
            "upload_date": "{date}/本周总市值千亿新高输出",
            "public": "",
        },
        "naming": {
            "output_template": "14 总市值大于1000亿 本周最高价格大于上周最高价格{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["weekly_mv1000_high"],
    },

    "全部A股总市值大于800亿": {
        "display_name": "全部A股总市值大于800亿",
        "base_subdir": "全部A股总市值大于800亿",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            # 输出 data/excel/{date}/全部A股800亿输出/18 全部A股总市值大于800亿{mmdd}.xlsx
            # 数据源为公共上传目录 data/excel/{date}/全部A股800亿/
            "upload_date": "{date}/全部A股800亿输出",
            "public": "",
        },
        "naming": {
            "output_template": "18 全部A股总市值大于800亿{mmdd}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["all_a_800"],
    },

    "导出20日均线趋势": {
        "display_name": "导出20日均线趋势",
        "base_subdir": "导出20日均线趋势",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            "upload_date": "导出20日均线趋势/{date}",
            "public": "",
        },
        "naming": {
            "output_template": "10站上20日均线趋势{date}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["export_ma20_trend"],
    },

    "百日新高总趋势": {
        "display_name": "百日新高总趋势",
        "base_subdir": "百日新高总趋势",
        "is_aggregation": True,
        "is_export_only": True,
        "directories": {
            "upload_date": "百日新高总趋势/{date}",
            "public": "",
        },
        "naming": {
            "output_template": "11百日新高趋势图{date}.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["export_high_price_trend"],
    },

    "涨幅排名": {
        "display_name": "涨幅排名",
        "base_subdir": "涨幅排名",
        "skip_public_in_merge": True,
        "date_aware_public": True,
        "directories": {
            "upload_date": "涨幅排名/{date}",
            "public": "涨幅排名/{date}/public",
        },
        "naming": {
            "merge_output": "total_1.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["merge_excel", "ranking_sort"],
    },
}

TYPE_ALIASES = {}

# 条件交集输出列配置
INTERSECTION_SOURCE_COLUMNS = ["序号", "证券代码", "证券简称", "最新公告日", "百日新高", "20日均线", "国企", "所属板块"]
INTERSECTION_COLUMN_RENAME = {
    "20日均线": "站上20日线",
    "国企": "国央企",
}
INTERSECTION_DISPLAY_COLUMNS = ["序号", "证券代码", "证券简称", "最新公告日", "百日新高", "站上20日线", "国央企", "所属板块", "资本运作行为"]


def get_type_config(workflow_type: str) -> dict:
    if not workflow_type or workflow_type == "并购重组":
        return WORKFLOW_TYPE_CONFIG[""]

    resolved_type = TYPE_ALIASES.get(workflow_type, workflow_type)

    if resolved_type in WORKFLOW_TYPE_CONFIG:
        return WORKFLOW_TYPE_CONFIG[resolved_type]

    return WORKFLOW_TYPE_CONFIG[""]


def get_available_types() -> list:
    types = []
    for type_key, config in WORKFLOW_TYPE_CONFIG.items():
        if type_key:
            types.append({
                "value": type_key,
                "display_name": config.get("display_name", type_key)
            })
    return sorted(types, key=lambda x: x["display_name"])
