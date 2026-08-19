"""
Stage 15: End-to-end verification against the live Render cloud service.
"""

import json, urllib.request, urllib.error, sys
from pathlib import Path

LIVE_URL = "https://aivaragentcompliancecardgenerator-22pd10.onrender.com"
FIXTURES = Path(__file__).parent / "fixtures" / "simple"

results = []
def check(label, ok, detail=""):
    results.append((label, ok))
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f"  -> {detail}" if detail else ""))

print("=" * 70)
print("STAGE 15 — LIVE CLOUD E2E VERIFICATION")
print(f"URL: {LIVE_URL}")
print("=" * 70)

# 1. GET /
try:
    with urllib.request.urlopen(LIVE_URL + "/", timeout=30) as r:
        s = r.status
        b = json.loads(r.read())
    check("GET /  (API Root)", s == 200 and "routes" in b, f"HTTP {s}")
except Exception as e:
    check("GET /", False, str(e))

# 2. GET /health?full=true
try:
    with urllib.request.urlopen(LIVE_URL + "/health?full=true", timeout=30) as r:
        s = r.status
        b = json.loads(r.read())
    check("GET /health?full=true  (Liveness & Dependency check)", s == 200 and b.get("status") == "healthy", f"Status: {b.get('status')}")
    check("  ↳ Neon Postgres Cloud DB", b.get("checks", {}).get("database", {}).get("status") == "ok", str(b.get("checks",{}).get("database")))
    check("  ↳ Groq LLaMA 3.3 70B API", b.get("checks", {}).get("llm", {}).get("status") == "ok", str(b.get("checks",{}).get("llm")))
except Exception as e:
    check("GET /health?full=true", False, str(e))

# 3. GET /docs (Swagger UI)
try:
    with urllib.request.urlopen(LIVE_URL + "/docs", timeout=30) as r:
        s = r.status
    check("GET /docs  (Interactive Swagger UI)", s == 200, f"HTTP {s}")
except Exception as e:
    check("GET /docs", False, str(e))

# 4. POST /agents/cards/generate  (live cloud generation + Neon DB save)
print("\n[....] Triggering live cloud card generation (calling Groq + Neon DB)...")
boundary = "CloudTestBoundary99"
files = {
    "config_file":   ("agent_config.json",  (FIXTURES / "agent_config.json").read_bytes()),
    "manifest_file": ("tool_manifest.json", (FIXTURES / "tool_manifest.json").read_bytes()),
    "trace_file":    ("run_trace.json",     (FIXTURES / "run_trace.json").read_bytes()),
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
        LIVE_URL + "/agents/cards/generate",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        s = r.status
        resp = json.loads(r.read())
    check("POST /agents/cards/generate  (Card Generation & Cloud DB Persistence)", s == 201 and "agent_id" in resp, f"HTTP {s}")
    agent_id = resp.get("agent_id")
    version = resp.get("version")
    check("  ↳ Generated Agent ID", bool(agent_id), agent_id)
    check("  ↳ Assigned Version Number", bool(version), f"v{version}")
except Exception as e:
    check("POST /agents/cards/generate", False, str(e))
    agent_id = "agent-cs-001"

# 5. GET /agents/cards/{agent_id}
try:
    with urllib.request.urlopen(LIVE_URL + f"/agents/cards/{agent_id}", timeout=30) as r:
        s = r.status
        card_data = json.loads(r.read())
    check(f"GET /agents/cards/{agent_id}  (Structured JSON Retrieval)", s == 200 and card_data.get("agent_id") == agent_id, f"Agent: {card_data.get('agent_name')}")
except Exception as e:
    check(f"GET /agents/cards/{agent_id}", False, str(e))

# 6. GET /agents/cards/{agent_id}/completeness
try:
    with urllib.request.urlopen(LIVE_URL + f"/agents/cards/{agent_id}/completeness", timeout=30) as r:
        s = r.status
        comp_data = json.loads(r.read())
    check(f"GET /agents/cards/{agent_id}/completeness  (Rule-Based Completeness Report)", s == 200 and "is_complete" in comp_data, f"is_complete: {comp_data.get('is_complete')}")
except Exception as e:
    check(f"GET /agents/cards/{agent_id}/completeness", False, str(e))

# 7. GET /agents/cards/{agent_id}/document (HTML document)
try:
    with urllib.request.urlopen(LIVE_URL + f"/agents/cards/{agent_id}/document", timeout=30) as r:
        s = r.status
        html_bytes = r.read()
    check(f"GET /agents/cards/{agent_id}/document  (Human-Readable HTML Document)", s == 200 and b"Agent Compliance Card" in html_bytes, f"Size: {len(html_bytes):,} bytes")
except Exception as e:
    check(f"GET /agents/cards/{agent_id}/document", False, str(e))

print("\n" + "=" * 70)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"STAGE 15 VERIFICATION: {passed}/{total} checks passed")
print("=" * 70)

sys.exit(0 if passed == total else 1)
