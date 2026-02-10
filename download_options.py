import yfinance as yf
import os
from datetime import datetime, timedelta
import pandas as pd
import time
import numpy as np

# Define tickers
TICKERS = {
    "nq100": "QQQ",
    "sp500": "IVV",
    "aapl": "AAPL",
    "msft": "MSFT",
    "nvda": "NVDA",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "goog": "GOOG",
    # Forex/Crypto often don't have standard Yahoo options, 
    # but we keep them in case coverage changes.
    "BTC": "BTC-USD", 
    "ETH": "ETH-USD",
    "gold": "GC=F", 
    "silver": "SI=F",
    "oil": "CL=F",
}

current_date = datetime.now().strftime("%Y-%m-%d")
base_folder = "options_data"
date_folder = os.path.join(base_folder, current_date)

if not os.path.exists(date_folder):
    os.makedirs(date_folder)

def get_risk_free_rate():
    """
    Get the current risk-free rate from 13-week Treasury Bill (^IRX)
    Returns annual rate as a decimal (e.g., 0.05 for 5%)
    """
    try:
        irx = yf.Ticker("^IRX")
        hist = irx.history(period="5d")
        if not hist.empty:
            # ^IRX is quoted as annual percentage, convert to decimal
            rate = hist['Close'].iloc[-1] / 100.0
            return rate
        else:
            print("Warning: Could not fetch risk-free rate, using default 0.05")
            return 0.05
    except Exception as e:
        print(f"Error fetching risk-free rate: {e}, using default 0.05")
        return 0.05

def get_stock_price_at_time(ticker_symbol, target_datetime, current_price):
    """
    Get the stock price at a specific datetime (accurate to 1 minute).
    If no trade within 5 days, return NaN.
    
    Args:
        ticker_symbol: The ticker symbol
        target_datetime: The datetime to find the price for
        current_price: Current/latest price as fallback
    
    Returns:
        Price at the target time or NaN if too old
    """
    try:
        # Make target_datetime timezone-aware if it isn't already
        if target_datetime.tzinfo is None:
            # Assume UTC if no timezone
            target_datetime = target_datetime.replace(tzinfo=pd.Timestamp.now(tz='UTC').tzinfo)
        
        # Check if trade is within last 5 days
        now = pd.Timestamp.now(tz='UTC')
        if (now - target_datetime).days > 5:
            return np.nan
        
        # Download 1-minute data for the day
        ticker = yf.Ticker(ticker_symbol)
        
        # Get data for the specific day - yfinance needs date strings, not datetime
        start_date = target_datetime.strftime('%Y-%m-%d')
        end_date = (target_datetime + timedelta(days=1)).strftime('%Y-%m-%d')
        
        hist = ticker.history(start=start_date, end=end_date, interval="1m")
        
        if hist.empty:
            # Try hourly data as fallback
            hist = ticker.history(start=start_date, end=end_date, interval="1h")
        
        if hist.empty:
            # If still no data, return current price (same-day trade likely)
            return current_price
        
        # Find the closest timestamp to our target
        hist.index = pd.to_datetime(hist.index, utc=True)
        closest_idx = hist.index.get_indexer([target_datetime], method='nearest')[0]
        
        if closest_idx >= 0:
            return hist['Close'].iloc[closest_idx]
        else:
            return current_price
            
    except Exception as e:
        print(f"    Error getting price at time {target_datetime}: {e}")
        return current_price

def process_options_df(df, ticker_symbol, current_price, risk_free_rate):
    """
    Compresses and formats the options DataFrame according to specific rules.
    Adds underlying price at lastTradeDate time.
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
        df['impliedVolatility'] = (df['impliedVolatility'] * 100).round(4)

    # 3. Convert inTheMoney to 0 (False) and 1 (True)
    if 'inTheMoney' in df.columns:
        df['inTheMoney'] = df['inTheMoney'].astype(int)

    # 4. Add underlying price at lastTradeDate
    if 'lastTradeDate' in df.columns:
        print(f"    Fetching underlying prices at trade times...")
        df['underlyingPriceAtTrade'] = df['lastTradeDate'].apply(
            lambda x: get_stock_price_at_time(ticker_symbol, x, current_price) if pd.notna(x) else np.nan
        )
    
    # 5. Add risk-free rate column
    df['riskFreeRate'] = risk_free_rate

    return df

# Get risk-free rate once at the start
risk_free_rate = get_risk_free_rate()
print(f"Risk-free rate (^IRX): {risk_free_rate:.4f} ({risk_free_rate*100:.2f}%)")
print(f"Starting options download for {current_date}...")

for name, ticker_symbol in TICKERS.items():
    print(f"\nProcessing {name} ({ticker_symbol})...")
    
    try:
        tk = yf.Ticker(ticker_symbol)
        
        # Get current/closing price
        try:
            hist = tk.history(period="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                current_price = tk.info.get('regularMarketPrice', 0)
            
            print(f"  Current price: ${current_price:.2f}")
        except Exception as e:
            print(f"  Error getting current price: {e}")
            current_price = 0
        
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
