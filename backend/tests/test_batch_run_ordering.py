"""一键批量执行（batch-run）工作流排序回归测试

锁定 _sort_batch_workflow_ids 的依赖链顺序（用户确认的规则）：
1. 「当月每日新增」在「条件交集」之后；
2. 「本月AI筛选汇总」在「当月每日新增」之后（自然也在「条件交集」之后）；
3. 「本月AI筛选20日线汇总」在「当月每日新增」之后（自然也在「条件交集」之后）。

背景：_run_batch_workflows 为严格串行执行（for 循环逐个 await），
每个工作流完成后立即 save_workflow_result 落库，因此排序即实际执行顺序，
排序正确 ⇒ 依赖方执行时前置产出（条件交集产出 / 当月每日新增 final + final_ma20）
已入库可供读取。
"""

from api.workflows import _sort_batch_workflow_ids
from config.workflow_type_config import get_type_config


def _items(*pairs):
    """[(wid, type)] → [(wid, type, is_aggregation)]，is_aggregation 取自真实类型配置"""
    return [(wid, t, bool(get_type_config(t).get("is_aggregation"))) for wid, t in pairs]


def test_full_dependency_chain_regardless_of_selection_order():
    """勾选顺序完全打乱 → 仍按依赖链执行：条件交集→当月每日新增→本月AI筛选汇总→本月AI筛选20日线汇总"""
    items = _items(
        (41, "本月AI筛选20日线汇总"),
        (11, "并购重组"),
        (39, "本月AI筛选汇总"),
        (37, "当月每日新增"),
        (35, "条件交集"),
    )
    assert _sort_batch_workflow_ids(items) == [11, 35, 37, 39, 41]


def test_daily_new_after_condition_intersection():
    """规则1：当月每日新增在条件交集之后（即使勾选时条件交集在后）"""
    items = _items((37, "当月每日新增"), (35, "条件交集"))
    assert _sort_batch_workflow_ids(items) == [35, 37]


def test_ai_summary_after_daily_new_and_intersection():
    """规则2：本月AI筛选汇总在当月每日新增之后，自然也在条件交集之后"""
    items = _items((39, "本月AI筛选汇总"), (37, "当月每日新增"), (35, "条件交集"))
    assert _sort_batch_workflow_ids(items) == [35, 37, 39]

    # 仅勾选 本月AI筛选汇总 + 条件交集：汇总仍排在条件交集之后
    items = _items((39, "本月AI筛选汇总"), (35, "条件交集"))
    assert _sort_batch_workflow_ids(items) == [35, 39]


def test_ai_ma20_summary_after_daily_new_and_intersection():
    """规则3：本月AI筛选20日线汇总在当月每日新增之后，自然也在条件交集之后"""
    items = _items((41, "本月AI筛选20日线汇总"), (37, "当月每日新增"), (35, "条件交集"))
    assert _sort_batch_workflow_ids(items) == [35, 37, 41]

    # 仅勾选 本月AI筛选20日线汇总 + 条件交集：仍排在条件交集之后
    items = _items((41, "本月AI筛选20日线汇总"), (35, "条件交集"))
    assert _sort_batch_workflow_ids(items) == [35, 41]


def test_normal_workflows_first_and_keep_relative_order():
    """普通（非聚合）工作流最先执行，且保持勾选时的相对顺序"""
    items = _items(
        (35, "条件交集"),
        (12, "股权转让"),
        (39, "本月AI筛选汇总"),
        (10, "并购重组"),
        (41, "本月AI筛选20日线汇总"),
    )
    assert _sort_batch_workflow_ids(items) == [12, 10, 35, 39, 41]


def test_other_aggregations_after_dependency_chain_and_stable():
    """未登记依赖顺序的其他聚合类型（导出20日均线趋势/百日新高总趋势）排最后，同优先级保持稳定"""
    items = _items(
        (45, "百日新高总趋势"),
        (43, "导出20日均线趋势"),
        (37, "当月每日新增"),
        (35, "条件交集"),
    )
    # 45 先于 43 勾选 → 稳定排序保持 45、43 相对顺序
    assert _sort_batch_workflow_ids(items) == [35, 37, 45, 43]

    # 同优先级（均为其他聚合）保持勾选相对顺序
    items2 = _items((43, "导出20日均线趋势"), (45, "百日新高总趋势"))
    assert _sort_batch_workflow_ids(items2) == [43, 45]


def test_missing_workflow_treated_as_normal():
    """工作流不存在（type=""）→ 按普通工作流处理，排在聚合类之前"""
    items = _items((35, "条件交集"), (99, ""))
    assert _sort_batch_workflow_ids(items) == [99, 35]


def test_aggregation_flags_consistent_with_config():
    """依赖链上四个类型必须登记为 is_aggregation（否则会绕过排序当作普通工作流先执行）"""
    for t in ("条件交集", "当月每日新增", "本月AI筛选汇总", "本月AI筛选20日线汇总"):
        assert get_type_config(t).get("is_aggregation"), f"{t} 未配置 is_aggregation"
