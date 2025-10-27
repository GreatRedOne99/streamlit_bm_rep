# Enhanced Stocks & Futures with DuckDB Integration

A comprehensive Python library for downloading and storing market data from Interactive Brokers (IBKR) with automatic DuckDB persistence and multi-frequency support.

## Features

- 📈 **Stock and Futures Data**: Download OHLCV data from IBKR
- 🗄️ **DuckDB Integration**: Automatic data persistence with optional storage
- ⏱️ **Multi-Frequency Support**: Handle 1min, 5min, 15min, 1hour, daily data
- 🔄 **Smart Updates**: INSERT OR REPLACE prevents duplicates
- 📊 **Separate Tables**: Stocks and futures stored in dedicated tables
- 🎯 **Timezone Handling**: Proper timezone conversion for futures data
- 🔍 **Query Utilities**: Built-in functions for data retrieval and analysis

## Installation

```bash
pip install ib_insync pandas duckdb pandas_market_calendars pytz
```

## Quick Start

### Basic Usage (No Database)

```python
from enhanced_stocks_futures import USStock, USFuture

# Connect to IBKR first (your existing connection code)
# client = your_ibkr_client

# Download stock data (returns DataFrame only)
stock = USStock("AAPL", client, "NASDAQ")
df = stock.USStock_historical_data("1 Y", "1 day", True)
```

### With DuckDB Storage

```python
# Enable DuckDB storage
stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)
df = stock.USStock_historical_data("1 Y", "1 day", True)
# ✅ Returns DataFrame AND saves to database

# Don't forget to close connection
stock.close_db()
```

## Classes

### USStock Class

Downloads and manages US stock data.

#### Constructor
```python
USStock(ticker, client, primaryExchange, use_duckdb=False, db_path="../data/market_data.duckdb")
```

**Parameters:**
- `ticker` (str): Stock symbol (e.g., "AAPL", "MSFT")
- `client`: IBKR client connection
- `primaryExchange` (str): Primary exchange (e.g., "NASDAQ", "NYSE")
- `use_duckdb` (bool): Enable database storage (default: False)
- `db_path` (str): Path to DuckDB file (default: "../data/market_data.duckdb")

#### Methods

**USStock_historical_data(time, period, useRTH)**
```python
df = stock.USStock_historical_data("1 Y", "1 day", True)
```
- `time`: Duration ("1 Y", "6 M", "30 D")
- `period`: Bar size ("1 day", "1 hour", "5 mins", "1 min")
- `useRTH`: Use regular trading hours (True/False)

**USStock_historical_data_WAY_BACK(time, period, endDate, useRTH)**
```python
df = stock.USStock_historical_data_WAY_BACK("1 Y", "1 day", "20231215", True)
```
Downloads historical data ending at specific date.

### USFuture Class

Downloads and manages US futures data with timezone handling.

#### Constructor
```python
USFuture(client, ticker, localticker, multiplier, currency, primaryExchange, lastTradeDate, use_duckdb=False, db_path="../data/market_data.duckdb")
```

**Parameters:**
- `client`: IBKR client connection
- `ticker` (str): Future symbol (e.g., "ES", "NQ")
- `localticker` (str): Local symbol (e.g., "ESH25")
- `multiplier` (int): Contract multiplier
- `currency` (str): Currency ("USD")
- `primaryExchange` (str): Exchange (e.g., "GLOBEX", "NYMEX")
- `lastTradeDate` (str): Expiration date (e.g., "202503")
- `use_duckdb` (bool): Enable database storage
- `db_path` (str): Path to DuckDB file

#### Methods

**USFuture_historical_data(time, period, useRTH)**
```python
future = USFuture(client, "ES", "ESH25", 50, "USD", "GLOBEX", "202503", use_duckdb=True)
df = future.USFuture_historical_data("5 D", "1 min", False)
```

**USContinousFuture_historical_data(time, period, useRTH)**
```python
df = future.USContinousFuture_historical_data("1 Y", "1 day", True)
```
Downloads data for continuous futures contracts.

## Database Schema

### Stock Data Table (stock_data)
```sql
CREATE TABLE stock_data (
    symbol VARCHAR,
    date_time TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    instrument_type VARCHAR,
    exchange VARCHAR,
    bar_size VARCHAR,
    duration VARCHAR,
    use_rth BOOLEAN,
    color VARCHAR,
    PRIMARY KEY (symbol, date_time, bar_size)
)
```

### Futures Data Table (futures_data)
```sql
CREATE TABLE futures_data (
    symbol VARCHAR,
    date_time TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    instrument_type VARCHAR,
    exchange VARCHAR,
    bar_size VARCHAR,
    duration VARCHAR,
    use_rth BOOLEAN,
    color VARCHAR,
    contract_month VARCHAR,
    PRIMARY KEY (symbol, date_time, bar_size)
)
```

## Multi-Frequency Support

The same symbol can have multiple frequencies stored simultaneously:

```python
# All of these create separate database entries
stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)
df_daily = stock.USStock_historical_data("1 Y", "1 day", True)      # Daily data
df_hourly = stock.USStock_historical_data("5 D", "1 hour", True)    # Hourly data  
df_minute = stock.USStock_historical_data("2 D", "1 min", False)    # Minute data
```

**Primary Key:** `(symbol, date_time, bar_size)` prevents conflicts between frequencies.

## Query Utilities

### query_market_data()

Query data with flexible filtering:

```python
from enhanced_stocks_futures import query_market_data

# Get all AAPL daily data
df = query_market_data(symbol="AAPL", bar_size="1 day", table_name="stock_data")

# Get ES 1-minute data for specific date range
df = query_market_data(
    symbol="ES", 
    bar_size="1 min", 
    start_date="2024-01-01", 
    end_date="2024-01-31",
    table_name="futures_data"
)

# Get all data from futures table
df = query_market_data(table_name="futures_data")
```

### get_available_frequencies()

See what data is available:

```python
from enhanced_stocks_futures import get_available_frequencies

# Check available frequencies for AAPL
freq_df = get_available_frequencies(symbol="AAPL", table_name="stock_data")
print(freq_df)
#   symbol bar_size  record_count  first_date           last_date
#   AAPL   1 day     252          2024-01-02          2024-12-31
#   AAPL   1 hour    1560         2024-12-27 09:30:00  2024-12-31 16:00:00
#   AAPL   1 min     2340         2024-12-30 09:30:00  2024-12-31 16:00:00

# Check all available data in futures table
all_freq = get_available_frequencies(table_name="futures_data")
```

## Complete Example

```python
from enhanced_stocks_futures import USStock, USFuture, query_market_data, get_available_frequencies

# Your IBKR connection code here
# client = connect_to_ibkr()

# Download stock data with database storage
stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)

# Download multiple frequencies
daily_df = stock.USStock_historical_data("1 Y", "1 day", True)
hourly_df = stock.USStock_historical_data("5 D", "1 hour", True)
minute_df = stock.USStock_historical_data("1 D", "1 min", False)

print(f"Downloaded {len(daily_df)} daily bars")
print(f"Downloaded {len(hourly_df)} hourly bars") 
print(f"Downloaded {len(minute_df)} minute bars")

# Download futures data
future = USFuture(client, "ES", "ESH25", 50, "USD", "GLOBEX", "202503", use_duckdb=True)
futures_df = future.USFuture_historical_data("5 D", "15 mins", False)

print(f"Downloaded {len(futures_df)} ES 15-min bars")

# Query the database
print("\nAvailable stock frequencies:")
stock_freq = get_available_frequencies(table_name="stock_data")
print(stock_freq)

print("\nAvailable futures frequencies:")
futures_freq = get_available_frequencies(table_name="futures_data")
print(futures_freq)

# Get specific data
aapl_daily = query_market_data(symbol="AAPL", bar_size="1 day", table_name="stock_data")
es_15min = query_market_data(symbol="ES", bar_size="15 mins", table_name="futures_data")

# Clean up connections
stock.close_db()
future.close_db()
```

## Data Update Strategy

### Initial Backfill
```python
# Download 1 year of daily data
stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)
df = stock.USStock_historical_data("1 Y", "1 day", True)  # 252 records
```

### Daily Maintenance
```python
# Download last 3 days (handles weekends/holidays)
df = stock.USStock_historical_data("3 D", "1 day", True)
# ✅ Replaces any existing dates, adds new dates
```

### Incremental Updates
```python
# Add minute data for recent days
df = stock.USStock_historical_data("2 D", "1 min", False)
# ✅ Creates separate frequency entries, no conflicts with daily data
```

## Important Notes

### Timezone Handling
- **Stocks**: Stored in market timezone
- **Futures**: Automatically converted to America/Chicago timezone
- **Database**: All timestamps stored as UTC

### Memory Management
```python
# Always close database connections
stock.close_db()
future.close_db()

# Or use context managers (if implemented)
with USStock("AAPL", client, "NASDAQ", use_duckdb=True) as stock:
    df = stock.USStock_historical_data("1 Y", "1 day", True)
# Automatically closes connection
```

### Error Handling
```python
try:
    stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)
    df = stock.USStock_historical_data("1 Y", "1 day", True)
except Exception as e:
    print(f"Error downloading data: {e}")
finally:
    if 'stock' in locals():
        stock.close_db()
```

## File Structure

```
project/
├── enhanced_stocks_futures.py     # Main library file
├── data/
│   └── market_data.duckdb         # Database file (auto-created)
└── your_trading_scripts.py        # Your code using the library
```

## Performance Tips

1. **Batch Downloads**: Download multiple frequencies in one session
2. **Index Usage**: Queries on `symbol` and `bar_size` are optimized
3. **Database Size**: DuckDB compresses data efficiently (~100MB per million rows)
4. **Query Optimization**: Use specific filters rather than loading all data

## Troubleshooting

### Common Issues

**"Table does not exist"**
```python
# Make sure to create an instance with use_duckdb=True first
stock = USStock("AAPL", client, "NASDAQ", use_duckdb=True)
# This creates the table if it doesn't exist
```

**"No data returned"**
```python
# Check what's actually in the database
frequencies = get_available_frequencies(table_name="stock_data")
print(frequencies)

# Debug your query
df = query_market_data(table_name="stock_data")  # Get all data
```

**"Connection errors"**
```python
# Always close connections
stock.close_db()

# Check database file exists
import os
print(os.path.exists("../data/market_data.duckdb"))
```

This library provides a robust foundation for IBKR data management with automatic persistence and multi-frequency support.
