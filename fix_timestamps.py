"""Convert UTC prices to Eastern time; optionally filter by the actual XNYS calendar."""
import argparse
from pathlib import Path
import pandas as pd
import exchange_calendars as xcals
from storage import read_prices, write_parquet

def convert_prices(df, regular_hours=False):
    df = df.copy()
    if regular_hours and not df.empty:
        schedule = xcals.get_calendar('XNYS', start=df.Datetime.min().date(),
                                     end=df.Datetime.max().date()).schedule
        times = pd.DatetimeIndex(df.Datetime)
        opens = pd.DatetimeIndex(schedule['open'])
        closes = pd.DatetimeIndex(schedule['close'])
        positions = opens.searchsorted(times, side='right') - 1
        valid = positions >= 0
        # Minute bars mark interval starts, so closing timestamps are excluded.
        valid &= times < closes.take(positions.clip(min=0))
        df = df.loc[valid].copy()
    df['Datetime'] = df.Datetime.dt.tz_convert('America/New_York')
    return df.reset_index(drop=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_file')
    parser.add_argument('output', type=Path)
    parser.add_argument('--naive-timezone')
    parser.add_argument('--regular-hours', action='store_true', help='Equities only: remove holidays and honor early closes')
    args = parser.parse_args()
    df = convert_prices(read_prices(args.input_file, args.naive_timezone), args.regular_hours)
    write_parquet(df, args.output)
    print(f'Saved {len(df)} rows to {args.output}')

if __name__ == '__main__':
    main()
