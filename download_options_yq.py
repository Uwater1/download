import os
from datetime import datetime
import pandas as pd
import time
from yahooquery import Ticker

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
    "BTC": "BTC-USD", 
    "ETH": "ETH-USD",
    "gold": "GC=F", 
    "silver": "SI=F",
    "oil": "CL=F",
}

current_date = datetime.now().strftime("%Y-%m-%d")
base_folder = "options_data_yq"
date_folder = os.path.join(base_folder, current_date)

if not os.path.exists(date_folder):
    os.makedirs(date_folder)

print(f"Starting options download (via yahooquery) for {current_date}...")

def process_and_save(df, ticker_name):
    """
    Splits the yahooquery bulk DataFrame into individual CSVs per expiration
    and applies formatting rules.
    """
    # yahooquery returns a MultiIndex: (symbol, expiration, option_type)
    # We reset index to make them columns we can filter by
    df = df.reset_index()

    # Map yahooquery snake_case columns to the camelCase format you might expect/want
    # or just keep them clean. Here we standardise to match your previous requirements.
    # Note: yahooquery usually returns: contract_symbol, strike, last_price, open_interest, etc.
    
    # 1. Format Implied Volatility (0.25 -> 25.0000)
    if 'implied_volatility' in df.columns:
        df['impliedVolatility'] = (df['implied_volatility'] * 100).round(4)
    
    # 2. Format In The Money (True/False -> 1/0)
    if 'in_the_money' in df.columns:
        df['inTheMoney'] = df['in_the_money'].astype(int)

    # 3. Rename columns to match typical conventions (optional, but good for consistency)
    rename_map = {
        'contract_symbol': 'contractSymbol',
        'last_price': 'lastPrice',
        'last_trade_date': 'lastTradeDate',
        'open_interest': 'openInterest'
    }
    df = df.rename(columns=rename_map)

    # 4. Drop unwanted columns
    # We remove the ones you requested to delete or that are often empty
    cols_to_drop = [
        'contract_size', 'currency', 'change', 'percent_change', 
        'bid', 'ask', 'openInterest', # User asked to remove openInterest if 0
        'implied_volatility', 'in_the_money' # Dropping original columns since we made new formatted ones
    ]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # Group by Expiration and Option Type to save files
    # Structure: df contains ALL data for this ticker. We need to split it up.
    
    # Get unique expirations
    expirations = df['expiration'].unique()
    
    saved_count = 0
    
    for date in expirations:
        try:
            # Format filename date part (YYYY-MM-DD -> YYYYMMDD)
            # yahooquery dates are usually datetime objects or strings.
            # Convert to string just in case
            date_str = str(date)
            safe_date = date_str.replace("-", "")
            
            # Filter for this date
            day_data = df[df['expiration'] == date]
            
            # Split Calls and Puts
            calls = day_data[day_data['option_type'] == 'calls'].copy()
            puts = day_data[day_data['option_type'] == 'puts'].copy()
            
            # Save Calls
            if not calls.empty:
                # Clean up columns for CSV (remove grouping cols)
                calls_out = calls.drop(columns=['symbol', 'expiration', 'option_type'], errors='ignore')
                filename = f"{ticker_name}_{safe_date}_calls.csv"
                calls_out.to_csv(os.path.join(date_folder, filename), index=False)
                saved_count += 1

            # Save Puts
            if not puts.empty:
                puts_out = puts.drop(columns=['symbol', 'expiration', 'option_type'], errors='ignore')
                filename = f"{ticker_name}_{safe_date}_puts.csv"
                puts_out.to_csv(os.path.join(date_folder, filename), index=False)
                saved_count += 1
                
        except Exception as e:
            print(f"Error saving expiration {date} for {ticker_name}: {e}")

    print(f"  Saved {saved_count} files for {ticker_name}")

# --- Main Loop ---

for name, ticker_symbol in TICKERS.items():
    print(f"Processing {name} ({ticker_symbol})...")
    
    try:
        t = Ticker(ticker_symbol)
        
        # This single line fetches ALL expirations at once!
        # It's much faster than yfinance looping.
        df = t.option_chain
        
        if df is None or df.empty:
            print(f"  No options data found for {name}.")
            continue
            
        # Check if the output is valid (sometimes returns weird dicts if failed)
        if isinstance(df, pd.DataFrame):
            process_and_save(df, name)
        else:
            print(f"  Unexpected data format for {name}: {type(df)}")

    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")
        # yahooquery sometimes throws specific errors for no data, catch them here

print("Options download complete.")
