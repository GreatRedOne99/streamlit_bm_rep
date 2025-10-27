"""
Fix the status of runs in the database
This can be used to mark incomplete runs as 'completed' if they have data
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import duckdb
    import pandas as pd

    db_path = "../data/replication.duckdb"

    print("=" * 80)
    print("RUN STATUS FIXER")
    print("=" * 80)

    conn = duckdb.connect(db_path, read_only=False)

    # Get all runs
    all_runs = conn.execute("""
        SELECT run_id, benchmark_ticker, run_date, status
        FROM backtest_runs
        ORDER BY run_date DESC
    """).df()

    if all_runs.empty:
        print("\n⚠️  No runs found in database")
        conn.close()
        sys.exit(0)

    print(f"\nFound {len(all_runs)} runs:")
    for idx, row in all_runs.iterrows():
        print(f"  {idx + 1}. {row['benchmark_ticker']} - {row['run_date']} - Status: {row['status']}")

    # Ask user which run to fix
    print("\n" + "=" * 80)
    choice = input("Enter run number to mark as 'completed' (or 'all' for all runs, 'q' to quit): ").strip()

    if choice.lower() == 'q':
        print("Exiting...")
        conn.close()
        sys.exit(0)

    if choice.lower() == 'all':
        # Mark all runs as completed
        conn.execute("UPDATE backtest_runs SET status = 'completed'")
        print(f"\n✅ Marked ALL {len(all_runs)} runs as 'completed'")

    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_runs):
                run_id = all_runs.iloc[idx]['run_id']
                conn.execute("UPDATE backtest_runs SET status = 'completed' WHERE run_id = ?", [run_id])
                print(f"\n✅ Marked run {run_id} as 'completed'")
            else:
                print(f"❌ Invalid selection: {choice}")
        except ValueError:
            print(f"❌ Invalid input: {choice}")

    # Show updated status
    print("\n" + "=" * 80)
    print("UPDATED STATUS:")
    print("=" * 80)

    updated_runs = conn.execute("""
        SELECT run_id, benchmark_ticker, run_date, status
        FROM backtest_runs
        ORDER BY run_date DESC
    """).df()

    for idx, row in updated_runs.iterrows():
        emoji = "✅" if row['status'] == 'completed' else "⚠️"
        print(f"  {emoji} {row['benchmark_ticker']} - {row['run_date']} - {row['status']}")

    conn.close()

    print("\n" + "=" * 80)
    print("Done! You can now run the Streamlit app:")
    print("  streamlit run Streamlit/benchmark_dashboard.py")
    print("=" * 80)

except ImportError as e:
    print(f"\n❌ ERROR: Missing required package")
    print(f"Details: {e}")
    print("\nPlease install required packages:")
    print("  pip install duckdb pandas")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
