import psycopg
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Connect to default postgres database
conn = psycopg.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="s1g!Alex"
)

# Create database
try:
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE gigaboard;")
    print("✅ Database 'gigaboard' created successfully!")
    cursor.close()
except psycopg.errors.DuplicateDatabase:
    print("⚠️ Database 'gigaboard' already exists")
finally:
    conn.close()
