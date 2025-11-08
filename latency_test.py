#!/usr/bin/env python3
"""Script to measure latency of each API call using standard library."""
import time
import json
from urllib import request as urllib_request

BASE_URL = "http://localhost:8000"

endpoints = [
    ("GET", "/api/scores/AAPL", None),
    ("GET", "/api/price-history/AAPL", None),
    ("GET", "/api/valuation-metrics/AAPL", None),
    ("GET", "/api/market-conditions", None),
    ("GET", "/api/sector-news/technology", None),
    ("GET", "/api/token-usage", None),
    ("POST", "/chat", {"question": "What is the market outlook for AAPL?", "include_reasoning": False}),
]

def measure(method, path, payload=None, trials=3):
    times = []
    for _ in range(trials):
        url = BASE_URL + path
        start = time.time()
        try:
            if method == "GET":
                resp = urllib_request.urlopen(url)
            elif method == "POST":
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib_request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
                resp = urllib_request.urlopen(req)
            else:
                continue
            _ = resp.read()
        except Exception:
            pass
        elapsed = time.time() - start
        times.append(elapsed)
    if times:
        return min(times), sum(times) / len(times), max(times)
    return None, None, None

def main():
    print("Measuring API endpoint latencies (in seconds):")
    for method, path, payload in endpoints:
        min_t, avg_t, max_t = measure(method, path, payload)
        if min_t is None:
            print(f"{method:4} {path:30} failed to get any response.")
        else:
            print(f"{method:4} {path:30} min: {min_t:.3f}  avg: {avg_t:.3f}  max: {max_t:.3f}")

if __name__ == "__main__":
    main()