import pytest
import asyncio
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import time


BASE_URL = "http://localhost:3000/api/v1"
TIMEOUT = 30.0

# e2e 测试依赖本地真实运行的后端（localhost:3000）。默认跳过，
# 设 RUN_E2E=1 主动启用（CI / staging 环境）。
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_E2E") != "1",
    reason="e2e 测试需真实后端运行于 localhost:3000；设 RUN_E2E=1 启用",
)


class TestDataFetchE2E:
    """端到端测试：数据获取API"""

    @pytest.mark.asyncio
    async def test_get_fetch_status_success(self):
        """测试获取数据状态 - 成功"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/fetch/status")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("success") is True, f"Expected success=True, got {data}"
            assert "data" in data, "Response should contain 'data' field"
            assert "stock_count" in data["data"], "Data should contain stock_count"

    @pytest.mark.asyncio
    async def test_get_fetch_status_response_structure(self):
        """测试获取数据状态 - 响应结构验证"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/fetch/status")

            assert response.status_code == 200
            data = response.json()

            expected_fields = ["stock_count", "daily_bar_count", "financial_count", "last_trade_date", "last_report_date"]
            for field in expected_fields:
                assert field in data["data"], f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_get_fetch_status_multiple_calls(self):
        """测试获取数据状态 - 多次调用稳定性"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            results = []
            for _ in range(3):
                response = await client.get("/data/fetch/status")
                assert response.status_code == 200
                results.append(response.json())

            assert all(r["success"] for r in results), "All calls should return success"


class TestStockListE2E:
    """端到端测试：股票列表API"""

    @pytest.mark.asyncio
    async def test_get_stock_list_success(self):
        """测试获取股票列表 - 成功"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/stock/list")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("success") is True, f"Expected success=True, got {data}"

    @pytest.mark.asyncio
    async def test_get_stock_list_returns_data(self):
        """测试获取股票列表 - 返回数据验证"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/stock/list")

            data = response.json()
            if data.get("success"):
                assert "data" in data, "Success response should contain data"
                assert "row_count" in data, "Success response should contain row_count"
                assert data["row_count"] >= 0, "Row count should be non-negative"

    @pytest.mark.asyncio
    async def test_get_industry_list_success(self):
        """测试获取行业列表 - 成功"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/industry/list")

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True


class TestSQLQueryE2E:
    """端到端测试：SQL查询API"""

    @pytest.mark.asyncio
    async def test_sql_query_simple_select(self):
        """测试SQL查询 - 简单SELECT"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            sql = "SELECT 1 as test_value"
            response = await client.post(
                "/data/query/sql",
                json={"sql": sql}
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert data.get("success") is True, f"Query failed: {data}"

    @pytest.mark.asyncio
    async def test_sql_query_with_where_clause(self):
        """测试SQL查询 - 带WHERE子句"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            sql = "SELECT 1 as num WHERE 1=1"
            response = await client.post(
                "/data/query/sql",
                json={"sql": sql}
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True

    @pytest.mark.asyncio
    async def test_sql_query_limit(self):
        """测试SQL查询 - 带LIMIT"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            sql = "SELECT 1 as num UNION SELECT 2 UNION SELECT 3 LIMIT 1"
            response = await client.post(
                "/data/query/sql",
                json={"sql": sql}
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "row_count" in data
                assert data["row_count"] <= 1

    @pytest.mark.asyncio
    async def test_sql_query_invalid_syntax(self):
        """测试SQL查询 - 无效语法"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            sql = "SELEC * FORM nonexistent"
            response = await client.post(
                "/data/query/sql",
                json={"sql": sql}
            )

            data = response.json()
            assert data.get("success") is False or "error" in data

    @pytest.mark.asyncio
    async def test_sql_query_empty_body(self):
        """测试SQL查询 - 空请求体"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/sql",
                json={}
            )

            assert response.status_code in [400, 422], "Should return error for empty body"

    @pytest.mark.asyncio
    async def test_sql_query_show_tables(self):
        """测试SQL查询 - SHOW TABLES"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/sql",
                json={"sql": "SHOW TABLES"}
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "data" in data
                assert isinstance(data["data"], list)


class TestAIQueryE2E:
    """端到端测试：AI查询API"""

    @pytest.mark.asyncio
    async def test_ai_query_consume_industry(self):
        """测试AI查询 - 消费行业"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": "查询消费行业的股票"}
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "sql" in data or "explanation" in data, "Response should contain sql or explanation"

    @pytest.mark.asyncio
    async def test_ai_query_with_growth_condition(self):
        """测试AI查询 - 带增长条件"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": "净利润增长超过50%的股票"}
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "sql" in data
                assert "50" in data["sql"]

    @pytest.mark.asyncio
    async def test_ai_query_low_pe(self):
        """测试AI查询 - 低市盈率"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": "市盈率低于10的股票"}
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "sql" in data

    @pytest.mark.asyncio
    async def test_ai_query_date_range(self):
        """测试AI查询 - 日期范围"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": "2026-01-01到2026-04-09的行情数据"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "sql" in data or "explanation" in data

    @pytest.mark.asyncio
    async def test_ai_query_empty_query(self):
        """测试AI查询 - 空查询"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": ""}
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False

    @pytest.mark.asyncio
    async def test_ai_query_unrecognized(self):
        """测试AI查询 - 无法识别的查询"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/ai",
                json={"query": "今天天气怎么样"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is False or "explanation" in data


class TestStockDailyQueryE2E:
    """端到端测试：股票日线查询API"""

    @pytest.mark.asyncio
    async def test_query_stock_daily_basic(self):
        """测试查询股票日线 - 基本查询"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stock-daily",
                json={
                    "start_date": "2026-01-01",
                    "end_date": "2026-04-09"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True or "columns" in data

    @pytest.mark.asyncio
    async def test_query_stock_daily_with_code(self):
        """测试查询股票日线 - 指定股票代码"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stock-daily",
                json={
                    "stock_code": "600000",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-09"
                }
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "data" in data

    @pytest.mark.asyncio
    async def test_query_stock_daily_with_indicators(self):
        """测试查询股票日线 - 指定指标"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stock-daily",
                json={
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-09",
                    "indicators": ["trade_date", "close", "ma5", "ma10"]
                }
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success") and data.get("columns"):
                assert "close" in data["columns"]


class TestStocksFilterE2E:
    """端到端测试：股票筛选API"""

    @pytest.mark.asyncio
    async def test_query_stocks_filter_basic(self):
        """测试股票筛选 - 基本筛选"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stocks-filter",
                json={
                    "limit": 10
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True or "data" in data

    @pytest.mark.asyncio
    async def test_query_stocks_filter_with_pe(self):
        """测试股票筛选 - 市盈率筛选"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stocks-filter",
                json={
                    "pe_min": 0,
                    "pe_max": 50,
                    "limit": 20
                }
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "data" in data

    @pytest.mark.asyncio
    async def test_query_stocks_filter_with_industry(self):
        """测试股票筛选 - 行业筛选"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stocks-filter",
                json={
                    "industry": "银行",
                    "limit": 10
                }
            )

            assert response.status_code == 200
            data = response.json()
            if data.get("success"):
                assert "data" in data

    @pytest.mark.asyncio
    async def test_query_stocks_filter_exchange(self):
        """测试股票筛选 - 交易所筛选"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stocks-filter",
                json={
                    "exchange": "SH",
                    "limit": 10
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_query_stocks_filter_sort(self):
        """测试股票筛选 - 排序"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/stocks-filter",
                json={
                    "sort_by": "pe_ratio",
                    "order": "asc",
                    "limit": 5
                }
            )

            assert response.status_code == 200


class TestManualUpdateE2E:
    """端到端测试：手动更新API"""

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_missing_params(self):
        """测试获取日线数据 - 缺少参数"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/fetch/daily-bar",
                json={}
            )

            assert response.status_code in [400, 422], "Should return error for missing params"

    @pytest.mark.asyncio
    async def test_fetch_daily_bar_partial_params(self):
        """测试获取日线数据 - 部分参数"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/fetch/daily-bar",
                json={
                    "stock_code": "600000"
                }
            )

            assert response.status_code in [400, 422], "Should return error for missing dates"


class TestIntegrationE2E:
    """端到端测试：集成测试"""

    @pytest.mark.asyncio
    async def test_full_query_flow(self):
        """测试完整查询流程"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.get("/data/fetch/status")
            assert response.status_code == 200

            response = await client.get("/data/stock/list")
            assert response.status_code == 200

            response = await client.post(
                "/data/query/sql",
                json={"sql": "SELECT 1"}
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """测试并发请求"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            tasks = [
                client.get("/data/fetch/status"),
                client.get("/data/stock/list"),
                client.post("/data/query/sql", json={"sql": "SELECT 1"}),
            ]

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for response in responses:
                if not isinstance(response, Exception):
                    assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_response_time(self):
        """测试API响应时间"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            start = time.time()
            response = await client.get("/data/fetch/status")
            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 5.0, f"API response took {elapsed:.2f}s, expected < 5s"

    @pytest.mark.asyncio
    async def test_multiple_ai_queries(self):
        """测试多个AI查询"""
        queries = [
            "查询消费行业的股票",
            "净利润增长超过30%的股票",
            "市盈率最低的前10只股票",
            "查询银行行业的股票"
        ]

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            for query in queries:
                response = await client.post(
                    "/data/query/ai",
                    json={"query": query}
                )
                assert response.status_code == 200


class TestErrorHandlingE2E:
    """端到端测试：错误处理"""

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """测试无效JSON"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/sql",
                content=b"not valid json",
                headers={"Content-Type": "application/json"}
            )

            assert response.status_code in [400, 422, 500]

    @pytest.mark.asyncio
    async def test_missing_content_type(self):
        """测试缺少Content-Type"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = await client.post(
                "/data/query/sql",
                content=b'{"sql": "SELECT 1"}'
            )

            assert response.status_code in [200, 400, 415]

    @pytest.mark.asyncio
    async def test_sql_injection_attempt(self):
        """测试SQL注入尝试"""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            dangerous_queries = [
                "'; DROP TABLE dim_stock; --",
                "1; DELETE FROM fact_daily_bar WHERE 1=1",
                "SELECT * FROM users WHERE name = ' OR 1=1 --"
            ]

            for sql in dangerous_queries:
                response = await client.post(
                    "/data/query/sql",
                    json={"sql": sql}
                )
                data = response.json()
                if response.status_code == 200:
                    assert data.get("success") is False or "error" in data
