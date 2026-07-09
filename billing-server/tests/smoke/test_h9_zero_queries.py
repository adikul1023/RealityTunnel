import asyncio
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from httpx import AsyncClient
import time

@pytest.mark.asyncio
async def test_health_zero_queries(async_client: AsyncClient):
    """
    H9 Remediation Proof: 
    Sends 1000 requests to /health and asserts that EXACTLY 0 database queries are executed
    across the entire test.
    """
    # Track the number of queries executed
    query_count = 0

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    # Attach the listener to the global engine
    from app.database import engine
    # In async context, the underlying sync engine is accessed via sync_engine
    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

    try:
        start = time.perf_counter()
        
        # We will use the same client to simulate a burst of traffic
        async def fetch():
            resp = await async_client.get("/health")
            assert resp.status_code == 200
            return resp

        tasks = [fetch() for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        
        duration = time.perf_counter() - start
        
        print(f"\n--- H9 EVIDENCE ---")
        print(f"Total Requests: {len(results)}")
        print(f"Total Time: {duration:.2f}s")
        print(f"Total Database Queries Executed: {query_count}")
        print(f"-------------------")
        
        assert query_count == 0, f"Expected 0 queries, but executed {query_count}"

    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
