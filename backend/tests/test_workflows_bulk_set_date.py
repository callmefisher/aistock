"""测试 PUT /workflows/bulk-set-date 批量同步日期端点"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.models import Workflow


class TestBulkSetDate:
    """PUT /api/v1/workflows/bulk-set-date 测试"""

    @pytest.mark.asyncio
    async def test_updates_all_workflow_dates_and_step_configs(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """所有工作流的 date_str 和 steps[].config.date_str 同步更新"""
        wf1 = Workflow(
            name="测试并购", workflow_type="并购重组", date_str="2026-04-20",
            steps=[
                {"type": "merge_excel", "config": {"date_str": "2026-04-20"}},
                {"type": "match_high_price", "config": {"date_str": "2026-04-20"}},
            ],
        )
        wf2 = Workflow(
            name="测试质押", workflow_type="质押", date_str="2026-04-20",
            steps=[{"type": "merge_excel", "config": {"date_str": "2026-04-20"}}],
        )
        db_session.add_all([wf1, wf2])
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] >= 2

        # 重新查询数据库
        result = await db_session.execute(select(Workflow))
        wfs = result.scalars().all()
        for wf in wfs:
            assert wf.date_str == "2026-04-23"
            for step in wf.steps:
                assert step["config"]["date_str"] == "2026-04-23"

    @pytest.mark.asyncio
    async def test_rejects_invalid_date_format(
        self, client: AsyncClient, auth_headers: dict
    ):
        """日期格式非法 → 422 或 400"""
        for bad in ["2026/04/23", "26-4-23", "abc", ""]:
            response = await client.put(
                "/api/v1/workflows/bulk-set-date",
                headers=auth_headers,
                json={"date_str": bad},
            )
            assert response.status_code == 400, f"{bad!r} 应被拒绝，实际 {response.status_code}"

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        """未登录 → 401"""
        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_workflows_returns_zero(
        self, client: AsyncClient, auth_headers: dict
    ):
        """无工作流 → updated_count=0，success=True"""
        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["updated_count"] == 0

    @pytest.mark.asyncio
    async def test_does_not_mutate_already_up_to_date(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """工作流 date 已是目标值 → 不计入 updated_count"""
        wf = Workflow(
            name="已最新", workflow_type="并购重组", date_str="2026-04-23",
            steps=[{"type": "merge_excel", "config": {"date_str": "2026-04-23"}}],
        )
        db_session.add(wf)
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200
        assert response.json()["updated_count"] == 0

    @pytest.mark.asyncio
    async def test_syncs_condition_intersection_period_end(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """条件交集 high_price_periods[].end 随日期同步更新，start 保持不动"""
        wf = Workflow(
            name="条件交集-测试", workflow_type="条件交集", date_str="2026-04-20",
            steps=[{
                "type": "condition_intersection",
                "config": {
                    "date_str": "2026-04-20",
                    "high_price_periods": [
                        {"start": "2026-03-18", "end": "2026-04-20"},
                        {"start": "2026-02-01", "end": "2026-04-20"},
                    ],
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        periods = refreshed.steps[0]["config"]["high_price_periods"]
        assert periods[0]["start"] == "2026-03-18"  # start 不变
        assert periods[0]["end"] == "2026-04-23"
        assert periods[1]["start"] == "2026-02-01"
        assert periods[1]["end"] == "2026-04-23"

    @pytest.mark.asyncio
    async def test_period_end_already_target_not_counted_twice(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """period.end 已经是目标日期 → 不重复计入 updated_count"""
        wf = Workflow(
            name="条件交集-已最新", workflow_type="条件交集", date_str="2026-04-23",
            steps=[{
                "type": "condition_intersection",
                "config": {
                    "date_str": "2026-04-23",
                    "high_price_periods": [
                        {"start": "2026-03-18", "end": "2026-04-23"},
                    ],
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200
        assert response.json()["updated_count"] == 0

    @pytest.mark.asyncio
    async def test_non_intersection_workflow_has_no_periods(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """非条件交集工作流的 step 不应被误加 high_price_periods 字段"""
        wf = Workflow(
            name="并购重组-无周期", workflow_type="并购重组", date_str="2026-04-20",
            steps=[{"type": "merge_excel", "config": {"date_str": "2026-04-20"}}],
        )
        db_session.add(wf)
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        assert "high_price_periods" not in cfg

    @pytest.mark.asyncio
    async def test_trend_preset_1y_reanchors_date_range(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """趋势类工作流 preset=1y 时，date_range_start/end 以新 date_str 为锚点重算"""
        wf = Workflow(
            name="A11百日新高趋势", workflow_type="百日新高总趋势", date_str="2026-04-20",
            steps=[{
                "type": "export_high_price_trend",
                "config": {
                    "date_str": "2026-04-20",
                    "date_preset": "1y",
                    "date_range_start": "2025-04-20",
                    "date_range_end": "2026-04-20",
                    "output_filename": "11百日新高趋势图2026-04-20.xlsx",
                    "_actual_output": "11百日新高趋势图2026-04-20.xlsx",
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        response = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )
        assert response.status_code == 200

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        assert cfg["date_str"] == "2026-04-23"
        assert cfg["date_range_start"] == "2025-04-23"
        assert cfg["date_range_end"] == "2026-04-23"
        assert cfg["output_filename"] == ""
        assert cfg["_actual_output"] == ""

    @pytest.mark.asyncio
    async def test_trend_preset_6m_reanchors_date_range(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """preset=6m 按 6 个月重算"""
        wf = Workflow(
            name="A10站上20日均线趋势", workflow_type="导出20日均线趋势", date_str="2026-04-20",
            steps=[{
                "type": "export_ma20_trend",
                "config": {
                    "date_str": "2026-04-20",
                    "date_preset": "6m",
                    "date_range_start": "2025-10-20",
                    "date_range_end": "2026-04-20",
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        assert cfg["date_range_start"] == "2025-10-23"
        assert cfg["date_range_end"] == "2026-04-23"

    @pytest.mark.asyncio
    async def test_trend_preset_custom_not_touched(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """preset=custom 时尊重用户手动设置的固定范围，date_range 不动"""
        wf = Workflow(
            name="A11自定义范围", workflow_type="百日新高总趋势", date_str="2026-04-20",
            steps=[{
                "type": "export_high_price_trend",
                "config": {
                    "date_str": "2026-04-20",
                    "date_preset": "custom",
                    "date_range_start": "2026-01-01",
                    "date_range_end": "2026-03-31",
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-23"},
        )

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        # date_str 更新
        assert cfg["date_str"] == "2026-04-23"
        # custom 范围不动
        assert cfg["date_range_start"] == "2026-01-01"
        assert cfg["date_range_end"] == "2026-03-31"

    @pytest.mark.asyncio
    async def test_condition_intersection_output_filename_cleared(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """条件交集 date_str 变更时，output_filename / _actual_output 被清空
        （下次执行时会按新 date_str 生成 7条件交集20260424.xlsx）"""
        wf = Workflow(
            name="7条件交集", workflow_type="条件交集", date_str="2026-04-23",
            steps=[{
                "type": "condition_intersection",
                "config": {
                    "date_str": "2026-04-23",
                    "output_filename": "7条件交集20260423.xlsx",
                    "_actual_output": "7条件交集20260423.xlsx",
                    "high_price_periods": [{"start": "2026-03-18", "end": "2026-04-23"}],
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-24"},
        )

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        assert cfg["date_str"] == "2026-04-24"
        assert cfg["output_filename"] == ""
        assert cfg["_actual_output"] == ""
        # period.end 也应同步
        assert cfg["high_price_periods"][0]["end"] == "2026-04-24"

    @pytest.mark.asyncio
    async def test_regular_workflow_output_filename_cleared_on_date_change(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """普通工作流（如涨幅排名）也会清空 output_filename"""
        wf = Workflow(
            name="8涨幅排名", workflow_type="涨幅排名", date_str="2026-04-23",
            steps=[
                {"type": "merge_excel", "config": {"date_str": "2026-04-23", "output_filename": "total_1.xlsx"}},
                {"type": "ranking_sort", "config": {
                    "date_str": "2026-04-23",
                    "_actual_output": "8涨幅排名0202-20260423.xlsx",
                    "output_filename": "",
                }},
            ],
        )
        db_session.add(wf)
        await db_session.commit()

        await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-24"},
        )

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        # merge_excel 的 output_filename=total_1.xlsx 不含日期，
        # date_str 变化时被清空（让执行时按新 resolver 重新生成）
        assert refreshed.steps[0]["config"]["output_filename"] == ""
        # ranking_sort 的 _actual_output 含旧日期 20260423，被清空
        assert refreshed.steps[1]["config"]["_actual_output"] == ""

    @pytest.mark.asyncio
    async def test_stale_filename_cleared_even_if_date_str_already_current(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """date_str 已是目标日期但 output_filename 里还残留旧日期 → 也应清空

        重放场景：首次 bulk-set-date 把 date_str 改了但 output_filename
        未清；第二次同日期调用时仍应清理残留。
        """
        wf = Workflow(
            name="7条件交集", workflow_type="条件交集", date_str="2026-04-24",
            steps=[{
                "type": "condition_intersection",
                "config": {
                    "date_str": "2026-04-24",  # 已是目标日期
                    "output_filename": "7条件交集20260423.xlsx",  # 但残留旧日期
                    "_actual_output": "7条件交集20260423.xlsx",
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        resp = await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-24"},
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] >= 1

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        cfg = refreshed.steps[0]["config"]
        assert cfg["output_filename"] == ""
        assert cfg["_actual_output"] == ""

    @pytest.mark.asyncio
    async def test_filename_with_current_date_preserved(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """filename 已经含当前日期 → 不应被误清"""
        wf = Workflow(
            name="7条件交集", workflow_type="条件交集", date_str="2026-04-24",
            steps=[{
                "type": "condition_intersection",
                "config": {
                    "date_str": "2026-04-24",
                    "output_filename": "7条件交集20260424.xlsx",  # 当前日期，应保留
                }
            }],
        )
        db_session.add(wf)
        await db_session.commit()

        await client.put(
            "/api/v1/workflows/bulk-set-date",
            headers=auth_headers,
            json={"date_str": "2026-04-24"},
        )

        result = await db_session.execute(select(Workflow).where(Workflow.id == wf.id))
        refreshed = result.scalar_one()
        assert refreshed.steps[0]["config"]["output_filename"] == "7条件交集20260424.xlsx"
