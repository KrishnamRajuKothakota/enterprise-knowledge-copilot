"""
Run once to create the four demo users.
Usage: python scripts/seed_users.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ekc.db.session import SessionLocal
from src.ekc.db.models import User, UserRole
from src.ekc.core.security import hash_password
import uuid

USERS = [
    {"name": "Admin User",       "email": "admin@ekc.local",    "password": "admin123",    "role": UserRole.admin,            "department": "IT"},
    {"name": "Junior Engineer",  "email": "junior@ekc.local",   "password": "junior123",   "role": UserRole.junior_engineer,  "department": "Engineering"},
    {"name": "L1 Support Agent", "email": "l1@ekc.local",       "password": "l1support123","role": UserRole.l1_support,       "department": "Support"},
    {"name": "Team Lead",        "email": "lead@ekc.local",     "password": "lead123",     "role": UserRole.lead,             "department": "Engineering"},
]

def seed():
    db = SessionLocal()
    created = 0
    for u in USERS:
        if db.query(User).filter(User.email == u["email"]).first():
            print(f"  skip (exists): {u['email']}")
            continue
        db.add(User(
            user_id=str(uuid.uuid4()),
            name=u["name"],
            email=u["email"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
            department=u["department"],
            is_active=True,
        ))
        created += 1
        print(f"  created: {u['email']} ({u['role'].value})")
    db.commit()
    db.close()
    print(f"\nDone — {created} users created.")

if __name__ == "__main__":
    seed()