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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
            "match_high_price": "百日新高",
            "match_ma20": "20日均线",
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
        "default_filters": [{"column": "百日新高", "enabled": True}],
        "default_type_order": [
            "并购重组", "股权转让", "增发实现",
            "申报并购重组", "减持叠加质押和大宗交易",
            "质押",
            "招投标"
        ],
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
            "output_template": "10站上20日均线趋势.xlsx",
        },
        "match_sources": {},
        "allowed_steps": ["export_ma20_trend"],
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
INTERSECTION_SOURCE_COLUMNS = ["序号", "证券代码", "证券简称", "最新公告日", "百日新高", "20日均线", "国企", "一级板块"]
INTERSECTION_COLUMN_RENAME = {
    "20日均线": "站上20日线",
    "国企": "国央企",
    "一级板块": "所属板块",
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
