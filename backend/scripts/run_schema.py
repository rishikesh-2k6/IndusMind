"""Run schema.sql against Supabase Postgres (one-time setup script)."""
import os
import psycopg2

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")

def main():
    print(f"Reading schema from: {SCHEMA_FILE}")
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Try direct connection (port 5432), fallback to session pooler (port 5432 on pooler)
    configs = [
        {
            "label": "Direct connection",
            "host": "db.ctvehidnxlvpsbqnmysi.supabase.co",
            "port": 5432,
            "user": "postgres",
            "password": "Dh@nush_Sai581",
        },
        {
            "label": "Session mode pooler",
            "host": "aws-0-ap-south-1.pooler.supabase.com",
            "port": 5432,
            "user": "postgres.ctvehidnxlvpsbqnmysi",
            "password": "Dh@nush_Sai581",
        },
    ]

    conn = None
    for cfg in configs:
        print(f"Trying {cfg['label']} ({cfg['host']}:{cfg['port']})...")
        try:
            conn = psycopg2.connect(
                host=cfg["host"],
                port=cfg["port"],
                dbname="postgres",
                user=cfg["user"],
                password=cfg["password"],
                sslmode="require",
                connect_timeout=15,
            )
            print(f"Connected via {cfg['label']}!")
            break
        except Exception as e:
            print(f"  Failed: {str(e).strip().split(chr(10))[0]}")

    if conn is None:
        print("\nERROR: Could not connect to the database with any method.")
        return

    conn.autocommit = True
    cur = conn.cursor()

    # Split into individual statements, respecting $$ function bodies
    statements = []
    current = []
    in_function = False

    for line in schema_sql.split('\n'):
        stripped = line.strip()
        if not stripped and not in_function and not current:
            continue

        dollar_count = stripped.count('$$')
        if dollar_count % 2 == 1:
            in_function = not in_function

        current.append(line)

        if stripped.endswith(';') and not in_function:
            stmt = '\n'.join(current).strip()
            if stmt and not stmt.startswith('--'):
                statements.append(stmt)
            current = []

    print(f"\nFound {len(statements)} SQL statements to execute.\n")
    success = 0
    for i, stmt in enumerate(statements, 1):
        first_line = stmt.split('\n')[0][:80]
        print(f"  [{i}/{len(statements)}] {first_line}")
        try:
            cur.execute(stmt)
            print(f"           OK")
            success += 1
        except Exception as e:
            err = str(e).strip().split('\n')[0]
            print(f"           WARNING: {err}")

    cur.close()
    conn.close()
    print(f"\nDone! {success}/{len(statements)} statements succeeded.")

if __name__ == "__main__":
    main()
