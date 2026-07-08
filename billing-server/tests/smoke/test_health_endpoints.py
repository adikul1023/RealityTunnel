import asyncio
import aiohttp
import time

async def main():
    base_url = "http://localhost:8088"
    
    async with aiohttp.ClientSession() as session:
        # Test /livez
        async with session.get(f"{base_url}/livez") as resp:
            print(f"GET /livez: {resp.status} - {await resp.text()}")

        # Test /readyz
        async with session.get(f"{base_url}/readyz") as resp:
            print(f"GET /readyz: {resp.status} - {await resp.text()}")

        # Test /health
        async with session.get(f"{base_url}/health") as resp:
            print(f"GET /health: {resp.status} - {await resp.text()}")

        # Test /admin/health (no auth should fail)
        async with session.get(f"{base_url}/admin/health") as resp:
            print(f"GET /admin/health (no auth): {resp.status} - {await resp.text()}")

        # Load test /health
        print("\nRunning load test on /health (1000 requests)...")
        start = time.perf_counter()
        
        async def fetch():
            async with session.get(f"{base_url}/health") as r:
                return r.status
        
        tasks = [fetch() for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start
        
        print(f"Load test completed: {len(results)} requests in {duration:.2f}s")
        print(f"Average latency: {(duration / 1000) * 1000:.2f}ms")

if __name__ == "__main__":
    asyncio.run(main())
