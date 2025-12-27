import sqlite3
import shutil
import os
from datetime import datetime

# Backup the database first
backup_file = f'app_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
shutil.copy('app.db', backup_file)
print(f"Database backed up to: {backup_file}")

conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Check current schema
print("\n=== Current workflow_runs schema ===")
cursor.execute("PRAGMA table_info(workflow_runs)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]}) - PK:{col[5]} - FK:{col[4]}")

# Check foreign keys
print("\n=== Current foreign keys ===")
cursor.execute("PRAGMA foreign_key_list(workflow_runs)")
fks = cursor.fetchall()
for fk in fks:
    print(f"  {fk}")

# Get all data from workflow_runs
print("\n=== Fetching existing data ===")
cursor.execute("SELECT * FROM workflow_runs")
existing_data = cursor.fetchall()
print(f"Found {len(existing_data)} existing workflow runs")

# Drop and recreate the table with correct schema
print("\n=== Recreating workflow_runs table ===")
cursor.execute("DROP TABLE IF EXISTS workflow_runs")

create_table_sql = """
CREATE TABLE workflow_runs (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'pending',
    input_data JSON NOT NULL,
    output_data JSON,
    started_at DATETIME NOT NULL,
    completed_at DATETIME,
    error_message VARCHAR,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
)
"""
cursor.execute(create_table_sql)
print("Table recreated successfully")

# Restore data
if existing_data:
    print(f"\n=== Restoring {len(existing_data)} rows ===")
    # The column order from the old table
    insert_sql = """
    INSERT INTO workflow_runs 
    (workflow_id, status, input_data, output_data, started_at, completed_at, id, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.executemany(insert_sql, existing_data)
    print(f"Restored {len(existing_data)} rows")

conn.commit()

# Verify the new schema
print("\n=== New workflow_runs schema ===")
cursor.execute("PRAGMA table_info(workflow_runs)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]}) - PK:{col[5]}")

print("\n=== New foreign keys ===")
cursor.execute("PRAGMA foreign_key_list(workflow_runs)")
fks = cursor.fetchall()
for fk in fks:
    print(f"  Column: {fk[3]} -> {fk[2]}.{fk[4]}")

conn.close()
print("\n✅ Migration complete!")
