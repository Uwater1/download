"""Keep full provider option chains in Parquet without estimating missing prices or IV."""
import argparse
from pathlib import Path
import time
import pandas as pd
from storage import ROOT, write_parquet

TICKERS = dict(nq100='QQQ', sp500='IVV', aapl='AAPL', msft='MSFT', nvda='NVDA',
               tsla='TSLA', amzn='AMZN', goog='GOOG', btc='IBIT', eth='ETHA',
               gold='GLD', silver='SLV', oil='USO')

def save_chain(df, symbol, expiration, kind, provider, root, day):
    if df is None or df.empty:
        return 0
    df = df.copy().reset_index(drop=True)
    if 'contractSymbol' not in df or df.contractSymbol.isna().any():
        raise ValueError('Invalid option contract identifiers')
    # Provider IV remains a decimal; quotes, open interest, and native precision remain intact.
    df['underlyingSymbol'] = symbol
    df['expiration'] = pd.Timestamp(expiration).strftime('%Y-%m-%d')
    df['optionType'] = kind
    df['provider'] = provider
    df['snapshotDate'] = day
    filename = f'{symbol}_{pd.Timestamp(expiration):%Y%m%d}_{kind}.parquet'
    for folder in (root / 'downloads' / 'options' / provider / day,
                   root / 'history' / 'options' / provider / day):
        write_parquet(df, folder / filename)
    return len(df)

def main(provider='yfinance'):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickers', nargs='+', choices=list(TICKERS), default=list(TICKERS))
    parser.add_argument('--output-root', type=Path, default=ROOT)
    parser.add_argument('--max-expirations', type=int, help='Limit requests for smoke testing')
    args = parser.parse_args()
    if args.max_expirations is not None and args.max_expirations < 1:
        parser.error('--max-expirations must be positive')
    day = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')
    failures = []
    for name in args.tickers:
        symbol = TICKERS[name]
        count = 0
        try:
            if provider == 'yfinance':
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                expirations = ticker.options
                if args.max_expirations:
                    expirations = expirations[:args.max_expirations]
                for expiration in expirations:
                    chain = ticker.option_chain(expiration)
                    for kind, df in [('calls', chain.calls), ('puts', chain.puts)]:
                        count += save_chain(df, symbol, expiration, kind, provider, args.output_root, day)
                    time.sleep(0.4)
            else:
                from yahooquery import Ticker
                chain = Ticker(symbol).option_chain
                if not isinstance(chain, pd.DataFrame) or chain.empty:
                    raise ValueError('Provider returned no option chains')
                chain = chain.reset_index().rename(columns={'option_type': 'optionType', 'contract_symbol': 'contractSymbol'})
                groups = list(chain.groupby(['expiration', 'optionType'], sort=True))
                allowed = sorted(chain.expiration.unique())
                if args.max_expirations:
                    allowed = allowed[:args.max_expirations]
                for (expiration, kind), df in groups:
                    if expiration in allowed:
                        count += save_chain(df, symbol, expiration, kind, provider, args.output_root, day)
            if count == 0:
                raise ValueError('Provider returned no option rows')
            print(f'{symbol}: saved {count} option rows')
        except Exception as error:
            print(f'{symbol}: FAILED: {error}')
            failures.append(name)
        time.sleep(1)
    if failures:
        raise SystemExit(f'Options failed: {", ".join(failures)}')
