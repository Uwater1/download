import yfinance as yf
import os
from datetime import datetime
import pandas as pd
import time

TICKERS = {
    "gold": "GC=F",
    "silver": "SI=F",
    "oil": "CL=F",
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "nq100": "QQQ",
    "sp500": "IVV",
    "aapl": "AAPL",
    "msft": "MSFT",
    "nvda": "NVDA",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "goog": "GOOG",
    "usdjpy": "JPY=X",
    "usdcad": "CAD=X",
    "eurusd": "EURUSD=X",
    "gbpusd": "GBPUSD=X",
    "audusd": "AUDUSD=X",
    "usdchf": "CHF=X"
}

current_date = datetime.now().strftime("%Y-%m-%d")
folder_path = current_date

if not os.path.exists(folder_path):
    os.makedirs(folder_path)

for name, ticker in TICKERS.items():
    try:
        print(f"Downloading data for {name} ({ticker})...")
        data = yf.download(ticker, period="7d", interval="1m")
        file_path = os.path.join(folder_path, f"{name}.csv")
        data.to_csv(file_path)
        print(f"Saved {name}.csv to {folder_path}")
    except Exception as e:
        print(f"Error downloading data for {name} ({ticker}): {e}")
    # Rate limiting to avoid API issues
    time.sleep(1)

print("All data downloaded and saved.")
