"""Quick script to check backtest runs in database"""
import sys
sys.path.insert(0, 'c:/Users/johnd/OneDrive/CeCodeAI/Benchmark_Replicator')

try:
    import duckdb
    import pandas as pd
    from pathlib import Path

    db_path = "../data/replication.duckdb"

    if not Path(db_path).exists():
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    conn = duckdb.connect(db_path, read_only=True)

    # Check all runs
    print("\n=== ALL BACKTEST RUNS ===")
    all_runs = conn.execute("""
        SELECT run_id, benchmark_ticker, start_date, end_date, run_date, status
        FROM backtest_runs
        ORDER BY run_date DESC
    """).df()

    print(f"\nTotal runs: {len(all_runs)}")
    print(all_runs.to_string())

    # Check completed runs
    print("\n\n=== COMPLETED RUNS ONLY ===")
    completed_runs = conn.execute("""
        SELECT run_id, benchmark_ticker, start_date, end_date, run_date, status
        FROM backtest_runs
        WHERE status = 'completed'
        ORDER BY run_date DESC
    """).df()

    print(f"\nCompleted runs: {len(completed_runs)}")
    print(completed_runs.to_string())

    # Check for latest run
    print("\n\n=== LATEST RUN ===")
    latest = conn.execute("""
        SELECT run_id, benchmark_ticker, start_date, end_date, run_date, status
        FROM backtest_runs
        ORDER BY run_date DESC
        LIMIT 1
    """).df()
    print(latest.to_string())

    # Check if there's any date filtering issue
    if not latest.empty:
        latest_run_id = latest.iloc[0]['run_id']
        print(f"\n\n=== DATA FOR LATEST RUN: {latest_run_id} ===")

        # Check daily returns
        daily_count = conn.execute(f"""
            SELECT COUNT(*) as count FROM daily_returns
            WHERE run_id = '{latest_run_id}'
        """).df()
        print(f"Daily returns records: {daily_count['count'].iloc[0]}")

        # Check positions
        positions_count = conn.execute(f"""
            SELECT COUNT(*) as count FROM portfolio_positions
            WHERE run_id = '{latest_run_id}'
        """).df()
        print(f"Portfolio positions records: {positions_count['count'].iloc[0]}")

        # Check metrics
        metrics_count = conn.execute(f"""
            SELECT COUNT(*) as count FROM monthly_metrics
            WHERE run_id = '{latest_run_id}'
        """).df()
        print(f"Monthly metrics records: {metrics_count['count'].iloc[0]}")

    conn.close()

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
