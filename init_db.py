# scripts/ensure_db_schema.py
from db.db import init_db
if __name__ == "__main__":
    init_db()
    print("DB schema ensured.")
