import yfinance as yf
import os
from datetime import datetime, timedelta
import pandas as pd
import time
import numpy as np
from scipy.stats import norm

# Define tickers (using ETFs for better options coverage)
TICKERS = {
    "nq100": "QQQ",
    "sp500": "IVV",
    "aapl": "AAPL",
    "msft": "MSFT",
    "nvda": "NVDA",
    "tsla": "TSLA",
    "amzn": "AMZN",
    "goog": "GOOG",
    "btc": "IBIT",   # iShares Bitcoin Trust ETF
    "eth": "ETHA",   # iShares Ethereum Trust ETF
    "gold": "GLD",   # SPDR Gold Shares ETF
    "silver": "SLV", # iShares Silver Trust ETF
    "oil": "USO",    # United States Oil Fund ETF
}

current_date = datetime.now().strftime("%Y-%m-%d")
base_folder = "options_data"
date_folder = os.path.join(base_folder, current_date)

if not os.path.exists(date_folder):
    os.makedirs(date_folder)

# Cache for intraday price data: {(ticker, date_str): DataFrame}
_intraday_cache = {}

def get_risk_free_rate():
    """
    Get the current risk-free rate from 13-week Treasury Bill (^IRX)
    Returns annual rate as a decimal (e.g., 0.04 for 4%)
    """
    try:
        irx = yf.Ticker("^IRX")
        hist = irx.history(period="5d")
        if not hist.empty:
            # ^IRX is quoted as annual percentage, convert to decimal
            rate = hist['Close'].iloc[-1] / 100.0
            return rate
        else:
            print("Warning: Could not fetch risk-free rate, using default 0.04")
            return 0.04
    except Exception as e:
        print(f"Error fetching risk-free rate: {e}, using default 0.04")
        return 0.04

def _bs_price_vec(S, K, T, r, sigma, is_call):
    """
    Vectorized Black-Scholes option price.
    All inputs are numpy arrays of the same length. is_call is a boolean array.
    """
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    discount = K * np.exp(-r * T)
    call_price = S * norm.cdf(d1) - discount * norm.cdf(d2)
    put_price = discount * norm.cdf(-d2) - S * norm.cdf(-d1)
    return np.where(is_call, call_price, put_price)

def _bs_vega_vec(S, K, T, r, sigma):
    """Vectorized Black-Scholes vega."""
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrt_T)
    return S * sqrt_T * norm.pdf(d1)

def calculate_iv_vectorized(market_prices, S_arr, K_arr, T, r, is_call, tol=1e-6):
    """
    Vectorized IV calculation: Newton-Raphson + bisection fallback on whole arrays.
    Returns IV as percentage array (float32). Cap at 5000%.
    """
    n = len(market_prices)
    result = np.full(n, np.nan, dtype=np.float64)

    # Validity mask
    valid = (market_prices > 0) & (S_arr > 0) & (K_arr > 0) & (T > 0)
    # Intrinsic check
    discount_K = K_arr * np.exp(-r * T)
    intrinsic = np.where(is_call, np.maximum(S_arr - discount_K, 0), np.maximum(discount_K - S_arr, 0))
    valid &= market_prices >= intrinsic * 0.99

    idx = np.where(valid)[0]
    if len(idx) == 0:
        return np.round(result * 100, 4).astype(np.float32)

    # Working arrays (only valid entries)
    mp = market_prices[idx]
    S = S_arr[idx]
    K = K_arr[idx]
    Tv = np.full(len(idx), T) if np.isscalar(T) else T[idx]
    ic = is_call[idx] if isinstance(is_call, np.ndarray) else np.full(len(idx), is_call)

    # Smart initial guess
    moneyness = np.abs(np.log(S / K))
    sigma = np.maximum(0.5, moneyness / np.sqrt(Tv))

    # --- Newton-Raphson (50 iterations) ---
    converged = np.zeros(len(idx), dtype=bool)
    for _ in range(50):
        active = ~converged
        if not active.any():
            break
        price = _bs_price_vec(S[active], K[active], Tv[active], r, sigma[active], ic[active])
        vega = _bs_vega_vec(S[active], K[active], Tv[active], r, sigma[active])
        good_vega = vega > 1e-12
        update = np.zeros_like(sigma[active])
        update[good_vega] = (price[good_vega] - mp[active][good_vega]) / vega[good_vega]
        new_sigma = sigma[active] - update
        # Mark bad updates
        bad = (new_sigma <= 0) | (~good_vega)
        new_sigma[bad] = sigma[active][bad]  # keep old sigma for bad ones
        sigma[active] = new_sigma
        # Check convergence
        conv_now = np.abs(price - mp[active]) < tol
        conv_indices = np.where(active)[0][conv_now]
        converged[conv_indices] = True

    # --- Bisection fallback for unconverged (cap 50.0 = 5000%) ---
    need_bisect = ~converged
    if need_bisect.any():
        bi = np.where(need_bisect)[0]
        lo = np.full(len(bi), 0.01)
        hi = np.full(len(bi), 50.0)
        for _ in range(200):
            mid = (lo + hi) / 2.0
            price = _bs_price_vec(S[bi], K[bi], Tv[bi], r, mid, ic[bi])
            below = price < mp[bi]
            lo[below] = mid[below]
            hi[~below] = mid[~below]
            done = (hi - lo) < 1e-8
            if done.all():
                break
        sigma[bi] = (lo + hi) / 2.0
        # Verify bisection results
        final_price = _bs_price_vec(S[bi], K[bi], Tv[bi], r, sigma[bi], ic[bi])
        bisect_ok = np.abs(final_price - mp[bi]) < tol * 100
        sigma[bi[~bisect_ok]] = np.nan

    result[idx] = sigma
    return np.round(result * 100, 4).astype(np.float32)

def _get_intraday_data(ticker_symbol, date_str):
    """
    Get (and cache) intraday 1-minute data for a ticker on a given date.
    Returns the cached DataFrame, downloading only once per (ticker, date).
    """
    cache_key = (ticker_symbol, date_str)
    if cache_key in _intraday_cache:
        return _intraday_cache[cache_key]

    ticker = yf.Ticker(ticker_symbol)
    end_date = (datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    hist = ticker.history(start=date_str, end=end_date, interval="1m")
    if hist.empty:
        # Fallback to hourly
        hist = ticker.history(start=date_str, end=end_date, interval="1h")

    if not hist.empty:
        hist.index = pd.to_datetime(hist.index, utc=True)

    _intraday_cache[cache_key] = hist
    return hist

def get_stock_price_at_time(ticker_symbol, target_datetime, current_price):
    """
    Get the stock price at a specific datetime using cached intraday data.
    If no trade within 5 days, return NaN.
    """
    try:
        if target_datetime.tzinfo is None:
            target_datetime = target_datetime.replace(tzinfo=pd.Timestamp.now(tz='UTC').tzinfo)

        now = pd.Timestamp.now(tz='UTC')
        if (now - target_datetime).days > 5:
            return np.float32(np.nan)

        date_str = target_datetime.strftime('%Y-%m-%d')
        hist = _get_intraday_data(ticker_symbol, date_str)

        if hist.empty:
            return np.float32(current_price)

        closest_idx = hist.index.get_indexer([target_datetime], method='nearest')[0]
        if closest_idx >= 0:
            return np.float32(hist['Close'].iloc[closest_idx])
        else:
            return np.float32(current_price)

    except Exception as e:
        print(f"    Error getting price at time {target_datetime}: {e}")
        return np.float32(current_price)

def process_options_df(df, ticker_symbol, current_price, risk_free_rate, expiration_date, option_type):
    """
    Compresses and formats the options DataFrame according to specific rules.
    Adds underlying price at lastTradeDate time. Prices stored as float32.
    Calculates Black-Scholes IV alongside yfinance IV.
    
    Args:
        expiration_date: expiration date string 'YYYY-MM-DD'
        option_type: 'call' or 'put'
    """
    if df is None or df.empty:
        return df

    # 1. Delete specific columns
    cols_to_drop = [
        'contractSize', 'currency', 'expirationDate', 
        'change', 'percentChange', 'bid', 'ask', 'openInterest'
    ]
    df = df.drop(columns=cols_to_drop, errors='ignore')

    # 2. Rename yfinance IV → IV_yf (percentage, 4dp)
    if 'impliedVolatility' in df.columns:
        df['IV_yf'] = (df['impliedVolatility'] * 100).round(4).astype(np.float32)
        df = df.drop(columns=['impliedVolatility'])

    # 3. Convert inTheMoney to 0 (False) and 1 (True)
    if 'inTheMoney' in df.columns:
        df['inTheMoney'] = df['inTheMoney'].astype(np.int8)

    # 4. Convert price columns to float32
    price_cols = ['lastPrice', 'strike', 'volume']
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].astype(np.float32)

    # 5. Add underlying price at lastTradeDate (using cached intraday data)
    if 'lastTradeDate' in df.columns:
        # Pre-fetch all unique trade dates for this ticker (one API call per date)
        unique_dates = df['lastTradeDate'].dropna().apply(
            lambda x: x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x)[:10]
        ).unique()

        now = pd.Timestamp.now(tz='UTC')
        for d in unique_dates:
            try:
                dt = pd.Timestamp(d, tz='UTC')
                if (now - dt).days <= 5:
                    _get_intraday_data(ticker_symbol, d)
            except Exception:
                pass

        print(f"    Looking up underlying prices at trade times ({len(unique_dates)} unique dates)...")
        df['underlyingPriceAtTrade'] = df['lastTradeDate'].apply(
            lambda x: get_stock_price_at_time(ticker_symbol, x, current_price) if pd.notna(x) else np.float32(np.nan)
        ).astype(np.float32)

    # 6. Calculate Black-Scholes IV using custom risk-free rate (vectorized)
    exp_dt = datetime.strptime(expiration_date, '%Y-%m-%d')
    today = datetime.now()
    T = max((exp_dt - today).days / 365.0, 1 / 365.0)  # time to expiry in years, min 1 day

    S_arr = df['underlyingPriceAtTrade'].values.astype(np.float64) if 'underlyingPriceAtTrade' in df.columns else np.full(len(df), float(current_price))
    # Fill NaN/zero S with current_price
    bad_S = np.isnan(S_arr) | (S_arr <= 0)
    S_arr[bad_S] = float(current_price)

    K_arr = df['strike'].values.astype(np.float64) if 'strike' in df.columns else np.full(len(df), np.nan)
    mp_arr = df['lastPrice'].values.astype(np.float64) if 'lastPrice' in df.columns else np.full(len(df), np.nan)
    is_call = np.full(len(df), option_type == 'call')

    print(f"    Calculating Black-Scholes IV (T={T:.4f}y, r={risk_free_rate:.4f}, type={option_type}, n={len(df)})...")
    df['impliedVolatility'] = calculate_iv_vectorized(mp_arr, S_arr, K_arr, T, float(risk_free_rate), is_call)

    # 7. Add risk-free rate column
    df['riskFreeRate'] = np.float32(risk_free_rate)

    return df

# Get risk-free rate once at the start
risk_free_rate = get_risk_free_rate() + 0.0005 # actual option market rate is higher than risk free rate
print(f"Risk-free rate (^IRX): {risk_free_rate:.4f} ({risk_free_rate*100:.2f}%)")
print(f"Starting options download for {current_date}...")

for name, ticker_symbol in TICKERS.items():
    print(f"\nProcessing {name} ({ticker_symbol})...")
    # Clear intraday cache between tickers to save memory
    _intraday_cache.clear()

    try:
        tk = yf.Ticker(ticker_symbol)

        # Get current/closing price
        try:
            hist = tk.history(period="1d")
            if not hist.empty:
                current_price = np.float32(hist['Close'].iloc[-1])
            else:
                current_price = np.float32(tk.info.get('regularMarketPrice', 0))

            print(f"  Current price: ${current_price:.2f}")
        except Exception as e:
            print(f"  Error getting current price: {e}")
            current_price = np.float32(0)

        # Get expiration dates
        try:
            expirations = tk.options
        except Exception:
            print(f"  No options found for {name} (or API error). Skipping.")
            continue

        if not expirations:
            print(f"  No options found for {name}. Skipping.")
            continue

        print(f"  Found {len(expirations)} expiration dates.")

        # Loop through expirations
        for date in expirations:
            try:
                # Download option chain
                chain = tk.option_chain(date)

                # Format filename: options_data/2026-02-10/aapl_20260217_calls_150_50.csv
                safe_date = date.replace("-", "")
                price_str = f"{current_price:.2f}".replace(".", "_")
                calls_file = os.path.join(date_folder, f"{name}_{safe_date}_calls_{price_str}.csv")
                puts_file = os.path.join(date_folder, f"{name}_{safe_date}_puts_{price_str}.csv")

                # Process and Save Calls
                if chain.calls is not None and not chain.calls.empty:
                    cleaned_calls = process_options_df(chain.calls.copy(), ticker_symbol, current_price, risk_free_rate, date, 'call')
                    cleaned_calls.to_csv(calls_file, index=False)
                    print(f"  Saved {len(cleaned_calls)} calls to {os.path.basename(calls_file)}")

                # Process and Save Puts
                if chain.puts is not None and not chain.puts.empty:
                    cleaned_puts = process_options_df(chain.puts.copy(), ticker_symbol, current_price, risk_free_rate, date, 'put')
                    cleaned_puts.to_csv(puts_file, index=False)
                    print(f"  Saved {len(cleaned_puts)} puts to {os.path.basename(puts_file)}")

                # Sleep to prevent rate limiting
                time.sleep(0.4)

            except Exception as e:
                print(f"  Error fetching {date} for {name}: {e}")

    except Exception as e:
        print(f"Failed to retrieve data for {name}: {e}")

print("\n" + "="*50)
print("Options download complete.")
print(f"Data saved to: {date_folder}")
