import psycopg2

conn = psycopg2.connect(
    dbname='postgres',
    user='postgres',
    password='Walker@2024@2008',
    host='localhost',
    port=5432,
)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = 'entropy_dev'")
if cur.fetchone() is None:
    cur.execute('CREATE DATABASE entropy_dev')
    print('Created database: entropy_dev')
else:
    print('Database already exists: entropy_dev')
conn.commit()
conn.close()
