"""
Stage 11 route test - hits all routes and prints results.
Run AFTER starting: myenv/Scripts/uvicorn app.main:app --port 8000
"""
import json, sys, urllib.request, urllib.error
from pathlib import Path

BASE = "http://localhost:8000"
FIXTURES = Path(__file__).parent / "fixtures" / "simple"
PASS = 0
FAIL = 0

def req(method, path, *, files=None, label=""):
    url = BASE + path
    try:
        if files:
            # multipart upload using urllib (no requests lib needed)
            boundary = "----TestBoundary"
            body_parts = []
            for field, (filename, data) in files.items():
                body_parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                    f"Content-Type: application/json\r\n\r\n".encode() + data + b"\r\n"
                )
            body = b"".join(
                p.encode() if isinstance(p, str) else p for p in body_parts
            ) + f"--{boundary}--\r\n".encode()
            req_obj = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
        else:
            req_obj = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req_obj, timeout=120) as resp:
            status = resp.status
            body = resp.read()
            return status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()

def check(label, status, body, expected_status=200, key=None):
    global PASS, FAIL
    ok = status == expected_status
    try:
        parsed = json.loads(body)
        body_str = json.dumps(parsed, indent=2)[:300]
        if key:
            ok = ok and key in parsed
    except Exception:
        body_str = body.decode(errors="replace")[:200]
    
    mark = "PASS" if ok else "FAIL"
    if ok: PASS += 1
    else:  FAIL += 1
    
    print(f"\n{'='*60}")
    print(f"[{mark}] {label}  (HTTP {status})")
    print(body_str)

print("="*60)
print("Stage 11 — FastAPI route test")
print("="*60)

# 1. GET /
s, b = req("GET", "/")
check("GET /  (API index)", s, b, key="routes")

# 2. GET /health
s, b = req("GET", "/health")
check("GET /health", s, b, key="status")

# 3. GET /agents  (before any cards exist from this run)
s, b = req("GET", "/agents")
check("GET /agents  (list — may be empty)", s, b, key="agents")

# 4. POST /agents/cards/generate  (LLM call — ~30s)
print("\n" + "="*60)
print("[....] POST /agents/cards/generate  (calling LLM — please wait ~30s)")
config_bytes  = (FIXTURES / "agent_config.json").read_bytes()
manifest_bytes = (FIXTURES / "tool_manifest.json").read_bytes()
trace_bytes   = (FIXTURES / "run_trace.json").read_bytes()

s, b = req("POST", "/agents/cards/generate", files={
    "config_file":   ("agent_config.json",  config_bytes),
    "manifest_file": ("tool_manifest.json", manifest_bytes),
    "trace_file":    ("run_trace.json",     trace_bytes),
})
check("POST /agents/cards/generate", s, b, expected_status=201, key="agent_id")

agent_id = None
try:
    data = json.loads(b)
    agent_id = data.get("agent_id")
    version  = data.get("version")
    print(f"     -> agent_id={agent_id}, version={version}, complete={data.get('completeness',{}).get('is_complete')}")
except Exception:
    pass

if agent_id:
    # 5. GET /agents/cards/{agent_id}
    s, b = req("GET", f"/agents/cards/{agent_id}")
    check(f"GET /agents/cards/{agent_id}  (latest JSON)", s, b, key="agent_name")

    # 6. GET /agents/cards/{agent_id}/versions/1
    s, b = req("GET", f"/agents/cards/{agent_id}/versions/1")
    check(f"GET /agents/cards/{agent_id}/versions/1", s, b, key="agent_id")

    # 7. GET /agents/cards/{agent_id}/completeness
    s, b = req("GET", f"/agents/cards/{agent_id}/completeness")
    check(f"GET /agents/cards/{agent_id}/completeness", s, b, key="is_complete")

    # 8. GET /agents/cards/{agent_id}/document  (HTML — just check 200 + contains agent name)
    s, b = req("GET", f"/agents/cards/{agent_id}/document")
    global PASS, FAIL
    ok = s == 200 and b"Agent Compliance Card" in b
    if ok: PASS += 1
    else:  FAIL += 1
    print(f"\n{'='*60}")
    print(f"[{'PASS' if ok else 'FAIL'}] GET /agents/cards/{agent_id}/document  (HTML)  (HTTP {s})")
    print(f"     HTML length: {len(b):,} bytes")

    # 9. Generate v2 then diff (no LLM — reuse same bytes, same agent_id gets v2)
    print("\n" + "="*60)
    print("[....] POST generate again (v2) for diff test...")
    s2, b2 = req("POST", "/agents/cards/generate", files={
        "config_file":   ("agent_config.json",  config_bytes),
        "manifest_file": ("tool_manifest.json", manifest_bytes),
        "trace_file":    ("run_trace.json",     trace_bytes),
    })
    if s2 == 201:
        v2 = json.loads(b2).get("version", 2)
        s, b = req("GET", f"/agents/cards/{agent_id}/diff?from=1&to={v2}")
        check(f"GET /agents/cards/{agent_id}/diff?from=1&to={v2}", s, b, key="total_changes")
    else:
        print(f"  v2 generation failed (HTTP {s2}) — skipping diff test")
else:
    print("\n  Skipping card-specific routes (generation failed — check LLM key)")

# 10. GET /agents/cards/nonexistent  (should be 404)
s, b = req("GET", "/agents/cards/nonexistent-agent-xyz")
check("GET /agents/cards/nonexistent  (expect 404)", s, b, expected_status=404)

print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} checks")
print("="*60)
sys.exit(0 if FAIL == 0 else 1)
