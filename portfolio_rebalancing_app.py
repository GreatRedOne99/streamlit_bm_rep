"""
Portfolio Rebalancing Orders Streamlit App

This app allows users to:
1. Select a benchmark and backtest run_id
2. Choose a rebalancing date from the backtest
3. Input their portfolio value
4. Generate buy/sell orders and trading reports

Author: Claude Code
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import duckdb
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Portfolio Rebalancing Orders",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data
def load_available_backtests(database_path: str = "data/replication.duckdb") -> pd.DataFrame:
    """Load all available backtest runs from database with retry logic"""
    import time
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            if not Path(database_path).exists():
                st.error(f"Database not found: {database_path}")
                return pd.DataFrame()
            
            # Use connection context manager for proper cleanup
            with duckdb.connect(database_path, read_only=True) as conn:
                # Get all backtest runs
                runs_query = """
                SELECT run_id, benchmark_ticker, start_date, end_date, run_date, description
                FROM backtest_runs 
                ORDER BY run_date DESC
                """
                runs_df = conn.execute(runs_query).df()
            
            # Rename columns for display
            if not runs_df.empty:
                runs_df.columns = ['run_id', 'benchmark', 'start_date', 'end_date', 'timestamp', 'description']
            
            return runs_df
            
        except Exception as e:
            if "being used by another process" in str(e) and attempt < max_retries - 1:
                st.warning(f"Database busy, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
                continue
            else:
                st.error(f"Error loading backtest runs after {max_retries} attempts: {e}")
                return pd.DataFrame()

@st.cache_data
def load_rebalancing_data(run_id: str, database_path: str = "data/replication.duckdb") -> Dict:
    """Load specific backtest data with retry logic"""
    import time
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            if not Path(database_path).exists():
                return {}
            
            # Use connection context manager for proper cleanup
            with duckdb.connect(database_path, read_only=True) as conn:
                data = {}
                
                # Load monthly rebalances - this is the core data we need
                rebalances_query = """
                SELECT rebalance_date, ticker, weight, position_rank, expected_return, actual_return
                FROM monthly_rebalances 
                WHERE run_id = ?
                ORDER BY rebalance_date, position_rank
                """
                rebalances_df = conn.execute(rebalances_query, [run_id]).df()
                
                if not rebalances_df.empty:
                    rebalances_df['rebalance_date'] = pd.to_datetime(rebalances_df['rebalance_date'])
                    data['rebalances'] = rebalances_df
            
            return data
            
        except Exception as e:
            if "being used by another process" in str(e) and attempt < max_retries - 1:
                st.warning(f"Database busy, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff
                continue
            else:
                st.error(f"Error loading backtest data after {max_retries} attempts: {e}")
                return {}

def extract_rebalance_dates_and_positions(backtest_data: Dict) -> pd.DataFrame:
    """Extract rebalancing dates and portfolio positions from backtest data"""
    if 'positions' not in backtest_data or backtest_data['positions'].empty:
        return pd.DataFrame()
    
    positions_df = backtest_data['positions'].copy()
    
    # Get unique rebalancing dates
    rebalance_dates = positions_df['date'].unique()
    rebalance_dates = sorted(rebalance_dates)
    
    # Create summary of each rebalance date
    rebalance_summary = []
    for date in rebalance_dates:
        date_positions = positions_df[positions_df['date'] == date]
        
        rebalance_summary.append({
            'rebalance_date': date,
            'num_positions': len(date_positions),
            'total_weight': date_positions['weight'].sum(),
            'top_holdings': ', '.join(date_positions.nlargest(3, 'weight')['ticker'].tolist())
        })
    
    return pd.DataFrame(rebalance_summary)

def generate_trading_orders_from_backtest(selected_date: str, 
                                        backtest_data: Dict,
                                        current_positions: Dict[str, float],
                                        portfolio_value: float) -> Dict:
    """Generate trading orders based on backtest portfolio for a specific date"""
    
    if 'positions' not in backtest_data or backtest_data['positions'].empty:
        return {'status': 'error', 'error': 'No positions data found in backtest'}
    
    # Get target portfolio for selected date
    positions_df = backtest_data['positions']
    target_positions_df = positions_df[positions_df['date'] == selected_date].copy()
    
    if target_positions_df.empty:
        return {'status': 'error', 'error': f'No portfolio data found for date {selected_date}'}
    
    # Convert weights to dollar amounts
    target_positions = {}
    for _, row in target_positions_df.iterrows():
        ticker = row['ticker']
        weight = row['weight']
        target_dollar_amount = weight * portfolio_value
        target_positions[ticker] = target_dollar_amount
    
    # Get all tickers from backtest
    all_tickers = set(positions_df['ticker'].unique())
    
    # Calculate trades needed
    trades = []
    total_buys = 0
    total_sells = 0
    
    for ticker in all_tickers:
        current_position = current_positions.get(ticker, 0.0)
        target_position = target_positions.get(ticker, 0.0)
        
        trade_amount = target_position - current_position
        
        if abs(trade_amount) > 1.0:  # Only trade if difference > $1
            if trade_amount > 0:
                action = "BUY"
                total_buys += trade_amount
            else:
                action = "SELL"
                total_sells += abs(trade_amount)
            
            trades.append({
                'ticker': ticker,
                'action': action,
                'dollar_amount': abs(trade_amount),
                'current_position': current_position,
                'target_position': target_position,
                'target_weight': target_positions.get(ticker, 0) / portfolio_value,
                'priority': 'HIGH' if abs(trade_amount) > 5000 else 'NORMAL'
            })
    
    # Sort trades by priority and amount
    trades.sort(key=lambda x: (x['priority'] == 'NORMAL', -x['dollar_amount']))
    
    # Calculate execution summary
    summary = {
        'total_trades': len(trades),
        'buy_orders': len([t for t in trades if t['action'] == 'BUY']),
        'sell_orders': len([t for t in trades if t['action'] == 'SELL']),
        'total_buy_amount': total_buys,
        'total_sell_amount': total_sells,
        'net_cash_flow': total_sells - total_buys,
        'estimated_turnover': (total_buys + total_sells) / portfolio_value if portfolio_value > 0 else 0
    }
    
    return {
        'status': 'success',
        'trades': trades,
        'summary': summary,
        'target_positions': target_positions,
        'rebalance_date': selected_date
    }

def create_execution_report(trading_result: Dict, portfolio_value: float) -> str:
    """Create formatted execution report"""
    if trading_result['status'] != 'success':
        return f"Error generating report: {trading_result.get('error', 'Unknown error')}"
    
    trades = trading_result['trades']
    summary = trading_result['summary']
    rebalance_date = trading_result['rebalance_date']
    
    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Create report
    report_lines = [
        "=" * 80,
        f"PORTFOLIO REBALANCING ORDERS - {rebalance_date}",
        f"Generated: {report_time}",
        "=" * 80,
        f"Portfolio Value: ${portfolio_value:,.2f}",
        f"Total Orders: {summary['total_trades']}",
        f"Estimated Turnover: {summary['estimated_turnover']:.1%}",
        "",
        "EXECUTION PRIORITY ORDER:",
        "-" * 50
    ]
    
    # Add trades in execution order
    for i, trade in enumerate(trades, 1):
        priority_marker = "🔴" if trade['priority'] == 'HIGH' else "🟡"
        weight_pct = trade['target_weight'] * 100
        report_lines.append(
            f"{i:2d}. {priority_marker} {trade['action']:<4} {trade['ticker']:<6} "
            f"${trade['dollar_amount']:>8,.0f} ({weight_pct:>5.1f}%) "
            f"[${trade['current_position']:>8,.0f} → ${trade['target_position']:>8,.0f}]"
        )
    
    report_lines.extend([
        "",
        "EXECUTION SUMMARY:",
        "-" * 30,
        f"Buy Orders:  {summary['buy_orders']} orders, ${summary['total_buy_amount']:>10,.2f}",
        f"Sell Orders: {summary['sell_orders']} orders, ${summary['total_sell_amount']:>10,.2f}",
        f"Net Cash:    ${summary['net_cash_flow']:>15,.2f}",
        "",
        "EXECUTION NOTES:",
        "-" * 20,
        "• Execute SELL orders first to generate cash",
        "• Execute BUY orders in priority sequence", 
        "• Monitor for significant price movements during execution",
        "• Consider using limit orders for large positions",
        "",
        "=" * 80
    ])
    
    return "\n".join(report_lines)

def main():
    st.title("📊 Portfolio Rebalancing Orders Generator")
    st.markdown("Generate buy/sell orders from backtest results for any rebalancing date")
    
    # Sidebar for selection
    with st.sidebar:
        st.header("🎯 Selection Parameters")
        
        # Load available backtests
        st.subheader("1. Select Backtest Run")
        available_runs = load_available_backtests()
        
        if available_runs.empty:
            st.error("No backtest runs found in database")
            st.stop()
        
        # Display runs with benchmark and timestamp
        run_display = []
        for _, row in available_runs.iterrows():
            timestamp_str = str(row['timestamp'])[:16] if row['timestamp'] is not None else "No Date"
            display_name = f"{row['benchmark']} - {row['run_id'][:8]} - {timestamp_str}"
            run_display.append(display_name)
        
        selected_run_display = st.selectbox("Choose backtest run:", run_display)
        
        if selected_run_display:
            # Extract run_id from display name
            selected_run_id = available_runs.iloc[run_display.index(selected_run_display)]['run_id']
            selected_benchmark = available_runs.iloc[run_display.index(selected_run_display)]['benchmark']
            
            st.info(f"Selected: {selected_benchmark} - {selected_run_id[:8]}...")
            
            # Load rebalancing data
            backtest_data = load_rebalancing_data(selected_run_id)
            
            if backtest_data and 'rebalances' in backtest_data:
                rebalances_df = backtest_data['rebalances']
                rebalance_dates = sorted(rebalances_df['rebalance_date'].unique())
                
                if rebalance_dates:
                    st.subheader("2. Select Rebalancing Date")
                    
                    # Format dates for display
                    date_display = []
                    for date in rebalance_dates:
                        date_positions = rebalances_df[rebalances_df['rebalance_date'] == date]
                        date_str = date.strftime('%Y-%m-%d')
                        display_str = f"{date_str} ({len(date_positions)} positions)"
                        date_display.append(display_str)
                    
                    selected_date_display = st.selectbox("Choose rebalancing date:", date_display)
                    selected_date = rebalance_dates[date_display.index(selected_date_display)]
                    # Show rebalancing details for selected date
                    st.subheader("📊 Rebalancing Details")
                    
                    # Get current and previous period data
                    current_positions = rebalances_df[rebalances_df['rebalance_date'] == selected_date].sort_values('position_rank')
                    
                    # Show portfolio composition
                    st.markdown("**Portfolio Composition:**")
                    composition_display = current_positions[['ticker', 'weight', 'position_rank']].copy()
                    composition_display['weight_pct'] = (composition_display['weight'] * 100).round(2)
                    composition_display = composition_display[['ticker', 'weight_pct', 'position_rank']]
                    composition_display.columns = ['Ticker', 'Weight (%)', 'Rank']
                    st.dataframe(composition_display, hide_index=True, use_container_width=True)
                else:
                    st.error("No rebalancing data found")
            else:
                st.error("No backtest data loaded")
    
    # Show info message in main area if no run selected
    if 'selected_run_display' not in locals():
        st.info("👆 Please select a backtest run from the sidebar to begin")

if __name__ == "__main__":
    main()