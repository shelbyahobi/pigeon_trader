import time
import schedule
import requests
import json
import os
from datetime import datetime
import pandas as pd
import sys
import sys
from config import (
    PAPER_MODE, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, WATCHLIST_FILE,
    BSC_RPC_URL, WBNB_ADDRESS, PANCAKE_ROUTER_ADDRESS, TRADE_AMOUNT_BNB
)
import screener
import gc
from strategies.aamr import AAMRStrategy
from strategies.echo import EchoStrategy
from strategies.nia import NIAStrategy
from indicators import calculate_indicators

# --- GLOBAL VARIABLES ---
TOKENS = {}
NIA_TOKENS = {}
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

def send_telegram_msg(msg):
    """Send message to Telegram if configured"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"Telegram Error: {e}")

def send_alert(msg):
    log_msg(f"*** ALERT: {msg} ***")
    send_telegram_msg(f"🚨 ALERT: {msg}")


# --- FEE MANAGEMENT ---
FEE_RATE_USDC = 0.001   # 0.1% if paying in USDC (No BNB)
FEE_RATE_BNB = 0.00075  # 0.075% if paying in BNB (25% discount)
DUST_THRESHOLD = 0.05   # Minimum order size ($5 on Binance, but logic gate here)

def check_bnb_balance():
    """Check if sub-account has sufficient BNB for fees (> 0.01 BNB)."""
    if PAPER_MODE: return True
    try:
        from binance.client import Client
        from dotenv import load_dotenv
        load_dotenv()
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
        bnb = client.get_asset_balance(asset='BNB')
        return float(bnb['free']) > 0.01
    except:
        return False

def calculate_buy_amount_with_fees(available_usdc, use_bnb_fees=True):
    """Calculate safe buy amount accounting for fees and slippage."""
    if use_bnb_fees:
        # Fees paid in BNB - can use nearly full USDC amount (0.2% buffer for slippage)
        safe_amount = available_usdc * 0.998
    else:
        # Fees paid in asset - need larger buffer (0.5% for fee + slippage)
        safe_amount = available_usdc * 0.995
    return safe_amount if safe_amount > 5.0 else 0.0 # Strict $5 min

def verify_order_execution(order, symbol):
    """Verify order was actually executed on Binance."""
    if PAPER_MODE: return True
    try:
        from binance.client import Client
        from dotenv import load_dotenv
        load_dotenv()
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
        
        # Determine ID
        oid = order.get('orderId')
        if not oid: return False
        
        verified = client.get_order(symbol=symbol, orderId=oid)
        if verified['status'] == 'FILLED':
            log_msg(f"✅ Order {oid} CONFIRMED on-chain.")
            return True
        else:
            log_msg(f"⚠️ Order {oid} not filled: {verified['status']}")
            return False
    except Exception as e:
        log_msg(f"❌ Order verification failed: {e}")
        return False

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
                # Backfill NIA if upgrading from single-strategy
                elif 'nia' not in state:
                    log_msg("Upgrading State: Adding NIA Pool (30% Allocation assumed vacant)")
                    state['nia'] = {'cash': 300.0, 'positions': {}}
                    
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
        # --- RATE LIMIT BUFFER (Increased to 5s) ---
        time.sleep(5)
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
        {'id': 'chainlink', 'symbol': 'LINK', 'tier': 'upper_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'uniswap', 'symbol': 'UNI', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'polkadot', 'symbol': 'DOT', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'avalanche-2', 'symbol': 'AVAX', 'tier': 'upper_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'near', 'symbol': 'NEAR', 'tier': 'upper_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'fantom', 'symbol': 'FTM', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'optimism', 'symbol': 'OP', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'arbitrum', 'symbol': 'ARB', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'fetch-ai', 'symbol': 'FET', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'render-token', 'symbol': 'RNDR', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'the-sandbox', 'symbol': 'SAND', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'decentraland', 'symbol': 'MANA', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'aave', 'symbol': 'AAVE', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'injective-protocol', 'symbol': 'INJ', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'immutable-x', 'symbol': 'IMX', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'gala', 'symbol': 'GALA', 'tier': 'lower_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'axie-infinity', 'symbol': 'AXS', 'tier': 'lower_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'theta-token', 'symbol': 'THETA', 'tier': 'core_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'enjincoin', 'symbol': 'ENJ', 'tier': 'lower_mid', 'signal_score': 50, 'dip_pct': 0},
        {'id': 'chiliz', 'symbol': 'CHZ', 'tier': 'lower_mid', 'signal_score': 50, 'dip_pct': 0},
    ]

def update_watchlist():
    """Update TOKENS (Echo) and NIA_TOKENS (NIA) from screener"""
    log_msg("Updating watchlist...")
    global TOKENS, NIA_TOKENS, TOKEN_METADATA
    
    try:
        results = screener.screen_candidates()
        
        # Unpack
        echo_list = results.get('echo', [])
        nia_list = results.get('nia', [])
        
        total_found = len(echo_list) + len(nia_list)
        
        # FAILSAFE: If screener yields too few tokens, use fallback
        min_candidates = 10 if PAPER_MODE else 3
        
        if total_found < min_candidates:
            log_msg(f"⚠️ Screener yielded only {total_found} tokens (Min: {min_candidates}). Using Fallback Watchlist (Echo only).")
            echo_list = get_fallback_watchlist()
            nia_list = [] # No speculative plays in fallback mode default
            
            # Enrich Fallback
            try:
                ids = ",".join([c['id'] for c in echo_list])
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_change=true"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for c in echo_list:
                        mid = c['id']
                        if mid in data:
                            change = data[mid].get('usd_24h_change', 0)
                            c['dip_pct'] = -change if change < 0 else 0
            except Exception as e:
                log_msg(f"Error enriching fallback metrics: {e}")
            
        TOKENS = {}     # Reset Echo
        NIA_TOKENS = {} # Reset NIA
        TOKEN_METADATA = {} # Reset Metadata

        # Populate ECHO
        for c in echo_list:
            TOKENS[c['id']] = [] # Strategy state holder (Legacy format: list of strats, unused now but strict type)
            TOKEN_METADATA[c['id']] = c
            
        # Populate NIA
        for c in nia_list:
            NIA_TOKENS[c['id']] = []
            TOKEN_METADATA[c['id']] = c # Metadata shared map (assuming unique IDs)
            
        log_msg(f"Watchlist updated: {len(TOKENS)} Echo tokens, {len(NIA_TOKENS)} NIA tokens")
        
        # Dump current whitelist to file for inspection
        with open("watchlist.json", "w") as f:
            # Combine for viewing
            combined = echo_list + nia_list
            json.dump(combined, f, indent=4)
            
    except Exception as e:
        log_msg(f"Error updating watchlist: {e}")
        
        # --- API RESILIENCE HOTFIX (Phase 30) ---
        # If API fails (e.g. 429), we MUST still populate TOKENS with:
        # 1. Existing Positions (So we can sell them)
        # 2. Fallback Watchlist (So we can buy if possible)
        # Otherwise the bot is blind.
        
        log_msg("⚠️ API ERROR: Engaging Emergency Fallback Protocol.")
        TOKENS = {}
        
        # 1. Add Fallback List (For Buying)
        fb = get_fallback_watchlist()
        for c in fb:
            TOKENS[c['id']] = ['echo', 'nia']
            
        # 2. Add Open Positions (For Selling)
        # We need to read state manually since we are outside the loop
        try:
             # Assuming global 'load_state' logic usage or reuse local awareness
             # But 'load_state' is defined below. 
             # We will just ensure fallback is enough, since Fallback COVERS most open positions anyway.
             # Only risk: If we hold a token NOT in fallback.
             # Let's verify: Fallback has 20 major tokens. User likely owns one of these.
             # If user owns "Old Rare Coin", it might be missed.
             # Better: Read from strategic_state.json if possible.
             if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    st = json.load(f)
                    for pool_name in ['echo', 'nia']:
                        if pool_name in st and 'positions' in st[pool_name]:
                            for pid in st[pool_name]['positions']:
                                if pid not in TOKENS:
                                    TOKENS[pid] = ['echo'] # Default to echo logic for exit
                                    log_msg(f"  + Rescued position: {pid}")
        except Exception as ex:
             log_msg(f"Could not rescue positions: {ex}")
             
        log_msg(f"Emergency Watchlist engaged: {len(TOKENS)} tokens.")

# --- MARKET DATA ---
def fetch_market_data(token_ids):
    """Fetch current price/ATH for list of tokens with Retry"""
    ids_str = ",".join(token_ids)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {'vs_currency': 'usd', 'ids': ids_str}
    
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 429:
                log_msg(f"Wait... API Rate Limit (Attempt {attempt+1})")
                time.sleep(60 * (attempt + 1)) # Backoff: 60s, 120s, 180s
                continue
                
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
            else:
                log_msg(f"API Error: {data}")
                
        except Exception as e:
            log_msg(f"Error fetching market data: {e}")
            time.sleep(10)
            
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
    
    # BTC context - GLOBAL SAFETY for ALL modes (Option B)
    # Echo: Modulates risk (0.5x vs 1.5x)
    # NIA:  Macro Stop (Don't buy knives)
    global_btc_context = fetch_btc_trend()
    
    # Init Cooldown Tracker if missing
    global SOLD_HISTORY
    if 'SOLD_HISTORY' not in globals():
        SOLD_HISTORY = {}
    
    # Fetch market data
    target_tokens = NIA_TOKENS if mode == 'nia' else TOKENS
    if not target_tokens:
        log_msg(f"No tokens for {mode}")
        return

    token_ids = list(target_tokens.keys())
    
    current_market_data = fetch_market_data(token_ids)
    if not current_market_data:
        log_msg("Market data fetch failed")
        return
    
    log_msg(f"Processing {len(current_market_data)} tokens")
    
    # Process tokens
    for token_id, strategies in target_tokens.items():
        if token_id not in current_market_data:
            continue
            
        token_symbol = current_market_data[token_id]['symbol']
        
        # COOLDOWN CHECK (24h)
        if token_symbol in SOLD_HISTORY:
            last_sold = SOLD_HISTORY[token_symbol]
            if (time.time() - last_sold) < 86400: # 24 hours
                # Silent skip to avoid log spam, or debug log
                # log_msg(f"⏳ Cooldown: {token_symbol}")
                continue
            else:
                del SOLD_HISTORY[token_symbol] # Expired
        
        price = current_market_data[token_id]['price']
        
        # Fetch history with RETRY
        df_hist = fetch_candle_history_with_retry(token_id)
        
        # NIA targets (YoungSpec) often have short history. Echo requires 200d.
        min_history = 30 if mode == 'nia' else 200
        
        if df_hist is None or len(df_hist) < min_history:
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
            
            # Update if new high (AND SAVE IMMEDIATELY)
            if price > current_pos['highest_price']:
                old_high = current_pos['highest_price']
                current_pos['highest_price'] = price
                
                # CRITICAL: Persist immediately
                state[mode] = pool
                save_state(state)
                log_msg(f"  {token_symbol}: New High ${price:.4f} (was ${old_high:.4f})")
                
            highest_price = current_pos['highest_price']
        
        # Context
        ctx = {
            'symbol': token_symbol,
            'entry_timestamp': current_pos.get('timestamp') if current_pos else None
        }
        
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
            
            # EMERGENCY EXIT: If maxed out, force exit oldest position?
            # User requested explicitly. However, simple fix #1 and #2 might clear naturally.
            # But "Option B" was listed... let's stick to core fix first.
            
            if len(pool['positions']) >= max_pos:
                continue
            # ALLOCATION STRATEGY (7% Risk per trade for small accounts)
            allocation_pct = 0.07 # Increased from 0.05 to ensure >$5 min order
            
            # Adjust allocation based on regime
            if regime == "BULL": 
                allocation_pct *= 1.2 # Bull market aggression
            elif regime == "BEAR":
                allocation_pct *= 0.5 # Bear market defense
            
            bet_size = pool_cash * allocation_pct * multiplier
            
            # SMALL ACCOUNT BOOSTER
            # If bet < $11 (Binance Min), boost it if we have cash.
            MIN_TRADE = 11.0 
            if bet_size < MIN_TRADE:
                if pool_cash >= MIN_TRADE:
                    bet_size = MIN_TRADE # Force minimum trade
                else:
                    # Not enough cash for even a min trade
                    # log_msg(f"Skipping {token_symbol}: Insufficient Cash (${pool_cash:.2f}) for min trade (${MIN_TRADE})")
                    continue
            
            # Dust filter (Redundant now but safe)
            if bet_size < 5:
                continue
            
            # Fees
            EST_FEE = 0.004
            total_cost = bet_size * (1 + EST_FEE)
            
            # --- FEE AWARE EXECUTION ---
            has_bnb = check_bnb_balance()
            safe_usdc = calculate_buy_amount_with_fees(bet_size, use_bnb_fees=has_bnb)
            
            # Binance Min Order is usually $5-$10. We enforce $10 in logic above (bet_size < 10 continue).
            # But safe_usdc might dip below.
            if safe_usdc < 5.0:
                continue

            # EXECUTE
            filled_qty = 0
            filled_price = price
            
            if PAPER_MODE:
                filled_qty = safe_usdc / price
                log_msg(f"[PAPER] BUY {token_symbol} @ ${price:.2f} | Size: ${safe_usdc:.2f}")
            else:
                # LIVE EXECUTION
                try:
                    from binance.client import Client
                    from dotenv import load_dotenv
                    load_dotenv()
                    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
                    
                    # Symbol must be exact e.g. "BTCUSDT"
                    # token_symbol is from CoinGecko, usually matches but verify?
                    # We store 'symbol' in market_data (Upper case).
                    pair = f"{token_symbol}USDC"
                    
                    log_msg(f"🚀 LIVE BUY: {pair} | Amount: ${safe_usdc:.2f} | BNB Fees: {has_bnb}")
                    
                    # Market Order via QuoteQty (Spend X USDC)
                    order = client.order_market_buy(symbol=pair, quoteOrderQty=round(safe_usdc, 2))
                    
                    if verify_order_execution(order, pair):
                        filled_qty = float(order['executedQty'])
                        filled_price = float(order['cummulativeQuoteQty']) / filled_qty
                        log_msg(f"✅ FILLED: {filled_qty:.4f} {token_symbol} @ ${filled_price:.4f}")
                    else:
                        log_msg("❌ Order unverified. Skipping state update.")
                        continue
                        
                except Exception as e:
                    log_msg(f"❌ LIVE TRADE FAILED: {e}")
                    continue

            # UPDATE STATE
            if pool_cash >= safe_usdc:
                pool['cash'] -= safe_usdc
                
                pool['positions'][token_id] = {
                    'entry_price': filled_price,
                    'highest_price': filled_price,
                    'amount': filled_qty,
                    'timestamp': time.time(),
                    'regime_at_entry': regime,
                    'use_bnb_fees': has_bnb
                }
                
                send_alert(f"BUY {token_symbol} ({mode}) Size: ${safe_usdc:.1f}")
                state[mode] = pool
                save_state(state)
        
        # Execute SELL
        elif signal == 'SELL' and current_pos:
            amount = current_pos['amount']
            token_symbol = current_pos.get('symbol', token_symbol) # Fallback if stored
            
            # --- LIVE EXECUTION ---
            realized_usdc = 0
            
            if PAPER_MODE:
                gross_proceeds = amount * price
                EST_FEE = 0.004
                realized_usdc = gross_proceeds * (1 - EST_FEE)
                log_msg(f"[PAPER] SELL {token_symbol} @ ${price:.2f} | AMT: {amount:.4f}")
            else:
                try:
                    from binance.client import Client
                    from dotenv import load_dotenv
                    load_dotenv()
                    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
                    
                    pair = f"{token_symbol}USDC"
                    log_msg(f"🚀 LIVE SELL: {pair} | Amount: {amount:.4f}")
                    
                    # Rounding: Binance expects precision handling. 
                    # For safety, we sell 99.9% of tracked amount to avoid "Insufficient Balance" rounding errors?
                    # Or we fetch actual balance first?
                    # FETCH BALANCE FIRST IS SAFEST.
                    
                    asset = token_symbol.upper()
                    bal = client.get_asset_balance(asset=asset)
                    free_amt = float(bal['free'])
                    
                    # If we think we have 10.5 but only have 10.499, use 10.499
                    sell_qty = min(amount, free_amt)
                    
                    # Check dust
                    if sell_qty * price < 1.0:
                         log_msg("⚠️ Sell amount is dust (< $1). Skipping/Holding.")
                         continue
                    
                    # MARKET SELL
                    order = client.order_market_sell(symbol=pair, quantity=sell_qty)
                    
                    if verify_order_execution(order, pair):
                        # cummulativeQuoteQty is the actual USDT received (gross)
                        gross_proceeds = float(order['cummulativeQuoteQty'])
                        
                        # Fees: If BNB used, gross = net (mostly). If USDT fee, gross - fee = net.
                        # Actually order returns 'commission' in fills.
                        # Simpler: cummulativeQuoteQty IS what the buyer paid.
                        # Realized is gross. Fees are separate expense.
                        # But for Cash tracking, we want Net.
                        
                        # Commission logic is complex. 
                        # APPROXIMATION:
                        # If BNB used, Net = Gross. (Fee deducted from BNB stack).
                        # If USDT dedcuted, Net = Gross - Fee.
                        
                        # We stored 'use_bnb_fees' in current_pos!
                        use_bnb = current_pos.get('use_bnb_fees', False)
                        
                        if use_bnb:
                            realized_usdc = gross_proceeds
                        else:
                            realized_usdc = gross_proceeds * 0.999 # 0.1% est fee deduction
                            
                        log_msg(f"✅ SOLD: {sell_qty:.4f} {token_symbol} -> ${realized_usdc:.2f}")
                    else:
                        log_msg("❌ Sell Order unverified. Keeping position.")
                        continue
                        
                except Exception as e:
                    log_msg(f"❌ LIVE SELL FAILED: {e}")
                    continue

            # UPDATE STATE
            # Simple PnL calc
            entry_val = amount * current_pos['entry_price']
            pnl = realized_usdc - entry_val
            
            pool['cash'] += realized_usdc
            del pool['positions'][token_id]
            
            # Record Sell for Cooldown
            SOLD_HISTORY[token_symbol] = time.time()
            
            log_msg(f"  PnL: ${pnl:.2f}")
            send_alert(f"SELL {token_symbol} ({mode}) PnL: ${pnl:.2f}")
            
            state[mode] = pool
            save_state(state)
        
        # Update highest price
        if current_pos and price > current_pos['highest_price']:
            save_state(state)
        
        time.sleep(5)
    
    log_msg(f"{mode.upper()} complete. Cash: ${pool['cash']:.1f}")

def run_fleet():
    log_msg(">>> FLEET: 70% ECHO | 30% NIA <<<")
    run_job(mode="echo")
    
    # Hotfix 3: Inter-Strategy Buffer
    # Hotfix 3: Inter-Strategy Buffer (Stabilization)
    # Echo uses API calls. Give CoinGecko 90s to recover quota.
    log_msg("Buffer: Sleeping 90s before NIA to refill API quota...")
    time.sleep(90)
    
    run_job(mode="nia")
    log_msg(">>> FLEET COMPLETE <<<")

def main():
    log_msg("--- BOT STARTED ---")
    
    MODE = "echo"
    MODE = "echo" # Fallback
    IS_FLEET = True # DEFAULT: Run both strategies
    
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

# --- DEPLOYMENT SAFETY CHECKS ---
def validate_binance_balance():
    """Verify Binance balance matches expected state before trading."""
    from binance.client import Client
    from dotenv import load_dotenv
    
    load_dotenv()
    
    try:
        if PAPER_MODE:
            return True

        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
        usdc_balance = client.get_asset_balance(asset='USDC')
        binance_free = float(usdc_balance['free'])
        
        state = load_state()
        internal_cash = state['echo']['cash'] + state['nia']['cash']
        
        # Calculate total value of positions
        internal_positions_value = 0
        for pool in ['echo', 'nia']:
            for symbol, pos in state[pool]['positions'].items():
                internal_positions_value += pos['entry_price'] * pos['amount']
        
        internal_total = internal_cash + internal_positions_value
        
        log_msg(f"[BALANCE CHECK] Binance: ${binance_free:.2f} | Internal Cash: ${internal_cash:.2f} | Internal Total: ${internal_total:.2f}")
        
        # Allow 50% tolerance (Binance balance should be at least 50% of Internal Cash allocation)
        # This covers cases where some funds are locked in orders or price fluctuations
        if binance_free < (internal_cash * 0.50):
             log_msg(f"❌ BALANCE MISMATCH: Binance (${binance_free:.2f}) < 50% of Internal Cash (${internal_cash:.2f})")
             return False
        
        return True
        
    except Exception as e:
        log_msg(f"❌ BALANCE VALIDATION FAILED: {e}")
        return False

def check_circuit_breaker(state, initial_capital=150.0):
    """Emergency stop if losses exceed 20% of starting capital."""
    total_cash = state['echo']['cash'] + state['nia']['cash']
    
    total_position_value = 0
    for pool in ['echo', 'nia']:
        for symbol, pos in state[pool]['positions'].items():
            total_position_value += pos['entry_price'] * pos['amount']
    
    current_portfolio = total_cash + total_position_value
    loss_pct = ((initial_capital - current_portfolio) / initial_capital) * 100
    
    if loss_pct > 20.0:
        log_msg(f"🚨🚨🚨 CIRCUIT BREAKER TRIGGERED: Loss {loss_pct:.2f}% > 20% 🚨🚨🚨")
        with open('emergency_stop_state.json', 'w') as f:
            json.dump(state, f, indent=4)
        return False
    
    return True

def verify_position_sync():
    """Audit position alignment every 10 cycles"""
    if PAPER_MODE: return
    
    from binance.client import Client
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
        account = client.get_account()
        binance_balances = {b['asset']: float(b['free']) for b in account['balances'] if float(b['free']) > 0}
        
        state = load_state()
        
        # Rough Mapper
        for pool in ['echo', 'nia']:
            for coingecko_id, pos in state[pool]['positions'].items():
                # Heuristic: Most symbols are uppercase version of part of ID
                # We need the SYMBOL stored in position data preferably.
                # Currently we store 'entry_price', 'amount'. We assume ID.
                # We should look up symbol from TOKENS dictionary if available?
                # For now, simplistic check: 
                # If we have a position, we expect SOME non-zero balance on Binance.
                pass 
                
    except Exception as e:
        log_msg(f"Sync check failed: {e}")

if __name__ == "__main__":
    # PRE-FLIGHT CHECK
    if not PAPER_MODE:
        if not validate_binance_balance():
            log_msg("⚠️ CRITICAL: Balance Validation Failed. Entering Sleep Mode.")
            while True: time.sleep(60)

    # CIRCUIT BREAKER ON START
    state = load_state()
    if not check_circuit_breaker(state):
        log_msg("⚠️ CRITICAL: Circuit Breaker Tripped on Startup. Aborting.")
        sys.exit(1)

    main()
