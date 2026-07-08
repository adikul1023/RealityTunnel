import urllib.request
import concurrent.futures
import time

def fetch(url):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status
    except Exception as e:
        return str(e)

def main():
    base_url = "http://localhost:8080"
    
    endpoints = ["/livez", "/readyz", "/health", "/admin/health"]
    for ep in endpoints:
        print(f"Testing {ep}...")
        status = fetch(f"{base_url}{ep}")
        print(f"Result: {status}")

    print("\nRunning load test on /health (1000 requests)...")
    start = time.perf_counter()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        urls = [f"{base_url}/health"] * 1000
        results = list(executor.map(fetch, urls))
        
    duration = time.perf_counter() - start
    
    print(f"Load test completed: {len(results)} requests in {duration:.2f}s")
    print(f"Average latency: {(duration / 1000) * 1000:.2f}ms")
    # count 200s
    success = results.count(200)
    print(f"Successful requests (200 OK): {success} / {len(results)}")

if __name__ == "__main__":
    main()
