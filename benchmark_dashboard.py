"""
Benchmark Replicator Dashboard
Professional Streamlit application for showcasing portfolio replication results
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import duckdb
from datetime import datetime
import json
from pathlib import Path
import glob

# Page configuration
st.set_page_config(
    page_title="Benchmark Replicator | Portfolio Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .big-metric {
        font-size: 36px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# Data Loading Functions
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_available_runs():
    """Get all available backtest runs grouped by benchmark"""
    db_path = "data/replication.duckdb"
    if not Path(db_path).exists():
        return {}
    
    conn = duckdb.connect(db_path, read_only=True)
    
    # Get all runs grouped by benchmark
    runs_query = """
    SELECT run_id, benchmark_ticker, start_date, end_date, run_date,
           description, status
    FROM backtest_runs
    ORDER BY benchmark_ticker, run_date DESC
    """
    runs_df = conn.execute(runs_query).df()
    conn.close()
    
    # Group by benchmark
    runs_by_benchmark = {}
    for _, row in runs_df.iterrows():
        benchmark = row['benchmark_ticker']
        if benchmark not in runs_by_benchmark:
            runs_by_benchmark[benchmark] = []
        
        # Add status indicator to description
        status_emoji = "✅" if row['status'] == 'completed' else ("⚠️" if row['status'] == 'failed' else "🔄")
        description = row['description'] if row['description'] else f"Run {row['run_date'].strftime('%Y-%m-%d %H:%M')}"

        runs_by_benchmark[benchmark].append({
            'run_id': row['run_id'],
            'run_date': row['run_date'],
            'description': f"{status_emoji} {description}",
            'date_range': f"{row['start_date']} to {row['end_date']}",
            'status': row['status']
        })
    
    return runs_by_benchmark

@st.cache_data(ttl=300)  # Cache for 5 minutes  
def load_backtest_results(run_id):
    """Load backtest results for a specific run_id"""
    
    data = {}
    
    # Try loading from DuckDB first
    db_path = "data/replication.duckdb"
    if Path(db_path).exists():
        conn = duckdb.connect(db_path, read_only=True)
        
        # Get run info
        run_query = """
        SELECT run_id, benchmark_ticker, start_date, end_date, run_date, description
        FROM backtest_runs 
        WHERE run_id = ?
        """
        run_info = conn.execute(run_query, [run_id]).df()
        
        if not run_info.empty:            
            # Load daily returns
            returns_query = """
            SELECT date, portfolio_return, benchmark_return, excess_return
            FROM daily_returns 
            WHERE run_id = ?
            ORDER BY date
            """
            daily_returns_df = conn.execute(returns_query, [run_id]).df()
            
            # Calculate cumulative returns
            if not daily_returns_df.empty:
                daily_returns_df['portfolio_cumulative'] = (1 + daily_returns_df['portfolio_return']).cumprod() - 1
                daily_returns_df['benchmark_cumulative'] = (1 + daily_returns_df['benchmark_return']).cumprod() - 1
            
            data['daily_returns'] = daily_returns_df
            
            # Load portfolio positions
            positions_query = """
            SELECT date, ticker, weight 
            FROM portfolio_positions 
            WHERE run_id = ?
            ORDER BY date, weight DESC
            """
            data['positions'] = conn.execute(positions_query, [run_id]).df()
            
            # Load monthly metrics
            metrics_query = """
            SELECT * FROM monthly_metrics 
            WHERE run_id = ?
            ORDER BY date
            """
            data['metrics'] = conn.execute(metrics_query, [run_id]).df()
            
            data['run_info'] = run_info
        
        conn.close()
    
    return data, None if data else "No data found"

@st.cache_data
def calculate_performance_metrics(daily_returns_df):
    """Calculate comprehensive performance metrics"""
    
    if daily_returns_df.empty:
        return {}
    
    metrics = {}
    
    # Annualized returns
    metrics['portfolio_annual_return'] = daily_returns_df['portfolio_return'].mean() * 252
    metrics['benchmark_annual_return'] = daily_returns_df['benchmark_return'].mean() * 252
    metrics['excess_return'] = metrics['portfolio_annual_return'] - metrics['benchmark_annual_return']
    
    # Risk metrics
    metrics['portfolio_volatility'] = daily_returns_df['portfolio_return'].std() * np.sqrt(252)
    metrics['benchmark_volatility'] = daily_returns_df['benchmark_return'].std() * np.sqrt(252)
    metrics['tracking_error'] = daily_returns_df['excess_return'].std() * np.sqrt(252)
    
    # Risk-adjusted metrics
    metrics['portfolio_sharpe'] = metrics['portfolio_annual_return'] / metrics['portfolio_volatility']
    metrics['benchmark_sharpe'] = metrics['benchmark_annual_return'] / metrics['benchmark_volatility']
    metrics['information_ratio'] = metrics['excess_return'] / metrics['tracking_error'] if metrics['tracking_error'] > 0 else 0
    
    # Drawdown calculation
    cum_returns = (1 + daily_returns_df['portfolio_return']).cumprod()
    running_max = cum_returns.expanding().max()
    drawdown = (cum_returns - running_max) / running_max
    metrics['max_drawdown'] = drawdown.min()
    
    # Win rate
    metrics['win_rate'] = (daily_returns_df['excess_return'] > 0).mean() * 100
    
    return metrics

# ============================================================================
# Visualization Functions
# ============================================================================

def create_performance_chart(daily_returns_df, benchmark_name="Benchmark"):
    """Create interactive cumulative performance chart"""
    
    fig = go.Figure()
    
    # Add portfolio line
    fig.add_trace(go.Scatter(
        x=daily_returns_df['date'],
        y=daily_returns_df['portfolio_cumulative'],
        name='Replica Portfolio',
        line=dict(color='#667eea', width=3),
        hovertemplate='%{y:.1%}<extra></extra>'
    ))
    
    # Add benchmark line
    fig.add_trace(go.Scatter(
        x=daily_returns_df['date'],
        y=daily_returns_df['benchmark_cumulative'],
        name=benchmark_name,
        line=dict(color='#f59e0b', width=3),
        hovertemplate='%{y:.1%}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title={
            'text': f'Cumulative Performance: Portfolio vs {benchmark_name}',
            'font': {'size': 24}
        },
        xaxis_title="Date",
        yaxis_title="Cumulative Return",
        yaxis_tickformat='.0%',
        hovermode='x unified',
        height=500,
        template='plotly_white',
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        )
    )
    
    return fig

def create_holdings_evolution_chart(positions_df):
    """Create portfolio holdings evolution chart"""
    
    if positions_df.empty:
        return None
    
    # Count holdings per date
    holdings_count = positions_df.groupby('date')['ticker'].count().reset_index()
    holdings_count.columns = ['date', 'holdings']
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=holdings_count['date'],
        y=holdings_count['holdings'],
        mode='lines+markers',
        line=dict(color='#10b981', width=3),
        marker=dict(size=8),
        fill='tozeroy',
        fillcolor='rgba(16, 185, 129, 0.1)'
    ))
    
    fig.update_layout(
        title={'text': 'Portfolio Holdings Over Time', 'font': {'size': 20}},
        xaxis_title="Date",
        yaxis_title="Number of Holdings",
        height=400,
        template='plotly_white'
    )
    
    return fig

def create_tracking_error_chart(daily_returns_df):
    """Create rolling tracking error visualization"""
    
    # Calculate 60-day rolling tracking error
    rolling_te = daily_returns_df.set_index('date')['excess_return'].rolling(60).std() * np.sqrt(252)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=rolling_te.index,
        y=rolling_te.values * 100,
        mode='lines',
        line=dict(color='#ef4444', width=2),
        fill='tozeroy',
        fillcolor='rgba(239, 68, 68, 0.1)',
        name='Tracking Error'
    ))
    
    # Add target range
    fig.add_hline(y=2, line_dash="dash", line_color="green", annotation_text="Target Min (2%)")
    fig.add_hline(y=4, line_dash="dash", line_color="orange", annotation_text="Target Max (4%)")
    
    fig.update_layout(
        title={'text': '60-Day Rolling Tracking Error', 'font': {'size': 20}},
        xaxis_title="Date",
        yaxis_title="Tracking Error (%)",
        height=400,
        template='plotly_white',
        showlegend=False
    )
    
    return fig

def create_feature_importance_chart(metrics_df):
    """Create feature importance evolution chart"""
    
    if 'feature_importance' not in metrics_df.columns:
        return None
    
    # Parse feature importance JSON
    feature_data = []
    for _, row in metrics_df.iterrows():
        if row['feature_importance'] and isinstance(row['feature_importance'], str):
            try:
                fi = json.loads(row['feature_importance'])
                
                # Handle nested structure: {"feature": {idx: name}, "importance": {idx: value}}
                if 'feature' in fi and 'importance' in fi:
                    features = fi['feature']
                    importances = fi['importance']
                    
                    for idx in features.keys():
                        if idx in importances:
                            try:
                                feature_name = str(features[idx])
                                importance_val = float(importances[idx])
                                feature_data.append({
                                    'date': row['date'],
                                    'feature': feature_name,
                                    'importance': importance_val
                                })
                            except (ValueError, TypeError):
                                continue
                
                # Fallback: handle direct feature->importance mapping  
                elif isinstance(fi, dict):
                    for feature, importance in fi.items():
                        try:
                            importance_val = float(importance)
                            feature_data.append({
                                'date': row['date'],
                                'feature': str(feature),
                                'importance': importance_val
                            })
                        except (ValueError, TypeError):
                            continue
            except:
                continue
    
    if not feature_data:
        return None
    
    fi_df = pd.DataFrame(feature_data)
    
    # Ensure importance column is numeric
    fi_df['importance'] = pd.to_numeric(fi_df['importance'], errors='coerce')
    fi_df = fi_df.dropna(subset=['importance'])
    
    if fi_df.empty:
        return None
    
    # Get top 5 features by average importance
    top_features = fi_df.groupby('feature')['importance'].mean().nlargest(5).index
    
    fig = go.Figure()
    
    for feature in top_features:
        feature_series = fi_df[fi_df['feature'] == feature]
        fig.add_trace(go.Scatter(
            x=feature_series['date'],
            y=feature_series['importance'],
            name=feature,
            mode='lines+markers',
            line=dict(width=2)
        ))
    
    fig.update_layout(
        title={'text': 'ML Model Feature Importance Over Time', 'font': {'size': 20}},
        xaxis_title="Date",
        yaxis_title="Feature Importance",
        height=400,
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig

def create_stock_attribution_chart(positions_df):
    """Create individual stock attribution analysis"""
    
    if positions_df.empty:
        return None
    
    # Calculate average weight per stock
    avg_weights = positions_df.groupby('ticker')['weight'].mean().sort_values(ascending=False).head(10)
    
    if avg_weights.empty:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=avg_weights.values,
        y=avg_weights.index,
        orientation='h',
        marker_color='#667eea',
        text=[f'{w:.1%}' for w in avg_weights.values],
        textposition='inside'
    ))
    
    fig.update_layout(
        title={'text': 'Top 10 Stock Holdings (Average Weight)', 'font': {'size': 20}},
        xaxis_title="Average Weight (%)",
        xaxis_tickformat='.0%',
        height=400,
        template='plotly_white',
        showlegend=False
    )
    
    return fig

def create_feature_importance_bar_chart(metrics_df):
    """Create current feature importance bar chart (latest month)"""
    
    if 'feature_importance' not in metrics_df.columns or metrics_df.empty:
        return None
    
    # Get latest month's feature importance
    latest_row = metrics_df.iloc[-1]
    
    if not latest_row['feature_importance']:
        return None
    
    try:
        fi = json.loads(latest_row['feature_importance'])
        
        # Handle nested structure
        if 'feature' in fi and 'importance' in fi:
            features = fi['feature']
            importances = fi['importance']
            
            feature_data = []
            for idx in features.keys():
                if idx in importances:
                    try:
                        feature_name = str(features[idx])
                        importance_val = float(importances[idx])
                        feature_data.append({
                            'feature': feature_name,
                            'importance': importance_val
                        })
                    except (ValueError, TypeError):
                        continue
        
        # Fallback: handle direct feature->importance mapping  
        elif isinstance(fi, dict):
            feature_data = []
            for feature, importance in fi.items():
                try:
                    importance_val = float(importance)
                    feature_data.append({
                        'feature': str(feature),
                        'importance': importance_val
                    })
                except (ValueError, TypeError):
                    continue
        else:
            return None
            
    except:
        return None
    
    if not feature_data:
        return None
    
    fi_df = pd.DataFrame(feature_data).sort_values('importance', ascending=True).tail(10)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=fi_df['importance'],
        y=fi_df['feature'],
        orientation='h',
        marker_color='#10b981',
        text=[f'{imp:.3f}' for imp in fi_df['importance']],
        textposition='inside'
    ))
    
    fig.update_layout(
        title={'text': f'Current Feature Importance (Latest Month)', 'font': {'size': 20}},
        xaxis_title="Importance Score",
        height=400,
        template='plotly_white',
        showlegend=False
    )
    
    return fig

# ============================================================================
# Main Dashboard
# ============================================================================

def main():
    # Header
    st.markdown("# 📊 Benchmark Replicator Portfolio System")
    st.markdown("### Advanced ML-Driven Portfolio Optimization & Analysis Platform")
    st.markdown("---")
    
    # Get available runs first
    available_runs = get_available_runs()
    
    if not available_runs:
        st.error("❌ No completed backtest runs found in database")
        st.info("Please run the backtest notebook first to generate results.")
        return
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Benchmark selection
        available_benchmarks = list(available_runs.keys())
        benchmark = st.selectbox(
            "Select Benchmark",
            available_benchmarks,
            help="Choose the benchmark ETF to analyze"
        )
        
        # Run selection for the chosen benchmark
        if benchmark in available_runs:
            runs_for_benchmark = available_runs[benchmark]
            
            # Create display options for runs
            run_options = []
            run_mapping = {}
            
            for run_info in runs_for_benchmark:
                display_name = f"{run_info['description']} ({run_info['date_range']})"
                run_options.append(display_name)
                run_mapping[display_name] = run_info['run_id']
            
            selected_run_display = st.selectbox(
                "Select Backtest Run",
                run_options,
                help="Choose specific backtest run to analyze"
            )
            
            selected_run_id = run_mapping[selected_run_display]
        else:
            selected_run_id = None
        
        # Refresh button
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 📈 System Info")
        st.info("""
        **Two-Stage Architecture:**
        - Stage 1: ML Portfolio Construction
        - Stage 2: Professional Analysis
        
        **Technology Stack:**
        - XGBoost Classification
        - CVXPY Optimization
        - DuckDB Storage
        """)
    
    # Load data for selected run
    if selected_run_id:
        with st.spinner("Loading backtest results..."):
            data, error = load_backtest_results(selected_run_id)
            
            # Debug info
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔍 Debug Info")
            st.sidebar.text(f"Selected Run ID: {selected_run_id[:20]}...")
            if 'daily_returns' in data:
                st.sidebar.text(f"Daily Returns: {len(data['daily_returns'])} records")
                if not data['daily_returns'].empty:
                    final_return = data['daily_returns']['portfolio_cumulative'].iloc[-1]
                    st.sidebar.text(f"Final Return: {final_return:.2%}")
    else:
        data, error = {}, "No run selected"
    
    if error:
        st.error(f"❌ {error}")
        st.info("Please run the backtest notebook first to generate results.")
        return
    
    # Calculate metrics
    if 'daily_returns' in data:
        metrics = calculate_performance_metrics(data['daily_returns'])
    else:
        st.warning("⚠️ Daily returns data not found")
        metrics = {}
    
    # Executive Summary Section
    st.markdown("## 🎯 Executive Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Information Ratio</div>
            <div class="big-metric">{:.3f}</div>
        </div>
        """.format(metrics.get('information_ratio', 0)), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <div class="metric-label">Tracking Error</div>
            <div class="big-metric">{:.2%}</div>
        </div>
        """.format(metrics.get('tracking_error', 0)), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <div class="metric-label">Excess Return</div>
            <div class="big-metric">{:.2%}</div>
        </div>
        """.format(metrics.get('excess_return', 0)), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <div class="metric-label">Win Rate</div>
            <div class="big-metric">{:.1f}%</div>
        </div>
        """.format(metrics.get('win_rate', 0)), unsafe_allow_html=True)
    
    # Tabbed interface for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Performance", "🎯 Portfolio Analytics", "🤖 ML Insights", 
        "💼 Business Intelligence", "📊 Raw Data"
    ])
    
    with tab1:
        st.markdown("### Performance Analysis")
        
        if 'daily_returns' in data and not data['daily_returns'].empty:
            # Cumulative performance chart
            fig_perf = create_performance_chart(data['daily_returns'], benchmark)
            st.plotly_chart(fig_perf, use_container_width=True)
            
            # Performance metrics comparison
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Portfolio Metrics")
                st.metric("Annual Return", f"{metrics.get('portfolio_annual_return', 0):.2%}")
                st.metric("Volatility", f"{metrics.get('portfolio_volatility', 0):.2%}")
                st.metric("Sharpe Ratio", f"{metrics.get('portfolio_sharpe', 0):.3f}")
                st.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2%}")
            
            with col2:
                st.markdown(f"#### {benchmark} Benchmark")
                st.metric("Annual Return", f"{metrics.get('benchmark_annual_return', 0):.2%}")
                st.metric("Volatility", f"{metrics.get('benchmark_volatility', 0):.2%}")
                st.metric("Sharpe Ratio", f"{metrics.get('benchmark_sharpe', 0):.3f}")
        
        else:
            st.info("No performance data available")
    
    with tab2:
        st.markdown("### Portfolio Characteristics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'positions' in data:
                fig_holdings = create_holdings_evolution_chart(data['positions'])
                if fig_holdings:
                    st.plotly_chart(fig_holdings, use_container_width=True)
        
        with col2:
            if 'daily_returns' in data:
                fig_te = create_tracking_error_chart(data['daily_returns'])
                if fig_te:
                    st.plotly_chart(fig_te, use_container_width=True)
        
        # Enhanced portfolio analytics
        if 'positions' in data and not data['positions'].empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Current Portfolio Composition")
                latest_date = data['positions']['date'].max()
                current_positions = data['positions'][data['positions']['date'] == latest_date]
                
                if not current_positions.empty:
                    fig_pie = px.pie(
                        current_positions, 
                        values='weight', 
                        names='ticker',
                        title=f"Portfolio Weights as of {latest_date}",
                        height=400
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.markdown("### Top Holdings Impact")
                fig_attribution = create_stock_attribution_chart(data['positions'])
                if fig_attribution:
                    st.plotly_chart(fig_attribution, use_container_width=True)
                else:
                    st.info("Stock attribution data not available")
        
            # Stock-level performance table
            st.markdown("### Stock Performance Attribution")
            if not current_positions.empty:
                # Show current holdings with weights
                display_positions = current_positions.copy()
                display_positions['weight'] = display_positions['weight'].apply(lambda x: f"{x:.2%}")
                display_positions = display_positions.sort_values('weight', ascending=False)
                st.dataframe(
                    display_positions[['ticker', 'weight']].rename(columns={
                        'ticker': 'Stock Symbol',
                        'weight': 'Portfolio Weight'
                    }), 
                    use_container_width=True
                )
    
    with tab3:
        st.markdown("### Machine Learning Model Insights")
        
        if 'metrics' in data and not data['metrics'].empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Feature Importance Over Time")
                fig_features = create_feature_importance_chart(data['metrics'])
                if fig_features:
                    st.plotly_chart(fig_features, use_container_width=True)
                else:
                    st.info("Feature importance time series not available")
            
            with col2:
                st.markdown("#### Current Feature Rankings")
                fig_features_bar = create_feature_importance_bar_chart(data['metrics'])
                if fig_features_bar:
                    st.plotly_chart(fig_features_bar, use_container_width=True)
                else:
                    st.info("Latest feature importance not available")
        else:
            st.info("ML model data not available")
        
        # ML MODEL PERFORMANCE VISUALIZATION (from notebook cell 17)
        st.markdown("### 🤖 ML Model Performance Analysis")
        
        if 'metrics' in data and not data['metrics'].empty:
            metrics_df = data['metrics']
            
            # Create time series charts for ML metrics
            col1, col2 = st.columns(2)
            
            with col1:
                if 'ml_auc_score' in metrics_df.columns:
                    fig_auc = go.Figure()
                    fig_auc.add_trace(go.Scatter(
                        x=metrics_df['date'],
                        y=metrics_df['ml_auc_score'],
                        mode='lines+markers',
                        line=dict(color='blue', width=2),
                        marker=dict(size=6),
                        name='AUC Score'
                    ))
                    fig_auc.add_hline(y=0.5, line_dash="dash", line_color="red", 
                                     annotation_text="Random (0.5)")
                    fig_auc.update_layout(
                        title='AUC Score Over Time',
                        yaxis_title='AUC Score',
                        height=300,
                        template='plotly_white'
                    )
                    st.plotly_chart(fig_auc, use_container_width=True)
            
            with col2:
                if 'ml_accuracy' in metrics_df.columns:
                    fig_acc = go.Figure()
                    fig_acc.add_trace(go.Scatter(
                        x=metrics_df['date'],
                        y=metrics_df['ml_accuracy'],
                        mode='lines+markers',
                        line=dict(color='green', width=2),
                        marker=dict(size=6),
                        name='Accuracy'
                    ))
                    fig_acc.update_layout(
                        title='Accuracy Over Time',
                        yaxis_title='Accuracy',
                        yaxis_tickformat='.0%',
                        height=300,
                        template='plotly_white'
                    )
                    st.plotly_chart(fig_acc, use_container_width=True)
            
            # Precision vs Recall scatter plot
            if all(col in metrics_df.columns for col in ['ml_precision', 'ml_recall']):
                fig_pr = go.Figure()
                fig_pr.add_trace(go.Scatter(
                    x=metrics_df['ml_recall'],
                    y=metrics_df['ml_precision'],
                    mode='markers',
                    marker=dict(size=8, color=metrics_df.index, colorscale='viridis'),
                    text=metrics_df['date'].dt.strftime('%Y-%m'),
                    hovertemplate='<b>%{text}</b><br>' +
                                 'Recall: %{x:.1%}<br>' +
                                 'Precision: %{y:.1%}<extra></extra>',
                    name='Precision vs Recall'
                ))
                fig_pr.update_layout(
                    title='Precision vs Recall Evolution',
                    xaxis_title='Recall',
                    yaxis_title='Precision',
                    xaxis_tickformat='.0%',
                    yaxis_tickformat='.0%',
                    height=400,
                    template='plotly_white'
                )
                st.plotly_chart(fig_pr, use_container_width=True)
            
            # F1 Score time series
            if 'ml_f1_score' in metrics_df.columns:
                fig_f1 = go.Figure()
                fig_f1.add_trace(go.Scatter(
                    x=metrics_df['date'],
                    y=metrics_df['ml_f1_score'],
                    mode='lines+markers',
                    line=dict(color='purple', width=2),
                    marker=dict(size=6),
                    name='F1-Score'
                ))
                fig_f1.update_layout(
                    title='F1-Score Over Time',
                    yaxis_title='F1-Score',
                    yaxis_tickformat='.0%',
                    height=300,
                    template='plotly_white'
                )
                st.plotly_chart(fig_f1, use_container_width=True)
        
        # Model performance metrics from database
        st.markdown("### Model Performance Summary")
        col1, col2, col3 = st.columns(3)
        
        if 'metrics' in data and not data['metrics'].empty:
            metrics_df = data['metrics']
            
            # Calculate average ML metrics for this run
            avg_accuracy = metrics_df['ml_accuracy'].mean() if 'ml_accuracy' in metrics_df.columns else None
            avg_auc = metrics_df['ml_auc_score'].mean() if 'ml_auc_score' in metrics_df.columns else None
            avg_precision = metrics_df['ml_precision'].mean() if 'ml_precision' in metrics_df.columns else None
            
            # Count unique features from feature importance data
            feature_count = 0
            if not metrics_df.empty and 'feature_importance' in metrics_df.columns:
                for _, row in metrics_df.iterrows():
                    if row['feature_importance']:
                        try:
                            fi = json.loads(row['feature_importance'])
                            if 'feature' in fi:
                                feature_count = max(feature_count, len(fi['feature']))
                        except:
                            continue
            
            with col1:
                if avg_accuracy is not None:
                    st.metric("ML Accuracy", f"{avg_accuracy:.1%}")
                else:
                    st.metric("ML Accuracy", "N/A")
            
            with col2:
                if avg_auc is not None:
                    st.metric("AUC Score", f"{avg_auc:.3f}")
                else:
                    st.metric("AUC Score", "N/A")
            
            with col3:
                if avg_precision is not None:
                    st.metric("ML Precision", f"{avg_precision:.1%}")
                else:
                    st.metric("ML Precision", "N/A")
        else:
            # Fallback if no metrics data
            with col1:
                st.metric("ML Accuracy", "N/A")
            with col2:
                st.metric("AUC Score", "N/A") 
            with col3:
                st.metric("ML Precision", "N/A")
    
    with tab4:
        st.markdown("### 💼 Business Intelligence & Strategic Insights")
        
        # Dynamic Executive Summary based on actual data
        if metrics:
            # Calculate dynamic metrics - Fix numpy formatting issues with safe conversion
            def safe_float(value, default=0.0):
                try:
                    return float(value) if value is not None else default
                except (ValueError, TypeError):
                    return default
            
            total_return = safe_float(metrics.get('portfolio_annual_return', 0))
            excess_return = safe_float(metrics.get('excess_return', 0))
            sharpe_ratio = safe_float(metrics.get('portfolio_sharpe', 0))
            tracking_error = safe_float(metrics.get('tracking_error', 0))
            info_ratio = safe_float(metrics.get('information_ratio', 0))
            
            # Get actual portfolio positions count
            actual_positions = 0
            benchmark_holdings_estimate = 2000  # Estimate for broad benchmarks
            
            if 'positions' in data and not data['positions'].empty:
                latest_date = data['positions']['date'].max()
                actual_positions = int(len(data['positions'][data['positions']['date'] == latest_date]))
                # Adjust benchmark estimate based on actual benchmark
                if benchmark in ['SPY', 'IWM', 'QQQ']:
                    benchmark_holdings_estimate = 2000 if benchmark == 'IWM' else 500
                elif benchmark in ['DIA']:
                    benchmark_holdings_estimate = 30
            
            efficiency_reduction = float((benchmark_holdings_estimate - actual_positions) / benchmark_holdings_estimate) if actual_positions > 0 else 0.0
            
            # Dynamic Key Achievements - Clean formatting
            achievement_text = f"""
            **🏆 Key Achievements:**
            - Successfully replicated {benchmark} with **{actual_positions:,} holdings** vs {benchmark_holdings_estimate:,}+ in benchmark ({efficiency_reduction:.0%} reduction)
            - Achieved **{excess_return:.2%} excess return** with Information Ratio of **{info_ratio:.2f}**
            - Maintained **{tracking_error:.2%} tracking error** {'✅ within target (2-4%)' if 0.02 <= tracking_error <= 0.04 else '⚠️ outside target range (2-4%)'}
            - Generated **{sharpe_ratio:.2f} Sharpe ratio** demonstrating risk-adjusted performance
            """
            
            st.success(achievement_text)
            
            # Dynamic Operational Advantages
            col1, col2 = st.columns(2)
            
            with col1:
                operational_text = f"""
                **📊 Operational Advantages:**
                - **Portfolio Efficiency**: {actual_positions:,} holdings vs {benchmark_holdings_estimate:,}+ in {benchmark}
                - **Cost Reduction**: ~{efficiency_reduction:.0%} fewer transaction costs
                - **Risk Management**: {tracking_error:.2%} tracking error achieved
                - **Return Enhancement**: {excess_return:.2%} annual excess return generated
                """
                st.markdown(operational_text)
            
            with col2:
                # Dynamic applications based on performance
                if info_ratio > 1.0:
                    app_text = """
                    **🚀 Recommended Applications:**
                    - Active portfolio management strategies
                    - Benchmark-plus return targets
                    - Institutional index enhancement
                    - Risk-budgeted alpha generation
                    """
                elif 0.5 <= info_ratio <= 1.0:
                    app_text = """
                    **🚀 Recommended Applications:**
                    - Cost-efficient index replication
                    - Core portfolio holdings
                    - Risk management overlays
                    - Transition management strategies
                    """
                else:
                    app_text = """
                    **🚀 Recommended Applications:**
                    - Parameter optimization required
                    - Feature engineering improvements
                    - Alternative benchmark selection
                    - Risk model refinements
                    """
                st.markdown(app_text)
            
            # KEY PERFORMANCE METRICS EXPLANATION
            st.markdown("---")
            st.markdown("### 📊 Key Performance Metrics Explained")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Information Ratio Analysis
                if info_ratio > 1.0:
                    ir_assessment = "🟢 **Excellent** - Exceptional active management skill"
                    ir_description = "Generates consistent excess returns relative to volatility"
                elif info_ratio > 0.5:
                    ir_assessment = "🟡 **Good** - Solid active management capability" 
                    ir_description = "Moderate excess returns with acceptable volatility"
                elif info_ratio > 0.0:
                    ir_assessment = "🟠 **Fair** - Limited active management value"
                    ir_description = "Small excess returns, optimization needed"
                else:
                    ir_assessment = "🔴 **Poor** - Underperforming benchmark"
                    ir_description = "Negative excess returns, major issues"
                
                st.markdown(f"""
                **📈 Information Ratio: {info_ratio:.2f}**
                
                {ir_assessment}
                
                *What it means:* {ir_description}
                
                **Industry Benchmarks:**
                - IR > 0.5: Good active management
                - IR > 1.0: Exceptional performance
                - IR < 0: Underperforming benchmark
                
                **Your Result:** {info_ratio:.2f} indicates {'strong' if info_ratio > 0.75 else 'moderate' if info_ratio > 0.25 else 'weak'} ability to generate risk-adjusted excess returns.
                """)
            
            with col2:
                # Sharpe Ratio Analysis  
                if sharpe_ratio > 2.0:
                    sr_assessment = "🟢 **Exceptional** - Outstanding risk-adjusted returns"
                    sr_description = "Top-tier performance with excellent risk management"
                elif sharpe_ratio > 1.0:
                    sr_assessment = "🟡 **Good** - Solid risk-adjusted performance"
                    sr_description = "Above-average returns per unit of risk taken"
                elif sharpe_ratio > 0.5:
                    sr_assessment = "🟠 **Acceptable** - Moderate risk-adjusted returns"
                    sr_description = "Decent performance but room for improvement"
                else:
                    sr_assessment = "🔴 **Poor** - Inadequate compensation for risk"
                    sr_description = "Low returns relative to volatility taken"
                
                st.markdown(f"""
                **⚡ Sharpe Ratio: {sharpe_ratio:.2f}**
                
                {sr_assessment}
                
                *What it means:* {sr_description}
                
                **Industry Benchmarks:**
                - SR > 1.0: Good risk-adjusted returns
                - SR > 2.0: Exceptional performance  
                - SR < 0.5: Poor risk compensation
                
                **Your Result:** {sharpe_ratio:.2f} shows {'excellent' if sharpe_ratio > 1.5 else 'good' if sharpe_ratio > 1.0 else 'moderate' if sharpe_ratio > 0.5 else 'poor'} return per unit of risk.
                """)

            # COMPREHENSIVE TECHNICAL ASSESSMENT
            st.markdown("---")
            st.markdown("### 🎯 Overall System Assessment")
            
            # Calculate overall score
            ir_score = min(info_ratio * 2, 2.0) if info_ratio > 0 else 0  # Scale 0-2
            sr_score = min(sharpe_ratio, 2.0) if sharpe_ratio > 0 else 0  # Scale 0-2
            te_score = 2.0 if 0.02 <= tracking_error <= 0.04 else (1.0 if tracking_error <= 0.06 else 0)  # Scale 0-2
            
            overall_score = (ir_score + sr_score + te_score) / 3  # Average score 0-2
            
            # Dynamic Technical Assessment with comprehensive analysis
            if overall_score >= 1.5:
                status_color = "success"
                status_icon = "🟢"
                status_grade = "A"
                status_text = "**PRODUCTION READY** - Institutional Quality System"
                detailed_assessment = f"""
                **System Grade: {status_grade}** ({overall_score:.1f}/2.0)
                
                ✅ **Strengths:**
                - Information Ratio ({info_ratio:.2f}) demonstrates consistent alpha generation
                - Sharpe Ratio ({sharpe_ratio:.2f}) shows excellent risk-adjusted returns  
                - Tracking Error ({tracking_error:.2%}) {'within' if 0.02 <= tracking_error <= 0.04 else 'near'} optimal range
                
                💼 **Business Impact:**
                - Ready for institutional deployment
                - Suitable for client portfolios
                - Strong value proposition vs benchmarks
                - Scalable across asset classes
                """
                
            elif overall_score >= 1.0:
                status_color = "info"
                status_icon = "🟡"
                status_grade = "B"
                status_text = "**GOOD PERFORMANCE** - Optimization Opportunities"
                detailed_assessment = f"""
                **System Grade: {status_grade}** ({overall_score:.1f}/2.0)
                
                ✅ **Strengths:**
                - {'Strong' if info_ratio > 0.5 else 'Moderate'} Information Ratio ({info_ratio:.2f})
                - {'Good' if sharpe_ratio > 1.0 else 'Acceptable'} Sharpe Ratio ({sharpe_ratio:.2f})
                
                🔧 **Optimization Areas:**
                - {'Tracking error management' if tracking_error > 0.04 else 'Parameter fine-tuning'}
                - {'Feature engineering improvements' if info_ratio < 0.75 else 'Risk model refinement'}
                
                💼 **Business Impact:**
                - Suitable for internal strategies
                - Requires monitoring and optimization
                - Good foundation for enhancements
                """
                
            else:
                status_color = "warning"
                status_icon = "🔴"
                status_grade = "C"
                status_text = "**NEEDS IMPROVEMENT** - Major Issues Identified"
                detailed_assessment = f"""
                **System Grade: {status_grade}** ({overall_score:.1f}/2.0)
                
                ⚠️ **Critical Issues:**
                - {'Low' if info_ratio < 0.5 else 'Negative'} Information Ratio ({info_ratio:.2f})
                - {'Poor' if sharpe_ratio < 1.0 else 'Inadequate'} Sharpe Ratio ({sharpe_ratio:.2f})
                - {'High' if tracking_error > 0.06 else 'Suboptimal'} Tracking Error ({tracking_error:.2%})
                
                🔧 **Required Actions:**
                - Complete parameter reoptimization
                - Feature engineering overhaul  
                - Model architecture review
                - Data quality assessment
                
                💼 **Business Impact:**
                - Not suitable for deployment
                - Requires significant development
                - High risk of underperformance
                """
            
            if status_color == "success":
                st.success(f"""
                {status_text}
                - Systematic ML-driven security selection
                - Robust portfolio optimization framework
                - Real-time performance monitoring
                - Institutional-quality risk management
                """)
            elif status_color == "info":
                st.info(f"""
                {status_text}
                - Machine learning model shows promise
                - Portfolio construction framework solid
                - Performance tracking operational
                - Ready for parameter optimization
                """)
            else:
                st.warning(f"""
                {status_text}
                - Model performance below target thresholds
                - Tracking error management needs improvement
                - Feature engineering optimization recommended
                - Parameter sensitivity analysis required
                """)
        
        else:
            # Fallback to static content if no data available
            st.info("""
            **📊 Executive Summary:**
            - Advanced ML-driven portfolio replication system
            - Systematic benchmark tracking with sparse portfolios
            - Professional-grade analysis and reporting capabilities
            - Configurable for multiple asset classes and benchmarks
            """)
    
    with tab5:
        st.markdown("### 📊 Raw Data Explorer")
        
        # Data table selector
        if data:
            table_name = st.selectbox(
                "Select Data Table",
                list(data.keys())
            )
            
            if table_name in data:
                st.dataframe(data[table_name], use_container_width=True)
                
                # Download button
                csv = data[table_name].to_csv(index=False)
                st.download_button(
                    label=f"Download {table_name}.csv",
                    data=csv,
                    file_name=f"{table_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

if __name__ == "__main__":
    main()