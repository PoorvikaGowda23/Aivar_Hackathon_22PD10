"""Quick synchronous route tests - no LLM calls for fast routes, then generate."""
import json, urllib.request, urllib.error, sys
from pathlib import Path

BASE = "http://localhost:8000"

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}

if __name__ == "__main__":
    results = []

    # --- 1. GET / ---
    s, b = get("/")
    ok = s == 200 and "routes" in b
    results.append(("GET /", s, ok))
    print(f"[{'OK' if ok else 'FAIL'}] GET /  (HTTP {s}) -> keys: {list(b.keys())}")

    # --- 2. GET /health ---
    s, b = get("/health")
    ok = s == 200 and b.get("status") == "healthy"
    results.append(("GET /health", s, ok))
    print(f"[{'OK' if ok else 'FAIL'}] GET /health  (HTTP {s}) -> {b}")

    # --- 3. GET /agents ---
    s, b = get("/agents")
    ok = s == 200 and "agents" in b
    results.append(("GET /agents", s, ok))
    print(f"[{'OK' if ok else 'FAIL'}] GET /agents  (HTTP {s}) -> count={b.get('count')}")

    # --- 4. GET /agents/cards/nonexistent -> expect 404 ---
    s, b = get("/agents/cards/does-not-exist-xyz")
    ok = s == 404
    results.append(("GET /agents/cards/nonexistent (404)", s, ok))
    print(f"[{'OK' if ok else 'FAIL'}] GET /agents/cards/nonexistent  (HTTP {s}) -> {b.get('detail','')[:60]}")

    print("\n--- Fast route checks done ---")
    print(f"Passed: {sum(1 for _,_,ok in results if ok)}/{len(results)}")
    print("\nNow testing POST /agents/cards/generate (LLM call ~30s)...")

    # --- 5. POST /agents/cards/generate ---
    FIXTURES = Path(__file__).parent / "fixtures" / "simple"
    boundary = "TestBoundary123"
    files = {
        "config_file":   ("agent_config.json",  (FIXTURES/"agent_config.json").read_bytes()),
        "manifest_file": ("tool_manifest.json", (FIXTURES/"tool_manifest.json").read_bytes()),
        "trace_file":    ("run_trace.json",     (FIXTURES/"run_trace.json").read_bytes()),
    }
    body_parts = []
    for field, (fname, data) in files.items():
        body_parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\nContent-Type: application/json\r\n\r\n".encode()
            + data + b"\r\n"
        )
    body = b"".join(body_parts) + f"--{boundary}--\r\n".encode()

    try:
        req = urllib.request.Request(
            BASE + "/agents/cards/generate", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            s = r.status
            resp = json.loads(r.read())
    except urllib.error.HTTPError as e:
        s = e.code
        resp = json.loads(e.read())

    ok = s == 201 and "agent_id" in resp
    results.append(("POST /agents/cards/generate", s, ok))
    agent_id = resp.get("agent_id")
    version = resp.get("version")
    print(f"[{'OK' if ok else 'FAIL'}] POST /agents/cards/generate  (HTTP {s})")
    if ok:
        print(f"  agent_id={agent_id}, version={version}, complete={resp.get('completeness',{}).get('is_complete')}")

    if agent_id:
        # --- 6. GET /agents/cards/{agent_id} ---
        s, b = get(f"/agents/cards/{agent_id}")
        ok = s == 200 and b.get("agent_id") == agent_id
        results.append((f"GET /agents/cards/{agent_id}", s, ok))
        print(f"[{'OK' if ok else 'FAIL'}] GET /agents/cards/{agent_id}  (HTTP {s}) -> v{b.get('version')}")

        # --- 7. GET /agents/cards/{agent_id}/versions/1 ---
        s, b = get(f"/agents/cards/{agent_id}/versions/1")
        ok = s == 200 and b.get("version") == 1
        results.append((f"GET /versions/1", s, ok))
        print(f"[{'OK' if ok else 'FAIL'}] GET .../versions/1  (HTTP {s}) -> version={b.get('version')}")

        # --- 8. GET /agents/cards/{agent_id}/completeness ---
        s, b = get(f"/agents/cards/{agent_id}/completeness")
        ok = s == 200 and "is_complete" in b
        results.append(("GET .../completeness", s, ok))
        print(f"[{'OK' if ok else 'FAIL'}] GET .../completeness  (HTTP {s}) -> is_complete={b.get('is_complete')}, issues={len(b.get('issues',[]))}")

        # --- 9. GET /agents/cards/{agent_id}/document (HTML) ---
        try:
            with urllib.request.urlopen(BASE + f"/agents/cards/{agent_id}/document", timeout=15) as r:
                hs = r.status
                html = r.read()
            ok = hs == 200 and b"Agent Compliance Card" in html
            results.append(("GET .../document (HTML)", hs, ok))
            print(f"[{'OK' if ok else 'FAIL'}] GET .../document  (HTTP {hs}) -> {len(html):,} bytes HTML")
        except Exception as e:
            results.append(("GET .../document (HTML)", 0, False))
            print(f"[FAIL] GET .../document -> {e}")

    print("\n" + "="*55)
    passed = sum(1 for _,_,ok in results if ok)
    print(f"STAGE 11 RESULTS: {passed}/{len(results)} routes passed")
    for label, status, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}  (HTTP {status})")
    print("="*55)
    sys.exit(0 if passed == len(results) else 1)
