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
    # 1. Handle Index: yahooquery usually returns MultiIndex (symbol, expiration, option_type, ...)
    df = df.reset_index()

    # 2. Normalize Columns (Fix for your error)
    # Sometimes it returns 'optionType', sometimes 'option_type'
    if 'optionType' in df.columns and 'option_type' not in df.columns:
        df = df.rename(columns={'optionType': 'option_type'})
    
    # Check if critical columns exist
    if 'option_type' not in df.columns:
        print(f"  [WARNING] 'option_type' column missing for {ticker_name}. Available columns: {list(df.columns)}")
        # Try to guess based on values? No, safer to skip to avoid bad data.
        return

    # 3. Format Implied Volatility (0.25 -> 25.0000)
    # Check for both snake_case and camelCase variations just in case
    iv_col = 'implied_volatility' if 'implied_volatility' in df.columns else 'impliedVolatility'
    if iv_col in df.columns:
        df['impliedVolatility'] = (df[iv_col] * 100).round(4)
    
    # 4. Format In The Money (True/False -> 1/0)
    itm_col = 'in_the_money' if 'in_the_money' in df.columns else 'inTheMoney'
    if itm_col in df.columns:
        df['inTheMoney'] = df[itm_col].astype(int)

    # 5. Rename columns to match typical conventions
    # We map from whatever yahooquery gave us to your desired camelCase
    rename_map = {
        'contract_symbol': 'contractSymbol', 'contractSymbol': 'contractSymbol',
        'last_price': 'lastPrice',           'lastPrice': 'lastPrice',
        'last_trade_date': 'lastTradeDate',  'lastTradeDate': 'lastTradeDate',
        'open_interest': 'openInterest',     'openInterest': 'openInterest',
        'expiration': 'expiration'
    }
    df = df.rename(columns=rename_map)

    # 6. Drop unwanted columns
    # We remove openInterest as requested (often 0)
    cols_to_drop = [
        'contract_size', 'currency', 'change', 'percent_change', 
        'bid', 'ask', 'openInterest', 
        'implied_volatility', 'in_the_money', 'optionType', # drop originals
        'impliedVolatility', 'inTheMoney' # Keep the ones we formatted? No, we need to KEEP the formatted ones.
    ]
    
    # Careful not to drop the formatted columns we just created ('impliedVolatility', 'inTheMoney')
    # So we only drop the raw source columns
    source_cols_to_drop = [
        'contract_size', 'currency', 'change', 'percent_change', 
        'bid', 'ask', 'openInterest', 
        'implied_volatility', 'in_the_money', 'optionType', 'change_percent'
    ]
    df = df.drop(columns=source_cols_to_drop, errors='ignore')

    # Group by Expiration and Option Type to save files
    if 'expiration' not in df.columns:
         print(f"  [ERROR] 'expiration' column missing for {ticker_name}. Skipping.")
         return

    expirations = df['expiration'].unique()
    saved_count = 0
    
    for date in expirations:
        try:
            # Format filename date part (YYYY-MM-DD -> YYYYMMDD)
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
        df = t.option_chain
        
        if df is None or df.empty:
            print(f"  No options data found for {name}.")
            continue
            
        if isinstance(df, pd.DataFrame):
            process_and_save(df, name)
        else:
            print(f"  Unexpected data format for {name}: {type(df)}")

    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")

print("Options download complete.")
