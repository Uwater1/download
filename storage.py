"""Validated, atomic Parquet storage shared by download and migration tools."""
from pathlib import Path
import os
import tempfile
import pandas as pd

ROOT = Path(__file__).resolve().parent
TICKERS = dict(gold='GC=F', silver='SI=F', oil='CL=F', BTC='BTC-USD', ETH='ETH-USD',
              nq100='QQQ', sp500='IVV', aapl='AAPL', msft='MSFT', nvda='NVDA', tsla='TSLA',
              amzn='AMZN', goog='GOOG', meta='META', avgo='AVGO', pltr='PLTR',
              usdjpy='JPY=X', usdcad='CAD=X', eurusd='EURUSD=X', gbpusd='GBPUSD=X',
              audusd='AUDUSD=X', usdchf='CHF=X')
COLS = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']

def write_parquet(df, path):
    path = Path(path)
    if path.suffix != '.parquet':
        raise ValueError('Output must use .parquet')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.parquet')
    os.close(fd)
    try:
        df.to_parquet(temporary, index=False, compression='zstd')
        pd.testing.assert_frame_equal(df.reset_index(drop=True), pd.read_parquet(temporary))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def normalize_prices(df, naive_timezone=None):
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        if len(df.columns.get_level_values(1).unique()) != 1:
            raise ValueError('Expected one ticker')
        df.columns = df.columns.get_level_values(0)
    if isinstance(df.index, pd.DatetimeIndex):
        df.index.name = 'Datetime'
        df = df.reset_index()
    df = df.rename(columns={'Price': 'Datetime', 'time': 'Datetime',
                            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'})
    if not set(COLS).issubset(df.columns):
        raise ValueError(f'Missing OHLCV columns: {list(df.columns)}')
    df = df[COLS]
    dates = pd.to_datetime(df.Datetime, format='mixed', errors='raise')
    if dates.dt.tz is None:
        if naive_timezone is None:
            raise ValueError('Naive timestamps require an explicit timezone')
        dates = dates.dt.tz_localize(naive_timezone, ambiguous='raise', nonexistent='raise')
    df['Datetime'] = dates.dt.tz_convert('UTC')
    for col in COLS[1:]:
        df[col] = pd.to_numeric(df[col], errors='raise').astype('float64')
    if df.isna().any().any() or not __import__('numpy').isfinite(df[COLS[1:]]).all().all():
        raise ValueError('Missing or nonfinite OHLCV data')
    if (df.Volume < 0).any():
        raise ValueError('Negative volume')
    return df.reset_index(drop=True)

def read_prices(path, naive_timezone=None):
    path = Path(path)
    if path.suffix == '.parquet':
        df = pd.read_parquet(path)
    else:
        with path.open() as f:
            f.readline()
            multi = f.readline().startswith('Ticker,')
        df = pd.read_csv(path, skiprows=[1, 2] if multi else None)
    return normalize_prices(df, naive_timezone)

def merge_prices(frames):
    return (pd.concat(frames, ignore_index=True).drop_duplicates('Datetime', keep='last')
            .sort_values('Datetime').reset_index(drop=True))
