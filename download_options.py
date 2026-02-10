import yfinance as yf
import os
from datetime import datetime
import pandas as pd
import time

# Define tickers (same as your other script, but you might want to remove Forex/Crypto if they don't have options)
TICKERS = {
    "nq100": "QQQ",
    "sp500": "IVV",
    "aapl": "AAPL",
    "msft": "MSFT",
    "nvda": "NVDA",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "goog": "GOOG",
    # Note: Forex and Crypto often do not have standard option chains on Yahoo Finance.
    # The script will try but skip them if unavailable.
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

print(f"Starting options download for {current_date}...")

for name, ticker_symbol in TICKERS.items():
    print(f"Processing {name} ({ticker_symbol})...")
    
    try:
        tk = yf.Ticker(ticker_symbol)
        
        # Get all expiration dates
        expirations = tk.options
        
        if not expirations:
            print(f"  No options found for {name}. Skipping.")
            continue
            
        print(f"  Found {len(expirations)} expiration dates.")

        # Loop through each expiration date
        for date in expirations:
            try:
                # Download option chain
                chain = tk.option_chain(date)
                
                # Prepare filenames
                # Structure: options_data/2023-10-27/AAPL_2023-11-03_calls.csv
                safe_date = date.replace("-", "")
                calls_file = os.path.join(date_folder, f"{name}_{safe_date}_calls.csv")
                puts_file = os.path.join(date_folder, f"{name}_{safe_date}_puts.csv")
                
                # Save Calls
                if not chain.calls.empty:
                    chain.calls['expirationDate'] = date
                    chain.calls.to_csv(calls_file, index=False)
                
                # Save Puts
                if not chain.puts.empty:
                    chain.puts['expirationDate'] = date
                    chain.puts.to_csv(puts_file, index=False)
                
                # Be nice to the API
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"  Error fetching {date} for {name}: {e}")
                
    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")

print("Options download complete.")
