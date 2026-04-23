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
