# Financial Data Downloader

Python 3.12 tools for Yahoo price and option downloads, with verified Zstandard-compressed Parquet storage. Run commands from this checkout; imports do not download data or create files.

## Setup and validation

```sh
python3.12 -m venv /workspace/download-env
/workspace/download-env/bin/python -m pip install -r requirements.txt
/workspace/download-env/bin/python -m pytest -q
```

Yahoo access requires `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `fc.yahoo.com`, and potentially `finance.yahoo.com`, `guce.yahoo.com`, and `consent.yahoo.com`. Public downloads need no API key. A proxy denial or empty provider response causes a nonzero exit; partial successes are retained and reported.

## Downloads

```sh
/workspace/download-env/bin/python download_data.py
/workspace/download-env/bin/python download_2m.py
/workspace/download-env/bin/python 5m.py
/workspace/download-env/bin/python download_options.py
/workspace/download-env/bin/python download_options_yq.py
```

Use `--tickers aapl` and `--output-root /tmp/price-smoke` for a small isolated check. Options also accept `--max-expirations 1`. Defaults include all configured assets. One-minute requests cover eight days; two- and five-minute requests cover sixty days, subject to Yahoo availability.

Price snapshots are written to `downloads/<interval>/<UTC-date>/<Yahoo-symbol>.parquet` and immediately merged into `history/<interval>/<Yahoo-symbol>.parquet`. Schema: `Datetime, Open, High, Low, Close, Volume`. Timestamps retain UTC timezone information; numeric prices use float64 without rounding. Adjustment is explicitly enabled to retain the previous yfinance behavior. The latest downloaded observation wins timestamp collisions. Intervals are never mixed.

Options are written to both `downloads/options/<provider>/<UTC-date>/` and `history/options/<provider>/<UTC-date>/`. New chains preserve provider fields, quotes, open interest, and precision; implied volatility stays a decimal. The old custom Black-Scholes calculation used current expiry timing with historical option prices and could substitute current underlying prices. It has been removed rather than treating those estimates as measured data. Bitcoin, Ethereum, metals, and oil options use the optionable ETF proxies IBIT, ETHA, GLD, SLV, and USO.

## Legacy migration

```sh
/workspace/download-env/bin/python combinator.py
/workspace/download-env/bin/python combinator.py --delete-sources
```

Migration reads existing CSV history and dated snapshots in chronological order, writes and reads back every Parquet output, records source/output SHA-256 hashes and row counts in `history/migration_manifest.json`, and removes sources only with `--delete-sources` after all checks pass. Unknown files, invalid data, or changed source hashes block deletion. Repeating migration after cleanup is a no-op.

Historical files lost timezone labels. The migration compares overlapping OHLCV values against preceding snapshots to identify UTC versus New York, Chicago, or London time. A timezone change requires at least 20 matching rows. When no values match (for example, a futures roll or revised crypto prices), it carries forward the preceding validated timezone and records that assumption in the manifest. It fails if no timezone has been established or candidate scores tie. No timestamps are inferred from the machine timezone.

`history/observations/1m/` retains all normalized one-minute source observations with source paths, including superseded values at overlapping timestamps. Canonical `history/1m/` keeps the latest value. Legacy two- and five-minute data go into their respective interval histories. Old option files go under `history/options/options_data_yq/` (or `options_data/`) without changing their field values or implied-volatility units; original naive option timestamp strings remain unchanged. Old Eastern-time derived outputs are retained in `history/legacy_derived/` with explicit timezone conversion. These derived datasets are not mixed into the one-minute history.

The old `missing.md` report used a simplified session heuristic and is not a reliable exchange-calendar gap report; see its replacement note. No source observations are removed based on guessed trading sessions.

## Utilities

`merge.py first second output.parquet` merges two price files with the second taking precedence. Legacy naive timestamps require `--naive-timezone`.

`fix_timestamps.py input output.parquet` converts aware timestamps to America/New_York. `--regular-hours` filters **equity** bars using the XNYS exchange calendar, including holidays and early closes; closing timestamps are excluded because bars mark interval starts. Without that option all rows are kept. This filter is unsuitable for crypto, futures, or FX.

## Automation

GitHub Actions use Python 3.12 and the pinned dependency file. The weekly workflow runs Saturday at 05:44 UTC; other download workflows are manual. Data-writing workflows share a concurrency group. Dependency pull requests run the separate test workflow and do not download or push market data. Local setup does not trigger Actions or push changes.

## License

See LICENSE.
