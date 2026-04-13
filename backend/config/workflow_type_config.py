WORKFLOW_TYPE_CONFIG = {
    "": {
        "display_name": "并购重组",
        "base_subdir": "",
        "directories": {
            "upload_date": "{date}",
            "public": "2025public",
        },
        "naming": {
            "output_template": "{type_display}{date}.xlsx",
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
            "output_template": "{type_display}{date}.xlsx",
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
            "output_template": "股权转让{date}.xlsx",
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
}

TYPE_ALIASES = {}


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
