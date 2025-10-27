# Benchmark Replicator - Setup Instructions

## Prerequisites

1. **Python Environment**: Python 3.8 or higher
2. **System Requirements**: 8GB+ RAM recommended for full backtests
3. **Jupyter Notebook**: For running the analysis notebooks
4. **DuckDB**: Database system for data storage (installed via requirements.txt)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/GreatRedOne99/Benchmark_Replicator.git
   cd Benchmark_Replicator
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate.bat
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Jupyter kernel**:
   ```bash
   python -m ipykernel install --user --name=benchmark_replicator --display-name="benchmark-replicator"
   ```

## Running the System

### Stage 1: Portfolio Construction & Backtesting

1. **Start Jupyter Notebook**:
   ```bash
   jupyter notebook
   ```

2. **Open Main Notebook**:
   - Open `benchmark_replication.ipynb`
   - Select the "benchmark-replicator" kernel
   - Run cells sequentially (do not use "Run All")

3. **Configure Analysis Period**:
   - Review the Month End Dates array in Cell 8
   - Set START_INDEX and END_INDEX in Cell 9 to control scope
   - Start with 5-6 months for faster execution

### Stage 2: Professional Analysis & Reporting

1. **Open Analysis Notebook**:
   - Open `benchmark_analytics_notebook.ipynb`
   - Ensure `benchmark_analysis_toolkit.py` is in project directory

2. **Run Analysis**:
   - Import the analysis toolkit
   - Load data automatically
   - Generate professional reports and visualizations

## Data Requirements

### Primary Data Source
- The system uses historical ETF price data stored in DuckDB format
- Database location: `data/replication.duckdb`
- Contains stock data with ticker, date, and adjusted close columns

### Supported Benchmarks
- **MTUM**: iShares MSCI USA Momentum Factor ETF
- **SPY**: SPDR S&P 500 ETF Trust
- **IWM**: iShares Russell 2000 ETF
- **QQQ**: Invesco QQQ Trust (Nasdaq-100)

## Expected Results

### Stage 1 Output: Backtest Results
After `benchmark_replication.ipynb` completes, you'll get:
```
backtest_results_YYYYMMDD_HHMMSS/
├── Timestamped results with comprehensive backtest data
└── Performance metrics and portfolio weights
```

### Stage 2 Output: Professional Analysis
After `benchmark_analytics_notebook.ipynb` completes, you'll get:
- **Executive Reports**: Professional markdown and Excel analysis
- **Visualizations**: Performance charts and portfolio analytics
- **Business Intelligence**: Interview-ready conclusions and insights

## System Features

### Two-Stage Architecture
- **Stage 1**: Portfolio construction and backtesting with ML and optimization
- **Stage 2**: Professional analysis and reporting with automated insights
- **Modular Design**: Clean separation of concerns between components

### Key Capabilities
- **Multi-Benchmark Support**: Replicate MTUM, SPY, IWM, QQQ, or other benchmarks
- **Machine Learning**: XGBoost for security selection based on momentum patterns
- **Portfolio Optimization**: CVXPY with L1 regularization for sparse portfolios
- **Performance Tracking**: Comprehensive backtesting with institutional metrics

### Data Infrastructure
- **DuckDB Integration**: Efficient columnar storage for time-series data
- **Automated Pipeline**: Clean data flow from raw data to final reports
- **Professional Output**: Executive reports and presentation-ready analysis

## Troubleshooting

### Common Issues

**Memory Errors**
- Reduce analysis period using START_INDEX/END_INDEX
- Enable bulk mode processing in notebook
- Close other applications to free RAM

**Module Import Errors**
- Ensure all files are in correct directories
- Verify virtual environment is activated
- Reinstall requirements if necessary

**Database Issues**
- Check that `data/replication.duckdb` exists
- Verify data coverage for analysis period
- Ensure DuckDB package is properly installed

### Performance Tips
- Start with shorter analysis periods (5-6 months)
- Use bulk mode for production runs
- Monitor memory usage during backtests

## Project Structure
```
Benchmark_Replicator/
├── notebooks/
│   ├── benchmark_replication.ipynb        # Main analysis notebook (Stage 1)
│   └── benchmark_analytics_notebook.ipynb # Professional reporting (Stage 2)
├── data/
│   └── replication.duckdb                  # Main database with historical data
├── reporting/
│   └── benchmark_analysis_toolkit.py      # Professional analysis functions
├── portfolio/                              # Core optimization modules
│   ├── xgb_portfolio_model.py            # ML security selection
│   ├── portfolio_optimization.py          # CVXPY optimization
│   └── expected_returns_models.py         # Expected returns calculation
├── data_processing/                        # Data utilities
│   ├── db_utils.py                        # Database access functions
│   ├── backtest_storage.py               # Backtest results storage
│   └── portfolio_precleaning.py          # Data preprocessing
├── pipeline/                               # Pipeline components
│   ├── clean_monthly_backtest_pipeline.py # Main pipeline class
│   └── data_loader.py                     # Data loading utilities
└── documentation/                          # Complete system documentation
```

## Support and Resources

For assistance:
- **System Documentation**: Check `documentation/` directory for detailed guides
- **User Guide**: `documentation/user_guide.md` for step-by-step instructions
- **Technical Reference**: `documentation/technical_reference.md` for developers
- **API Documentation**: `documentation/api_documentation.md` for function reference