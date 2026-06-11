"""
Run before demo to pre-populate Redis cache with all demo queries.
Subsequent queries will be <500ms.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx, time

API = "http://localhost:8000/api/v1"

# Login
r = httpx.post(f"{API}/auth/login",
    json={"email": "admin@ekc.local", "password": "admin123"}, timeout=10)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

ROLES = ["junior_engineer", "l1_support", "lead", "admin"]

DEMO_QUERIES = [
    "Resolve ticket JRA-1001: auth-service CrashLoopBackOff after deployment",
    "Auto-resolve: Pod ImagePullBackOff in production namespace",
    "What is the SLA for P1 incident resolution?",
    "How do I escalate a VPN issue to L2?",
    "Find K8s rollback procedure",
    "New employee IT onboarding steps",
    "Which SOPs cover CrashLoopBackOff?",
    "What is the leaver account disable procedure?",
    "What is the change management process?",
    "How do I provision cloud access?",
    "Which SOPs apply to auth-service that triggered JRA-1001?",
    "What is the incident management escalation procedure?",
]

ROLES = ["junior_engineer", "l1_support", "lead", "admin"]

print("Warming cache for demo queries (all 4 roles)...")
for role in ROLES:
    print(f"\n  Role: {role}")
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"    [{i}/{len(DEMO_QUERIES)}] {query[:45]}...", end=" ", flush=True)
        start = time.time()
        r = httpx.post(f"{API}/query",
            json={"query": query, "role": role}, headers=headers, timeout=120)
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json()
            conf = data.get("confidence_score", 0)
            cached = data.get("cache_hit", False)
            status = "(cached)" if cached else ""
            print(f"✓ {elapsed:.1f}s conf={conf:.0%} {status}")
        else:
            print(f"✗ error {r.status_code}")
print()
print("Cache warmed for all 4 roles. Done.")
