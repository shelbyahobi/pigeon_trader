import time
import schedule
import requests
import json
import os
from datetime import datetime
import pandas as pd
import sys
import config
import screener
import gc
from strategies.aamr import AAMRStrategy
from strategies.echo import EchoStrategy
from strategies.nia import NIAStrategy
from indicators import calculate_indicators

# --- GLOBAL VARIABLES ---
TOKENS = {}
TOKEN_METADATA = {}
market_data = {}
CANDLE_CACHE = {} # Memory cache: {token_id: (timestamp, df)}

# --- STRATEGY INITIALIZATION ---
strategy = AAMRStrategy()

def get_strategy_for_mode(mode):
    if mode == 'echo':
        return EchoStrategy()
    elif mode == 'nia':
        return NIAStrategy()
    return AAMRStrategy()

# --- LOGGING ---
STATE_FILE = "strategic_state.json"
LOG_FILE = "strategic_log.txt"

def log_msg(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def send_alert(msg):
    log_msg(f"*** ALERT: {msg} ***")

# --- STATE MANAGEMENT ---
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                if 'echo' not in state:
                    log_msg("Initializing Unified State: 70/30 Split")
                    state = {
                        'echo': {'cash': 700.0, 'positions': {}},
                        'nia': {'cash': 300.0, 'positions': {}}
                    }
                return state
        except:
            pass
    return {
        'echo': {'cash': 700.0, 'positions': {}},
        'nia': {'cash': 300.0, 'positions': {}}
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

# --- MARKET CONTEXT FUNCTIONS ---
def fetch_btc_regime():
    """
    Returns (regime_name, multiplier) based on BTC 30d return.
    Bull (>20%) -> 1.5x
    Bear (<-20%) -> 0.5x
    Neutral -> 1.0x
    """
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {'vs_currency': 'usd', 'days': 35, 'interval': 'daily'}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            prices = [p[1] for p in data['prices']]
            if len(prices) >= 30:
                price_now = prices[-1]
                price_30d = prices[-30]
                ret = (price_now / price_30d) - 1
                
                if ret > 0.20:
                    return "BULL", 1.5
                elif ret < -0.20:
                    return "BEAR", 0.5
                else:
                    return "NEUTRAL", 1.0
    except Exception as e:
        log_msg(f"Error fetching BTC regime: {e}")
    
    return "NEUTRAL", 1.0

def fetch_btc_trend():
    """Returns True if BTC > 21-Week EMA"""
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {'vs_currency': 'usd', 'days': 160, 'interval': 'daily'}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            prices = [p[1] for p in data['prices']]
            if len(prices) < 147:
                return True
            
            s = pd.Series(prices)
            ema_21w = s.ewm(span=147, adjust=False).mean().iloc[-1]
            current = prices[-1]
            return current > ema_21w
    except Exception as e:
        # log_msg might not be safe to call here if this runs before log_msg definition
        # But we are placing it after log_msg
        log_msg(f"Error fetching BTC trend: {e}")
    return True

def fetch_funding_rate(symbol):
    """Returns True if funding rate < 0.01%"""
    try:
        binance_symbol = f"{symbol}USDT"
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {'symbol': binance_symbol}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if 'lastFundingRate' in data:
                return float(data['lastFundingRate']) < 0.0001
    except Exception as e:
        log_msg(f"Error fetching funding for {symbol}: {e}")
    return True

def get_fallback_watchlist():
    """Hardcoded quality tokens as fallback to prevent starvation"""
    return [
        {'id': 'chainlink', 'symbol': 'LINK', 'tier': 'upper_mid'},
        {'id': 'uniswap', 'symbol': 'UNI', 'tier': 'core_mid'},
        {'id': 'polkadot', 'symbol': 'DOT', 'tier': 'core_mid'},
        {'id': 'avalanche-2', 'symbol': 'AVAX', 'tier': 'upper_mid'},
        {'id': 'near', 'symbol': 'NEAR', 'tier': 'upper_mid'},
        {'id': 'fantom', 'symbol': 'FTM', 'tier': 'core_mid'},
        {'id': 'optimism', 'symbol': 'OP', 'tier': 'core_mid'},
        {'id': 'arbitrum', 'symbol': 'ARB', 'tier': 'core_mid'},
        {'id': 'fetch-ai', 'symbol': 'FET', 'tier': 'core_mid'},
        {'id': 'render-token', 'symbol': 'RNDR', 'tier': 'core_mid'},
        {'id': 'the-sandbox', 'symbol': 'SAND', 'tier': 'core_mid'},
        {'id': 'decentraland', 'symbol': 'MANA', 'tier': 'core_mid'},
        {'id': 'aave', 'symbol': 'AAVE', 'tier': 'core_mid'},
        {'id': 'injective-protocol', 'symbol': 'INJ', 'tier': 'core_mid'},
        {'id': 'immutable-x', 'symbol': 'IMX', 'tier': 'core_mid'},
        {'id': 'gala', 'symbol': 'GALA', 'tier': 'lower_mid'},
        {'id': 'axie-infinity', 'symbol': 'AXS', 'tier': 'lower_mid'},
        {'id': 'theta-token', 'symbol': 'THETA', 'tier': 'core_mid'},
        {'id': 'enjincoin', 'symbol': 'ENJ', 'tier': 'lower_mid'},
        {'id': 'chiliz', 'symbol': 'CHZ', 'tier': 'lower_mid'},
    ]

def update_watchlist():
    """Update TOKENS from screener"""
    log_msg("Updating watchlist...")
    global TOKENS
    
    try:
        candidates = screener.screen_candidates()
        
        # FAILSAFE: If screener yields too few tokens, use fallback
        # TESTING MODE (Paper=True): Force fallback if list is short (< 10) to ensure good data.
        # PRODUCTION (Paper=False): Only fallback if list is critical (< 3).
        min_candidates = 10 if config.PAPER_MODE else 3
        
        if len(candidates) < min_candidates:
            log_msg(f"⚠️ Screener yielded only {len(candidates)} tokens (Min: {min_candidates}). Using Fallback Watchlist (20 tokens).")
            candidates = get_fallback_watchlist()
            
        TOKENS = {}
        count = 0 
        for c in candidates:
            token_id = c['id']
            # Default to "echo" if tier is missing, but prioritize based on logic
            # Echo: Large/Mid/Upper. NIA: All valid.
            strategies = ['echo', 'nia'] # Default to both for now
            if c.get('tier') == 'small':
                strategies = ['nia'] # Small caps NIA only
            
            TOKENS[token_id] = strategies
            count += 1
            
        log_msg(f"Watchlist updated: {count} tokens")
            
    except Exception as e:
        log_msg(f"Error updating watchlist: {e}")

# --- MARKET DATA ---
def fetch_market_data(token_ids):
    """Fetch current price/ATH for list of tokens"""
    ids_str = ",".join(token_ids)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {'vs_currency': 'usd', 'ids': ids_str}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        market_map = {}
        if isinstance(data, list):
            for item in data:
                market_map[item['id']] = {
                    'price': item['current_price'],
                    'ath': item['ath'],
                    'symbol': item['symbol'].upper()
                }
        return market_map
    except Exception as e:
        log_msg(f"Error fetching market data: {e}")
        return None

# ... (skip to fetch_candle_history) ...

def fetch_candle_history(token_id):
    """Fetch 250 days OHLCV + calculate indicators (with caching)"""
    
    # 1. Check Cache (1 Hour TTL)
    if token_id in CANDLE_CACHE:
        cache_time, cached_df = CANDLE_CACHE[token_id]
        if time.time() - cache_time < 3600:
            return cached_df

    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    params = {'vs_currency': 'usd', 'days': 250, 'interval': 'daily'}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            
            # ... (parsing logic) ...
            prices = data.get('prices', [])
            if not prices: return None
            
            df = pd.DataFrame(prices, columns=['timestamp', 'price'])
            
            # Volumes
            vols = data.get('total_volumes', [])
            if vols:
                df_v = pd.DataFrame(vols, columns=['timestamp', 'total_volume'])
                df['total_volume'] = df_v['total_volume']
                if len(df_v) != len(df):
                    df = pd.merge(df, df_v, on='timestamp', how='left').fillna(0)
            else:
                df['total_volume'] = 0.0
            
            # Timestamps
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('date', inplace=True)
            
            # OHLC proxy
            df['high'] = df['price']
            df['low'] = df['price']
            df['open'] = df['price']
            df['close'] = df['price']
            
            # Indicators
            df = calculate_indicators(df)
            
            # 2. Update Cache
            CANDLE_CACHE[token_id] = (time.time(), df)
            
            return df
            
        elif r.status_code == 429:
            log_msg(f"Rate limited: {token_id}")
    except Exception as e:
        log_msg(f"Error fetching candles for {token_id}: {e}")
    
    return None

def fetch_candle_history_with_retry(token_id, max_retries=2):
    """Fetch candle history with retry on rate limit (Exponential Backoff)"""
    for attempt in range(max_retries + 1):
        df = fetch_candle_history(token_id)
        
        if df is not None:
            return df
        
        # If rate limited and not last attempt, wait and retry
        if attempt < max_retries:
            wait_time = 30 * (attempt + 1)  # 30s, 60s
            log_msg(f"Rate Limited on {token_id}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    log_msg(f"Failed to fetch {token_id} history after {max_retries} retries")
    return None

# --- BOT LOGIC ---
def run_job(mode="echo"):
    start_time = time.time()
    log_msg(f"Running {mode.upper()} pool...")
    
    state = load_state()
    pool = state.get(mode)
    
    if not pool:
        log_msg(f"Error: Pool {mode} not found")
        return
    
    # Select strategy
    global strategy
    strategy = get_strategy_for_mode(mode)
    
    # BTC context
    global_btc_context = True
    if mode == 'echo':
        global_btc_context = fetch_btc_trend()
    
    # Fetch market data
    token_ids = list(TOKENS.keys())
    if not token_ids:
        log_msg(f"No tokens for {mode}")
        return
    
    current_market_data = fetch_market_data(token_ids)
    if not current_market_data:
        log_msg("Market data fetch failed")
        return
    
    log_msg(f"Processing {len(current_market_data)} tokens")
    
    # Process tokens
    for token_id, token_symbol in TOKENS.items():
        if token_id not in current_market_data:
            continue
        
        price = current_market_data[token_id]['price']
        
        # Fetch history with RETRY
        df_hist = fetch_candle_history_with_retry(token_id)
        if df_hist is None or len(df_hist) < 200:
            continue
        
        # --- RATE LIMIT PROTECTION ---
        # Sleep 2s between tokens to prevent API spam (30 calls/min limit)
        # We have 20 tokens, so this adds ~40s to loop which is fine for hourly job.
        time.sleep(2)
        
        # Position state
        current_pos = pool['positions'].get(token_id)
        current_pos_price = current_pos['entry_price'] if current_pos else None
        
        # Trailing stop tracking
        highest_price = None
        if current_pos:
            if 'highest_price' not in current_pos:
                current_pos['highest_price'] = current_pos_price
            if price > current_pos['highest_price']:
                current_pos['highest_price'] = price
            highest_price = current_pos['highest_price']
        
        # Context
        ctx = {}
        if mode == 'echo':
            ctx['btc_bullish'] = global_btc_context
            ctx['funding_ok'] = fetch_funding_rate(token_symbol)
        if mode == 'nia':
            if token_id in TOKEN_METADATA:
                ctx.update(TOKEN_METADATA[token_id])
        
        # Get signal
        signal = strategy.get_signal(df_hist, current_pos_price, highest_price, mode, context=ctx)
        
        # Execute BUY
        if signal == 'BUY' and not current_pos:
            pool_cash = pool['cash']
            risk_cap = 0.05 if mode == 'echo' else 0.10
            
            # Regime Detection logic
            regime, multiplier = fetch_btc_regime()
            
            # Max positions
            max_pos = 10 if mode == 'echo' else 5
            if len(pool['positions']) >= max_pos:
                continue
            
            bet_size = pool_cash * risk_cap * multiplier
            
            # Dust filter
            if bet_size < 10:
                continue
            
            # Fees
            EST_FEE = 0.004
            total_cost = bet_size * (1 + EST_FEE)
            
            if pool_cash >= total_cost:
                amount = bet_size / price
                pool['cash'] -= total_cost
                
                pool['positions'][token_id] = {
                    'entry_price': price,
                    'highest_price': price,
                    'amount': amount,
                    'timestamp': time.time(),
                    'regime_at_entry': regime # Store context
                }
                
                log_msg(f"BUY {token_symbol} ({mode}) @ ${price:.2f} Size: ${bet_size:.1f} ({regime})")
                send_alert(f"BUY {token_symbol} ({mode}) Size: ${bet_size:.1f} [{regime}]")
                
                state[mode] = pool
                save_state(state)
        
        # Execute SELL
        elif signal == 'SELL' and current_pos:
            amount = current_pos['amount']
            gross_proceeds = amount * price
            
            EST_FEE = 0.004
            net_proceeds = gross_proceeds * (1 - EST_FEE)
            
            pnl = net_proceeds - (amount * current_pos['entry_price'])
            
            pool['cash'] += net_proceeds
            del pool['positions'][token_id]
            
            log_msg(f"SELL {token_symbol} ({mode}) @ ${price:.2f} PnL: ${pnl:.2f}")
            send_alert(f"SELL {token_symbol} ({mode}) PnL: ${pnl:.2f}")
            
            state[mode] = pool
            save_state(state)
        
        # Update highest price
        if current_pos and price > current_pos['highest_price']:
            save_state(state)
        
        time.sleep(1)
    
    log_msg(f"{mode.upper()} complete. Cash: ${pool['cash']:.1f}")

def run_fleet():
    log_msg(">>> FLEET: 70% ECHO | 30% NIA <<<")
    run_job(mode="echo")
    
    # Hotfix 3: Inter-Strategy Buffer
    # Echo uses API calls. Give CoinGecko 30s to recover before NIA runs.
    log_msg("Buffer: Sleeping 30s before NIA...")
    time.sleep(30)
    
    run_job(mode="nia")
    log_msg(">>> FLEET COMPLETE <<<")

def main():
    log_msg("--- BOT STARTED ---")
    
    MODE = "echo"
    IS_FLEET = False
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "flash":
            MODE = "flash"
        elif arg == "echo":
            MODE = "echo"
        elif arg == "mixed":
            IS_FLEET = True
    
    # Initial run
    # 1. Hotfix: Ensure State File Exists & Normalized
    # Always load and save on startup to ensure format migration persists
    log_msg("Verifying state integrity...")
    save_state(load_state())

    update_watchlist()
    
    # 2. Hotfix: API Cool-down
    # Screener uses heavy API quota. Pause to let bucket refill before trading.
    # Reviewer recommended 90s to be safe.
    log_msg("Screener complete. Cooling down API for 90s...")
    time.sleep(90)

    if IS_FLEET:
        run_fleet()
        schedule.every(1).hours.do(run_fleet)
    else:
        run_job(MODE)
        schedule.every(1).hours.do(lambda: run_job(mode=MODE))
    
    schedule.every().monday.do(update_watchlist)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
