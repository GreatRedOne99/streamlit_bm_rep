"""
Quick diagnostic script to check what's in the backtest_runs table
Run this to see all your runs and their statuses
"""
import sys
import os
sys.path.append('..')
# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    # Import the storage class to use its connection
    from data_processing.backtest_storage import BacktestResultsStorage
    import duckdb

    db_path = "../data/replication.duckdb"

    print("=" * 80)
    print("DATABASE DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"\nDatabase: {db_path}")

    conn = duckdb.connect(db_path, read_only=True)

    # Query all runs
    print("\n" + "=" * 80)
    print("ALL BACKTEST RUNS")
    print("=" * 80)

    query = """
    SELECT
        run_id,
        benchmark_ticker,
        run_date,
        start_date,
        end_date,
        status,
        total_months,
        success_rate,
        description
    FROM backtest_runs
    ORDER BY run_date DESC
    """

    all_runs = conn.execute(query).df()

    if all_runs.empty:
        print("\n⚠️  NO RUNS FOUND IN DATABASE!")
    else:
        print(f"\nTotal runs: {len(all_runs)}")
        print("\n" + all_runs.to_string(index=False))

        # Show status breakdown
        print("\n" + "=" * 80)
        print("STATUS BREAKDOWN")
        print("=" * 80)
        status_counts = all_runs['status'].value_counts()
        for status, count in status_counts.items():
            print(f"  {status}: {count}")

        # Show most recent run details
        print("\n" + "=" * 80)
        print("MOST RECENT RUN DETAILS")
        print("=" * 80)
        latest = all_runs.iloc[0]
        print(f"\nRun ID: {latest['run_id']}")
        print(f"Benchmark: {latest['benchmark_ticker']}")
        print(f"Run Date: {latest['run_date']}")
        print(f"Period: {latest['start_date']} to {latest['end_date']}")
        print(f"Status: {latest['status']}")
        print(f"Success Rate: {latest['success_rate']:.1%}")
        print(f"Total Months: {latest['total_months']}")

        # Check if data exists for latest run
        latest_run_id = latest['run_id']

        print("\n" + "=" * 80)
        print(f"DATA CHECK FOR LATEST RUN: {latest_run_id}")
        print("=" * 80)

        tables = [
            ('daily_returns', 'SELECT COUNT(*) as count FROM daily_returns WHERE run_id = ?'),
            ('monthly_rebalances', 'SELECT COUNT(*) as count FROM monthly_rebalances WHERE run_id = ?'),
            ('portfolio_positions', 'SELECT COUNT(*) as count FROM portfolio_positions WHERE run_id = ?'),
            ('monthly_metrics', 'SELECT COUNT(*) as count FROM monthly_metrics WHERE run_id = ?')
        ]

        for table_name, query in tables:
            try:
                result = conn.execute(query, [latest_run_id]).df()
                count = result['count'].iloc[0]
                status = "✅" if count > 0 else "❌"
                print(f"{status} {table_name}: {count} records")
            except Exception as e:
                print(f"❌ {table_name}: Error - {e}")

    conn.close()

    print("\n" + "=" * 80)
    print("DIAGNOSIS COMPLETE")
    print("=" * 80)
    print("\n💡 If the latest run has status != 'completed', that was the issue!")
    print("💡 The Streamlit app has been fixed to show ALL runs regardless of status")
    print("💡 Run: streamlit run Streamlit/benchmark_dashboard.py")

except ImportError as e:
    print(f"\n❌ ERROR: Missing required package")
    print(f"Details: {e}")
    print("\nPlease install required packages:")
    print("  pip install duckdb pandas")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
