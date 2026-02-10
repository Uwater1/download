import yfinance as yf
import os
from datetime import datetime, timedelta
import pandas as pd
import time
import numpy as np

# Define tickers (using ETFs for better options coverage)
TICKERS = {
    "nq100": "QQQ",
    "sp500": "IVV",
    "aapl": "AAPL",
    "msft": "MSFT",
    "nvda": "NVDA",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "goog": "GOOG",
    "btc": "IBIT",   # iShares Bitcoin Trust ETF
    "eth": "ETHA",   # iShares Ethereum Trust ETF
    "gold": "GLD",   # SPDR Gold Shares ETF
    "silver": "SLV", # iShares Silver Trust ETF
    "oil": "USO",    # United States Oil Fund ETF
}

current_date = datetime.now().strftime("%Y-%m-%d")
base_folder = "options_data"
date_folder = os.path.join(base_folder, current_date)

if not os.path.exists(date_folder):
    os.makedirs(date_folder)

# Cache for intraday price data: {(ticker, date_str): DataFrame}
_intraday_cache = {}

def get_risk_free_rate():
    """
    Get the current risk-free rate from 13-week Treasury Bill (^IRX)
    Returns annual rate as a decimal (e.g., 0.04 for 4%)
    """
    try:
        irx = yf.Ticker("^IRX")
        hist = irx.history(period="5d")
        if not hist.empty:
            # ^IRX is quoted as annual percentage, convert to decimal
            rate = hist['Close'].iloc[-1] / 100.0
            return rate
        else:
            print("Warning: Could not fetch risk-free rate, using default 0.04")
            return 0.04
    except Exception as e:
        print(f"Error fetching risk-free rate: {e}, using default 0.04")
        return 0.04

def _get_intraday_data(ticker_symbol, date_str):
    """
    Get (and cache) intraday 1-minute data for a ticker on a given date.
    Returns the cached DataFrame, downloading only once per (ticker, date).
    """
    cache_key = (ticker_symbol, date_str)
    if cache_key in _intraday_cache:
        return _intraday_cache[cache_key]

    ticker = yf.Ticker(ticker_symbol)
    end_date = (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    hist = ticker.history(start=date_str, end=end_date, interval="1m")
    if hist.empty:
        # Fallback to hourly
        hist = ticker.history(start=date_str, end=end_date, interval="1h")

    if not hist.empty:
        hist.index = pd.to_datetime(hist.index, utc=True)

    _intraday_cache[cache_key] = hist
    return hist

def get_stock_price_at_time(ticker_symbol, target_datetime, current_price):
    """
    Get the stock price at a specific datetime using cached intraday data.
    If no trade within 5 days, return NaN.
    """
    try:
        if target_datetime.tzinfo is None:
            target_datetime = target_datetime.replace(tzinfo=pd.Timestamp.now(tz='UTC').tzinfo)

        now = pd.Timestamp.now(tz='UTC')
        if (now - target_datetime).days > 5:
            return np.float32(np.nan)

        date_str = target_datetime.strftime('%Y-%m-%d')
        hist = _get_intraday_data(ticker_symbol, date_str)

        if hist.empty:
            return np.float32(current_price)

        closest_idx = hist.index.get_indexer([target_datetime], method='nearest')[0]
        if closest_idx >= 0:
            return np.float32(hist['Close'].iloc[closest_idx])
        else:
            return np.float32(current_price)

    except Exception as e:
        print(f"    Error getting price at time {target_datetime}: {e}")
        return np.float32(current_price)

def process_options_df(df, ticker_symbol, current_price, risk_free_rate):
    """
    Compresses and formats the options DataFrame according to specific rules.
    Adds underlying price at lastTradeDate time. Prices stored as float32.
    """
    if df is None or df.empty:
        return df

    # 1. Delete specific columns
    cols_to_drop = [
        'contractSize', 'currency', 'expirationDate', 
        'change', 'percentChange', 'bid', 'ask', 'openInterest'
    ]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # 2. Convert impliedVolatility to percentage with 4 decimal places
    if 'impliedVolatility' in df.columns:
        df['impliedVolatility'] = (df['impliedVolatility'] * 100).round(4).astype(np.float32)

    # 3. Convert inTheMoney to 0 (False) and 1 (True)
    if 'inTheMoney' in df.columns:
        df['inTheMoney'] = df['inTheMoney'].astype(np.int8)

    # 4. Convert price columns to float32
    price_cols = ['lastPrice', 'strike', 'volume']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].astype(np.float32)

    # 5. Add underlying price at lastTradeDate (using cached intraday data)
    if 'lastTradeDate' in df.columns:
        # Pre-fetch all unique trade dates for this ticker (one API call per date)
        unique_dates = df['lastTradeDate'].dropna().apply(
            lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)[:10]
        ).unique()

        now = pd.Timestamp.now(tz='UTC')
        for d in unique_dates:
            try:
                dt = pd.Timestamp(d, tz='UTC')
                if (now - dt).days <= 5:
                    _get_intraday_data(ticker_symbol, d)
            except Exception:
                pass

        print(f"    Looking up underlying prices at trade times ({len(unique_dates)} unique dates)...")
        df['underlyingPriceAtTrade'] = df['lastTradeDate'].apply(
            lambda x: get_stock_price_at_time(ticker_symbol, x, current_price) if pd.notna(x) else np.float32(np.nan)
        ).astype(np.float32)

    # 6. Add risk-free rate column
    df['riskFreeRate'] = np.float32(risk_free_rate)

    return df

# Get risk-free rate once at the start
risk_free_rate = get_risk_free_rate()
print(f"Risk-free rate (^IRX): {risk_free_rate:.4f} ({risk_free_rate*100:.2f}%)")
print(f"Starting options download for {current_date}...")

for name, ticker_symbol in TICKERS.items():
    print(f"\nProcessing {name} ({ticker_symbol})...")
    # Clear intraday cache between tickers to save memory
    _intraday_cache.clear()

    try:
        tk = yf.Ticker(ticker_symbol)

        # Get current/closing price
        try:
            hist = tk.history(period="1d")
            if not hist.empty:
                current_price = np.float32(hist['Close'].iloc[-1])
            else:
                current_price = np.float32(tk.info.get('regularMarketPrice', 0))

            print(f"  Current price: ${current_price:.2f}")
        except Exception as e:
            print(f"  Error getting current price: {e}")
            current_price = np.float32(0)

        # Get expiration dates
        try:
            expirations = tk.options
        except Exception:
            print(f"  No options found for {name} (or API error). Skipping.")
            continue

        if not expirations:
            print(f"  No options found for {name}. Skipping.")
            continue

        print(f"  Found {len(expirations)} expiration dates.")

        # Loop through expirations
        for date in expirations:
            try:
                # Download option chain
                chain = tk.option_chain(date)

                # Format filename: options_data/2026-02-10/aapl_20260217_calls_150_50.csv
                safe_date = date.replace("-", "")
                price_str = f"{current_price:.2f}".replace(".", "_")
                calls_file = os.path.join(date_folder, f"{name}_{safe_date}_calls_{price_str}.csv")
                puts_file = os.path.join(date_folder, f"{name}_{safe_date}_puts_{price_str}.csv")

                # Process and Save Calls
                if chain.calls is not None and not chain.calls.empty:
                    cleaned_calls = process_options_df(chain.calls.copy(), ticker_symbol, current_price, risk_free_rate)
                    cleaned_calls.to_csv(calls_file, index=False)
                    print(f"  Saved {len(cleaned_calls)} calls to {os.path.basename(calls_file)}")

                # Process and Save Puts
                if chain.puts is not None and not chain.puts.empty:
                    cleaned_puts = process_options_df(chain.puts.copy(), ticker_symbol, current_price, risk_free_rate)
                    cleaned_puts.to_csv(puts_file, index=False)
                    print(f"  Saved {len(cleaned_puts)} puts to {os.path.basename(puts_file)}")

                # Sleep to prevent rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"  Error fetching {date} for {name}: {e}")

    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")

print("\n" + "="*50)
print("Options download complete.")
print(f"Data saved to: {date_folder}")
