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
    "meta": "META",
    "avgo": "AVGO",
    "pltr": "PLTR",
    "usdjpy": "JPY=X",
    "usdcad": "CAD=X",
    "eurusd": "EURUSD=X",
    "gbpusd": "GBPUSD=X",
    "audusd": "AUDUSD=X",
    "usdchf": "CHF=X",
}

current_date = datetime.now().strftime("%Y-%m-%d")
folder_path = current_date

if not os.path.exists(folder_path):
    os.makedirs(folder_path)

skipped = []
downloaded = []

for name, ticker in TICKERS.items():
    try:
        print(f"Downloading data for {name} ({ticker})...")
        data = yf.download(ticker, period="8d", interval="1m")

        # Skip writing if no data returned
        if data is None or (hasattr(data, "empty") and data.empty) or (isinstance(data, pd.DataFrame) and data.shape[0] == 0):
            print(f"No data returned for {name} ({ticker}). Skipping CSV write.")
            skipped.append(name)
            continue

        file_path = os.path.join(folder_path, f"{name}.csv")
        data = data.round(5) 
        data.index = data.index.strftime("%Y-%m-%d %H:%M") 
        data.to_csv(file_path)
        print(f"Saved {name}.csv to {folder_path}")
        downloaded.append(name)
    except Exception as e:
        print(f"Error downloading data for {name} ({ticker}): {e}")
    time.sleep(1)

print("All data download attempts complete.")
print(f"Downloaded files: {len(downloaded)}")
if downloaded:
    print("Downloaded tickers:", ", ".join(downloaded))
print(f"Skipped tickers with no data: {len(skipped)}")
if skipped:
    print("Skipped tickers:", ", ".join(skipped))
