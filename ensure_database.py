import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load .env for local dev (no hard-coded secrets)
load_dotenv(Path(__file__).resolve().parent / '.env')

conn = psycopg2.connect(
    dbname=os.environ.get('DB_MAINTENANCE_DB', 'postgres'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD') or os.environ.get('POSTGRES_PASSWORD') or '',
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)
# Use DB_NAME from env for target DB, fallback to entropy_dev for legacy
target_db = os.environ.get('DB_NAME', 'entropy_dev')
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
if cur.fetchone() is None:
    # Use identifier quoting to avoid SQL injection (target_db is env-driven, but safe)
    cur.execute(f'CREATE DATABASE "{target_db}"')
    print(f'Created database: {target_db}')
else:
    print(f'Database already exists: {target_db}')
conn.commit()
conn.close()
