"""Price downloads keep aware UTC timestamps and merge into interval-specific history."""
import argparse
import time
import pandas as pd
import yfinance as yf
from storage import ROOT, TICKERS, normalize_prices, read_prices, merge_prices, write_parquet

def main(interval='1m'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickers', nargs='+', choices=list(TICKERS), default=list(TICKERS))
    parser.add_argument('--output-root', type=__import__('pathlib').Path, default=ROOT)
    args = parser.parse_args()
    folder = args.output_root / 'downloads' / interval / pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')
    history = args.output_root / 'history' / interval
    failed = []
    for name in args.tickers:
        symbol = TICKERS[name]
        try:
            data = yf.download(symbol, period='8d' if interval == '1m' else '60d',
                               interval=interval, auto_adjust=True, ignore_tz=False,
                               progress=False, threads=False, timeout=30)
            if data is None or data.empty:
                raise ValueError('Provider returned no rows')
            data = normalize_prices(data)
            write_parquet(data, folder / f'{symbol}.parquet')
            destination = history / f'{symbol}.parquet'
            frames = [read_prices(destination), data] if destination.exists() else [data]
            write_parquet(merge_prices(frames), destination)
            print(f'{symbol}: {len(data)} downloaded rows; history updated')
        except Exception as error:
            failed.append(name)
            print(f'{symbol}: FAILED: {error}')
        time.sleep(1)
    if failed:
        raise SystemExit(f'Downloads failed: {", ".join(failed)}')
