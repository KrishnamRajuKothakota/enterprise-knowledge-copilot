"""
Locust load test — 50 concurrent users, 2-minute run.
Tests the query endpoint under realistic concurrent load.
Usage: locust -f scripts/locustfile.py --headless -u 50 -r 5 -t 2m --host http://localhost:8000
"""
import json
import random
from locust import HttpUser, task, between

QUERIES = [
    "What is the SLA for P1 incident resolution?",
    "How do I escalate a VPN issue to L2?",
    "Find K8s rollback procedure",
    "New employee IT onboarding steps",
    "What is the leaver account disable procedure?",
    "What is the change management process?",
    "How do I provision cloud access?",
    "What is the incident management escalation procedure?",
    "How are incidents classified by priority?",
    "What is the backup and recovery procedure?",
]

class EKCUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Login once per user."""
        r = self.client.post("/api/v1/auth/login",
            json={"email": "admin@ekc.local", "password": "admin123"},
            name="/auth/login",
        )
        if r.status_code == 200:
            self.token = r.json().get("access_token")

    @task(10)
    def query(self):
        """Main query task — weighted 10x."""
        if not self.token:
            return
        q = random.choice(QUERIES)
        self.client.post(
            "/api/v1/query",
            json={"query": q},
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/v1/query",
            timeout=30,
        )

    @task(2)
    def health(self):
        """Health check — weighted 2x."""
        self.client.get("/health", name="/health")

    @task(1)
    def metrics(self):
        """Metrics endpoint — weighted 1x."""
        self.client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/v1/metrics",
        )
