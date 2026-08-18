import sqlite3
import argparse
import os
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass

@dataclass
class MigrationResult:
    modified: int
    backed_up_to: str = ""

def migrate(db_path: str, apply: bool = False) -> MigrationResult:
    if not os.path.exists(db_path):
        return MigrationResult(0)
        
    backup_path = ""
    if apply:
        backup_path = f"{db_path}.{int(datetime.now().timestamp())}.bak"
        shutil.copy2(db_path, backup_path)
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check if audit table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='qualifications_audit'")
    if not cur.fetchone():
        if apply:
            cur.execute('''
                CREATE TABLE qualifications_audit (
                    strategy_id TEXT,
                    status TEXT,
                    metrics TEXT,
                    reason TEXT,
                    retired_at TEXT
                )
            ''')
    
    # Find legacy QUALIFIED rows
    try:
        cur.execute("SELECT strategy_id, status, backtest_sharpe, wf_sharpe, paper_trades, backtest_return, wf_return, max_dd_pct FROM qualifications WHERE status='QUALIFIED'")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        rows = []
        
    modified = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    reason = "Terminal report: structural integrity and cost-model violations"
    
    if apply and rows:
        for row in rows:
            sid = row[0]
            status = row[1]
            metrics_dict = {
                "backtest_sharpe": row[2],
                "wf_sharpe": row[3],
                "paper_trades": row[4],
                "backtest_return": row[5],
                "wf_return": row[6],
                "max_dd_pct": row[7]
            }
            import json
            metrics_json = json.dumps(metrics_dict)
            
            # Append to audit
            cur.execute(
                "INSERT INTO qualifications_audit (strategy_id, status, metrics, reason, retired_at) VALUES (?, ?, ?, ?, ?)",
                (sid, "RETIRED/INVALIDATED", metrics_json, reason, now_iso)
            )
            # We don't delete from qualifications as per plan, we just update status
            cur.execute(
                "UPDATE qualifications SET status='RETIRED/INVALIDATED' WHERE strategy_id=?",
                (sid,)
            )
        conn.commit()
        modified = len(rows)
    else:
        modified = len(rows)
        
    conn.close()
    return MigrationResult(modified=modified, backed_up_to=backup_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--apply", action="store_true", help="Apply the migration (mutating)")
    args = parser.parse_args()
    
    res = migrate(args.db_path, apply=args.apply)
    print(f"Migration completed. Modified: {res.modified}, Backup: {res.backed_up_to}")
