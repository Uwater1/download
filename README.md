# Financial Data Downloader

This project automatically downloads weekly financial data for various assets using Yahoo Finance and saves them as CSV files in a date-stamped folder.

## Features

- Downloads 7 days of 1-minute interval data for:
  - Gold (GC=F)
  - Silver (SI=F)
  - Oil (CL=F)
  - Bitcoin (BTC-USD)
  - Ethereum (ETH-USD)
  - Nasdaq 100 (QQQ)
  - S&P 500 (IVV)
  - USD/JPY (JPY=X)
  - USD/CAD (CAD=X)
  - EUR/USD (EURUSD=X)

- Runs automatically every Saturday at midnight UTC via GitHub Actions
- Can be triggered manually
- Includes rate limiting and error handling
- Commits downloaded data to the repository

## Usage

The workflow runs automatically. To trigger manually:
1. Go to the Actions tab in the repository
2. Select "Weekly Data Download"
3. Click "Run workflow"

## Output

- CSV files are saved in folders named `YYYY-MM-DD/`
- Work log is available in the GitHub Actions job summary

## Requirements

- Python 3.x
- Dependencies: yfinance, pandas

## License

See LICENSE file.
