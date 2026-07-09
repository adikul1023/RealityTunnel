import asyncio
import time
from sqlalchemy import event
import httpx
from app.main import app
from app.database import engine

async def run_test():
    query_count = 0

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        query_count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute)

    print("Starting H9 Verification Load Test (1000 requests to /health)...")
    start = time.perf_counter()
    
    # We use httpx AsyncClient passing the FastAPI app directly.
    # This runs the requests in-process, sharing the same SQLAlchemy engine.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [client.get("/health") for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        
    duration = time.perf_counter() - start
    
    event.remove(engine.sync_engine, "before_cursor_execute", before_cursor_execute)
    
    success = sum(1 for r in results if r.status_code == 200)

    print(f"\n--- H9 EVIDENCE ---")
    print(f"Total Requests: {len(results)}")
    print(f"Successful Requests (200 OK): {success}")
    print(f"Total Time: {duration:.2f}s")
    print(f"Total Database Queries Executed: {query_count}")
    print(f"-------------------")
    
    if query_count == 0 and success == 1000:
        print("VERDICT: PASS. Zero database queries executed.")
    else:
        print("VERDICT: FAIL.")

if __name__ == "__main__":
    asyncio.run(run_test())
