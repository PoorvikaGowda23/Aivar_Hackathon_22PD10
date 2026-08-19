"""Stage 12 verification: test logging, request-ID, error handlers, and real /health."""
import json, urllib.request, urllib.error, sys, time

BASE = "http://localhost:8000"

def get(path, expect=200):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read())
    except Exception as e:
        return 0, {}, {"error": str(e)}

results = []
if __name__ == "__main__":
    results = []

    print("=" * 60)
    print("Stage 12 verification")
    print("=" * 60)

    s, headers, b = get_any("/health")
    rid = headers.get("X-Request-ID") or headers.get("x-request-id", "")
    db_ok   = b.get("checks", {}).get("database", {}).get("status") == "ok"
    groq_ok = b.get("checks", {}).get("llm", {}).get("status") == "ok"
    overall = b.get("status") == "healthy"
    check("GET /health — overall healthy",  overall,  b.get("status"))
    check("GET /health — DB ping ok",       db_ok,    str(b.get("checks",{}).get("database",{})))
    check("GET /health — Groq key valid",   groq_ok,  str(b.get("checks",{}).get("llm",{})))
    check("X-Request-ID header present",    bool(rid), rid[:12] if rid else "MISSING")
    check("request_id in body",             "request_id" in b, b.get("request_id",""))
    check("DB latency reported",            "latency_ms" in b.get("checks",{}).get("database",{}))

    # 2. 404 — request_id in error body
    s, headers, b = get("/agents/cards/no-such-agent-xyz-999", expect=404)
    rid_404 = headers.get("X-Request-ID") or headers.get("x-request-id", "")
    check("404 has request_id in body",     "request_id" in b, str(b.get("request_id","")))
    check("404 has X-Request-ID header",    bool(rid_404), rid_404[:12] if rid_404 else "MISSING")
    check("404 detail is readable string",  isinstance(b.get("detail"), str), b.get("detail","")[:60])

    # 3. / root still works
    s, _, b = get("/")
    check("GET / still returns routes",     "routes" in b)

    print()
    passed = sum(1 for _, ok in results if ok)
    print(f"Stage 12 RESULTS: {passed}/{len(results)} checks passed")
    for label, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")
    print("=" * 60)
    sys.exit(0 if passed == len(results) else 1)
