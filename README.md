# Financial Data Downloader

This project automatically downloads weekly financial data for various assets using Yahoo Finance and saves them as CSV files in a date-stamped folder.
It also automatically downloads daily option data on 23:00 UTC Monday to Friday.

## Features

- Downloads 8 days of 1-minute interval data for:
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

- Runs automatically every Sunday at midnight UTC via GitHub Actions
- Can be triggered manually
- Includes rate limiting and error handling
- Commits downloaded data to the repository

## Usage

The workflow runs automatically. To trigger manually:
1. Go to the Actions tab in the repository
2. Select "Weekly Data Download"
3. Click "Run workflow"

## Output

- Price CSV files are saved in folders named `YYYY-MM-DD/`
- Work log is available in the GitHub Actions job summary
- Option CSV file: 1 represent In the Money, 0 represent Out of the Money

## Requirements

- Python 3.x
- Dependencies: yfinance, pandas

## Github Action
each Github action might has a delay **UP TO 48 HOURS** so I got 2 github action running
**THERE'S NO GUANTEE IT WILL WORK**

## License

See LICENSE file.
