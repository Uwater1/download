from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from storage import normalize_prices, write_parquet, read_prices, merge_prices
from combinator import infer_timezone, migrate
from fix_timestamps import convert_prices
from option_download import save_chain

def prices(dates):
    return pd.DataFrame({'Datetime': dates, 'Open': 1., 'High': 2., 'Low': .5, 'Close': 1.5, 'Volume': 10.})

def test_aware_roundtrip_and_latest_wins(tmp_path):
    old = normalize_prices(prices(['2026-06-01 13:30:00+00:00']))
    new = old.copy(); new['Close'] = 1.6
    out = merge_prices([old, new])
    write_parquet(out, tmp_path/'prices.parquet')
    pd.testing.assert_frame_equal(read_prices(tmp_path/'prices.parquet'), out)
    assert len(out) == 1 and out.Close.iloc[0] == 1.6
    with pytest.raises(ValueError, match='explicit timezone'):
        normalize_prices(prices(['2026-06-01 09:30']))

def test_timezone_inferred_from_overlap(tmp_path):
    times = pd.date_range('2026-05-20 13:30', periods=40, freq='min', tz='UTC')
    reference = normalize_prices(prices(times))
    local = prices(times.tz_convert('America/New_York').tz_localize(None))
    file = tmp_path/'raw.csv'; local.to_csv(file, index=False)
    zone, scores = infer_timezone(file, reference)
    assert zone == 'America/New_York' and scores[zone] == 40

def test_exchange_holiday_and_early_close():
    df = normalize_prices(prices(['2026-11-26 15:00+00:00', '2026-11-27 17:59+00:00', '2026-11-27 18:00+00:00']))
    out = convert_prices(df, True)
    assert len(out) == 1
    assert out.Datetime.iloc[0].hour == 12

def test_options_preserve_quotes_and_decimal_iv(tmp_path):
    df = pd.DataFrame({'contractSymbol': ['TEST'], 'bid': [1.], 'ask': [2.], 'impliedVolatility': [.25]})
    assert save_chain(df, 'AAPL', '2026-10-16', 'calls', 'yfinance', tmp_path, '2026-10-01') == 1
    out = pd.read_parquet(next((tmp_path/'history').rglob('*.parquet')))
    assert out.impliedVolatility.iloc[0] == .25 and out.bid.iloc[0] == 1.

def test_migration_cleanup_and_repeatability(tmp_path):
    (tmp_path/'history').mkdir(); (tmp_path/'2026-05-02').mkdir()
    dates = pd.date_range('2026-04-30 13:30', periods=40, freq='min', tz='UTC')
    df = prices(dates); df.to_csv(tmp_path/'history/AAPL.csv', index=False)
    raw = df.rename(columns={'Datetime':'Price'})
    raw.to_csv(tmp_path/'2026-05-02/aapl.csv', index=False)
    migrate(tmp_path, True)
    assert not (tmp_path/'2026-05-02').exists()
    assert len(read_prices(tmp_path/'history/1m/AAPL.parquet')) == 40
    assert len(pd.read_parquet(tmp_path/'history/observations/1m/AAPL.parquet')) == 80
    migrate(tmp_path, True)

def test_invalid_input_blocks_deletion(tmp_path):
    (tmp_path/'history').mkdir(); (tmp_path/'2026-05-02').mkdir()
    path=tmp_path/'2026-05-02/aapl.csv'; path.write_text('bad,data\n1,2\n')
    with pytest.raises(ValueError):
        migrate(tmp_path, True)
    assert path.exists()

@pytest.mark.parametrize('interval', ['1m', '2m', '5m'])
def test_download_to_snapshot_and_history(tmp_path, monkeypatch, interval):
    import price_download
    df = prices(pd.date_range('2026-06-01 13:30', periods=3, freq='min', tz='UTC')).set_index('Datetime')
    df.columns = pd.MultiIndex.from_product([df.columns, ['AAPL']])
    monkeypatch.setattr(price_download.yf, 'download', lambda *a, **kw: df)
    monkeypatch.setattr(price_download.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sys, 'argv', ['download', '--tickers', 'aapl', '--output-root', str(tmp_path)])
    price_download.main(interval)
    price_download.main(interval)
    history = read_prices(tmp_path/f'history/{interval}/AAPL.parquet')
    snapshot = read_prices(next((tmp_path/f'downloads/{interval}').rglob('*.parquet')))
    pd.testing.assert_frame_equal(history, snapshot)
    assert len(history) == 3


def test_empty_download_reports_failure_without_files(tmp_path, monkeypatch):
    import price_download
    monkeypatch.setattr(price_download.yf, 'download', lambda *a, **kw: pd.DataFrame())
    monkeypatch.setattr(price_download.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sys, 'argv', ['download', '--tickers', 'aapl', '--output-root', str(tmp_path)])
    with pytest.raises(SystemExit, match='Downloads failed'):
        price_download.main()
    assert not list(tmp_path.rglob('*.parquet'))

@pytest.mark.parametrize('provider', ['yfinance', 'yahooquery'])
def test_option_provider_pipeline(tmp_path, monkeypatch, provider):
    import option_download
    import yfinance
    import yahooquery
    from types import SimpleNamespace
    df = pd.DataFrame({'contractSymbol': ['AAPLTEST'], 'strike': [100.], 'impliedVolatility': [.25]})
    if provider == 'yfinance':
        ticker = SimpleNamespace(options=['2026-10-16'], option_chain=lambda _: SimpleNamespace(calls=df, puts=df))
        monkeypatch.setattr(yfinance, 'Ticker', lambda _: ticker)
    else:
        chain = df.assign(symbol='AAPL', expiration=pd.Timestamp('2026-10-16'), optionType='calls')
        monkeypatch.setattr(yahooquery, 'Ticker', lambda _: SimpleNamespace(option_chain=chain))
    monkeypatch.setattr(option_download.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sys, 'argv', ['options', '--tickers', 'aapl', '--max-expirations', '1', '--output-root', str(tmp_path)])
    option_download.main(provider)
    files = list((tmp_path/'history/options'/provider).rglob('*.parquet'))
    assert len(files) == (2 if provider == 'yfinance' else 1)
    for path in files:
        result = pd.read_parquet(path)
        assert result.impliedVolatility.iloc[0] == .25 and result.underlyingSymbol.iloc[0] == 'AAPL'
