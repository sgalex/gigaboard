import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="gigaboard",
    user="postgres",
    password="s1g!Alex"
)

cur = conn.cursor()
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name LIKE '%data_node%'
    ORDER BY table_name;
""")

tables = cur.fetchall()
if tables:
    print("DataNode tables still in DB:")
    for table in tables:
        print(f"  - {table[0]}")
else:
    print("✓ All DataNode tables removed!")

cur.close()
conn.close()
