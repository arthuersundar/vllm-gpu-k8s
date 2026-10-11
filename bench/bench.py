import os, time, requests
from concurrent.futures import ThreadPoolExecutor

URL = os.getenv("VLLM_URL", "http://localhost:8000") + "/v1/chat/completions"
MODEL = os.getenv("MODEL", "Qwen/Qwen3-4B")
HEADERS = {"Authorization": f"Bearer {os.environ['VLLM_KEY']}"}
PROMPT = "Explain what a Kubernetes StatefulSet is in about 150 words."

def one_request(_):
    t0 = time.time()
    r = requests.post(URL, headers=HEADERS, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 256,
        "chat_template_kwargs": {"enable_thinking": False},
    }, timeout=300)
    r.raise_for_status()
    return time.time() - t0, r.json()["usage"]["completion_tokens"]

for concurrency in [1, 4, 8, 16, 32, 64]:
    t0 = time.time()
    with ThreadPoolExecutor(concurrency) as ex:
        results = list(ex.map(one_request, range(concurrency * 2)))
    wall = time.time() - t0
    tokens = sum(t for _, t in results)
    avg_latency = sum(l for l, _ in results) / len(results)
    print(f"concurrency={concurrency:2d}  total tok/s={tokens/wall:7.1f}  "
          f"avg latency={avg_latency:5.2f}s  requests={len(results)}")