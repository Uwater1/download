import yfinance as yf
import os
from datetime import datetime
import pandas as pd
import time

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

def process_options_df(df):
    """
    Compresses and formats the options DataFrame according to specific rules.
    """
    if df is None or df.empty:
        return df

    # 1. Delete specific columns
    # We remove 'expirationDate' by simply not adding it, but we list it here to be safe
    # We remove bid/ask/change/openInterest as requested because they are often 0 on YF delayed data
    cols_to_drop = [
        'contractSize', 'currency', 'expirationDate', 
        'change', 'percentChange', 'bid', 'ask', 'openInterest'
    ]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # 2. Convert impliedVolatility to percentage with 4 decimal places
    # e.g., 0.25301 -> 25.3010
    if 'impliedVolatility' in df.columns:
        df['impliedVolatility'] = (df['impliedVolatility'] * 100).round(4)

    # 3. Convert inTheMoney to 0 (False) and 1 (True)
    if 'inTheMoney' in df.columns:
        df['inTheMoney'] = df['inTheMoney'].astype(int)

    return df

print(f"Starting options download for {current_date}...")

for name, ticker_symbol in TICKERS.items():
    print(f"Processing {name} ({ticker_symbol})...")
    
    try:
        tk = yf.Ticker(ticker_symbol)
        
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
                
                # Format filename: options_data/2026-02-10/AAPL_2026-02-17_calls.csv
                safe_date = date.replace("-", "")
                calls_file = os.path.join(date_folder, f"{name}_{safe_date}_calls.csv")
                puts_file = os.path.join(date_folder, f"{name}_{safe_date}_puts.csv")
                
                # Process and Save Calls
                if chain.calls is not None and not chain.calls.empty:
                    # Note: We are NOT adding 'expirationDate' column as requested
                    cleaned_calls = process_options_df(chain.calls.copy())
                    cleaned_calls.to_csv(calls_file, index=False)
                
                # Process and Save Puts
                if chain.puts is not None and not chain.puts.empty:
                    cleaned_calls = process_options_df(chain.puts.copy())
                    cleaned_calls.to_csv(puts_file, index=False)
                
                # Sleep to prevent rate limiting
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"  Error fetching {date} for {name}: {e}")
                
    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")

print("Options download complete.")
