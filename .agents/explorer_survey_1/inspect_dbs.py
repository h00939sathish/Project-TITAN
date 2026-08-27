import sqlite3
import os
import json

dbs = ['.titan_state.db', 'dummy_state.db', 'research_data/titan_research.db', 'research_data/test.db']

for db_path in dbs:
    print('='*70)
    print(f'DB: {db_path} (exists: {os.path.exists(db_path)})')
    if not os.path.exists(db_path):
        continue
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE type in ('table', 'view');")
    items = cursor.fetchall()
    print(f'Schema items ({len(items)}):')
    for name, itype, sql in items:
        print(f'  [{itype}] {name}')
        if itype == 'table':
            try:
                cursor.execute(f'SELECT count(*) FROM "{name}"')
                count = cursor.fetchone()[0]
                print(f'    row count: {count}')
                cursor.execute(f'PRAGMA table_info("{name}")')
                cols = [c[1] for c in cursor.fetchall()]
                print(f'    columns: {cols}')
                cursor.execute(f'SELECT * FROM "{name}" LIMIT 3')
                samples = cursor.fetchall()
                if samples:
                    print(f'    sample row: {samples[0]}')
            except Exception as e:
                print(f'    err: {e}')
    conn.close()
