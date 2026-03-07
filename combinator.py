import os
import glob
import pandas as pd
from datetime import datetime, timedelta, time
import pytz

def get_ticker_from_file(filepath):
    """
    Extracts the ticker symbol from the second line of the CSV file.
    """
    try:
        with open(filepath, 'r') as f:
            f.readline() # Skip first line
            line2 = f.readline()
            parts = line2.strip().split(',')
            if len(parts) > 1:
                return parts[1]
    except Exception as e:
        print(f"Error reading ticker from {filepath}: {e}")
    return None

def load_existing_history(output_dir):
    """
    Loads existing CSV files from the history directory.
    """
    existing_data = {}
    if os.path.exists(output_dir):
        csv_files = glob.glob(os.path.join(output_dir, "*.csv"))
        for filepath in csv_files:
            try:
                # The history files are already in standard format: Datetime,Open,High,Low,Close,Volume
                df = pd.read_csv(filepath)
                df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)
                ticker = os.path.splitext(os.path.basename(filepath))[0]
                existing_data[ticker] = [df]
                print(f"Loaded existing history for {ticker}")
            except (pd.errors.ParserError, KeyError, ValueError) as e:
                print(f"Error reading existing history {filepath}: {e}")
    return existing_data

def is_trading_time(ticker, dt):
    """
    Checks if the given datetime is within trading hours for the asset.
    All times evaluated in US/Eastern.
    - Crypto (-USD): 24/7
    - Futures (=F): Sun 18:00 to Fri 17:00, daily break 17:00-18:00
    - Forex (=X): Sun 17:00 to Fri 17:00
    - Stocks (Others): Mon-Fri 09:30-16:00
    """
    if ticker.endswith('-USD'):
        return True

    eastern = pytz.timezone('US/Eastern')
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    dt_eastern = dt.astimezone(eastern)

    weekday = dt_eastern.weekday() # Mon=0, Sun=6
    current_time = dt_eastern.time()

    t17 = time(17, 0)
    t18 = time(18, 0)
    t0930 = time(9, 30)
    t1600 = time(16, 0)

    if ticker.endswith('=F'):
        # Friday close at 17:00
        if weekday == 4 and current_time >= t17:
            return False
        # Saturday closed
        if weekday == 5:
            return False
        # Sunday open at 18:00
        if weekday == 6 and current_time < t18:
            return False
        # Daily break 17:00-18:00
        if t17 <= current_time < t18:
            return False
        return True

    if ticker.endswith('=X') or ticker.endswith('USD=X'):
        # Friday close at 17:00
        if weekday == 4 and current_time >= t17:
            return False
        # Saturday closed
        if weekday == 5:
            return False
        # Sunday open at 17:00
        if weekday == 6 and current_time < t17:
            return False
        return True

    # Stocks
    if weekday >= 5: # Sat, Sun
        return False
    if t0930 <= current_time <= t1600:
        return True
    return False

def main():
    output_dir = "history"
    report_file = "missing.md"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Find source directories
    # Pattern: YYYY-MM-DD/ and not ending with _5m
    all_dirs = glob.glob("*/")
    source_dirs = []
    for d in all_dirs:
        d = d.rstrip('/')
        if not d.endswith('_5m') and len(d.split('-')) == 3:
             # Basic check if it looks like a date
             try:
                 datetime.strptime(d, "%Y-%m-%d")
                 source_dirs.append(d)
             except ValueError:
                 pass

    print(f"Found source directories: {source_dirs}")

    ticker_data = load_existing_history(output_dir)

    for d in source_dirs:
        csv_files = glob.glob(os.path.join(d, "*.csv"))
        for filepath in csv_files:
            ticker = get_ticker_from_file(filepath)
            if not ticker:
                print(f"Skipping {filepath}: Could not extract ticker")
                continue

            # Read CSV
            try:
                # Skip header rows 1 and 2 (0-indexed lines 1 and 2), keep line 0 as header but we will rename
                df = pd.read_csv(filepath, skiprows=[1, 2])

                # Rename Price to Datetime
                if 'Price' in df.columns:
                    df.rename(columns={'Price': 'Datetime'}, inplace=True)

                # Normalize columns to standard OHLCV
                cols = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
                if set(cols).issubset(df.columns):
                    df = df[cols]

                # Convert Datetime to datetime objects
                df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)

                if ticker not in ticker_data:
                    ticker_data[ticker] = []
                ticker_data[ticker].append(df)

            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    missing_report = "# Missing Data Report\n\n"

    for ticker, dfs in ticker_data.items():
        print(f"Processing {ticker}...")
        full_df = pd.concat(dfs)

        # Drop duplicates based on Datetime
        full_df.drop_duplicates(subset=['Datetime'], keep='last', inplace=True)

        # Sort by Datetime
        full_df.sort_values('Datetime', inplace=True)
        full_df.reset_index(drop=True, inplace=True)

        # Save to CSV
        output_path = os.path.join(output_dir, f"{ticker}.csv")
        full_df.to_csv(output_path, index=False)
        print(f"Saved {output_path}")

        # Check for missing data
        if len(full_df) > 1:
            min_dt = full_df['Datetime'].min()
            max_dt = full_df['Datetime'].max()

            # Generate expected range
            expected_range = pd.date_range(start=min_dt, end=max_dt, freq='1min', tz='UTC')

            # Find missing timestamps
            # Convert to sets for faster comparison
            existing_timestamps = set(full_df['Datetime'])

            # Filter expected range
            expected_range_filtered = [dt for dt in expected_range if is_trading_time(ticker, dt)]

            missing_timestamps = sorted(list(set(expected_range_filtered) - existing_timestamps))

            if missing_timestamps:
                # Group consecutive missing timestamps
                gaps = []
                if len(missing_timestamps) > 0:
                    start_gap = missing_timestamps[0]
                    prev_gap = missing_timestamps[0]

                    for dt in missing_timestamps[1:]:
                        if dt == prev_gap + timedelta(minutes=1):
                            prev_gap = dt
                        else:
                            gaps.append((start_gap, prev_gap))
                            start_gap = dt
                            prev_gap = dt
                    gaps.append((start_gap, prev_gap))

                ticker_has_significant_missing = False
                temp_report = ""
                for start, end in gaps:
                    duration = end - start + timedelta(minutes=1)
                    # Ignore gap <= 2 minutes
                    if duration <= timedelta(minutes=2):
                        continue

                    if not ticker_has_significant_missing:
                        temp_report += f"## {ticker}\n\n"
                        ticker_has_significant_missing = True

                    start_str = start.strftime('%Y-%m-%d %H:%M')
                    end_str = end.strftime('%Y-%m-%d %H:%M')
                    temp_report += f"{start_str} to {end_str} ({duration})\n\n"

                if ticker_has_significant_missing:
                    missing_report += temp_report + "\n"

    with open(report_file, 'w') as f:
        f.write(missing_report)
    print(f"Missing data report saved to {report_file}")

if __name__ == "__main__":
    main()
