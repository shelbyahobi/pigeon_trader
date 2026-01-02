import time
import schedule
import requests
import json
import os
from datetime import datetime
import pandas as pd
import config
import screener
import gc
from strategies.aamr import AAMRStrategy
from strategies.echo import EchoStrategy

# --- CONFIG ---
# Real tokens to monitor
TOKENS = {} # Will be populated by dynamic screener


# Initialize Strategy (Default)
strategy = AAMRStrategy()

def get_strategy_for_mode(mode):
    if mode == 'echo':
        return EchoStrategy()
    return AAMRStrategy()

# --- LOGGING & ALERTING ---

STATE_FILE = "strategic_state.json"

LOG_FILE = "strategic_log.txt"

# --- LOGGING & ALERTING ---
def log_msg(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def send_alert(msg):
    # Placeholder for Telegram alert
    log_msg(f"*** ALERT: {msg} ***")

# --- STATE MANAGEMENT ---
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

# --- MARKET DATA ---
def fetch_market_data(token_ids):
    """
    Fetches current price and ATH for list of tokens.
    """
    ids_str = ",".join(token_ids)
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        'vs_currency': 'usd',
        'ids': ids_str
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Convert list to dict keyed by ID
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
        log_msg(f"Error fetching data: {e}")
        return None

def fetch_candle_history(token_id):
    """Fetch 250 days of history for AAMR Strategy"""
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    params = {'vs_currency': 'usd', 'days': 250, 'interval': 'daily'}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('date', inplace=True)
            return df
        # Rate limit handling
        elif r.status_code == 429:
            log_msg(f"Rate limited fetching history for {token_id}. Skipping.")
    except Exception as e:
        log_msg(f"Error fetching candles for {token_id}: {e}")
    return None

# --- WATCHLIST MANAGEMENT ---

# --- WATCHLIST MANAGEMENT ---
def update_watchlist():
    log_msg("Updating watchlist via Screener...")
    candidates = screener.screen_candidates() # Returns list of dicts
    
    new_tokens = {}
    for c in candidates:
        new_tokens[c['id']] = c['symbol']
        
    global TOKENS
    TOKENS = new_tokens
    log_msg(f"Watchlist updated: {len(TOKENS)} tokens. {list(TOKENS.values())}")

# --- RISK MANAGEMENT ---
def calculate_kelly_bet(cash, win_prob=0.55, win_loss_ratio=1.5, max_risk_pct=0.20):
    """
    Calculates bet size using Half-Kelly Criterion.
    f* = (bp - q) / b
    b = win/loss ratio
    p = probability of winning
    q = probability of losing (1-p)
    """
    if cash < 10: return 0.0
    
    # Kelly Formula
    q = 1.0 - win_prob
    f_star = ((win_loss_ratio * win_prob) - q) / win_loss_ratio
    
    # Safety: Use Half-Kelly (Crypto is volatile)
    safe_f = f_star * 0.5
    
    # Safety: Hard Cap at 20% of portfolio
    final_pct = min(max(safe_f, 0.0), max_risk_pct)
    
    bet_amount = cash * final_pct
    
    # Floor: Don't bet less than $10 (dust)
    if bet_amount < 10.0: bet_amount = 10.0
    
    return bet_amount

# --- CONTEXT DATA (Expert Hardening) ---
def fetch_btc_trend():
    """Returns True if BTC > 21-Week EMA (Bull Regime)"""
    try:
        # Fetch 150 days of BTC (approx 21 weeks)
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {'vs_currency': 'usd', 'days': 160, 'interval': 'daily'}
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            prices = [p[1] for p in data['prices']]
            if len(prices) < 147: return True # Default to permissible if data fail
            
            # Calculate 21-Week EMA (approx 147 days)
            # EMA_today = (Price * k) + (EMA_yesterday * (1-k))
            # Pandas is heavy, let's use SMA as close proxy for speed or simple pandas
            s = pd.Series(prices)
            ema_21w = s.ewm(span=147, adjust=False).mean().iloc[-1]
            current = prices[-1]
            
            log_msg(f"BTC Context: ${current:.0f} vs 21wEMA ${ema_21w:.0f} -> {'BULL' if current > ema_21w else 'BEAR'}")
            return current > ema_21w
    except Exception as e:
        log_msg(f"Error fetching BTC trend: {e}")
    return True # Default permisssive

def fetch_funding_rate(symbol):
    """Returns True if Funding is Negative or Neutral (Not Overheated)"""
    # Map Symbol to Binance Ticker (e.g. PEPE -> 1000PEPEUSDT or PEPEUSDT)
    # This is tricky without a mapping.
    # We will try standard 'SYMBOL'+'USDT'
    try:
        binance_symbol = f"{symbol.upper()}USDT"
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {'symbol': binance_symbol}
        r = requests.get(url, params=params, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            # If symbol invalid, it returns error code usually
            if 'lastFundingRate' in data:
                fr = float(data['lastFundingRate'])
                # Expert Rule: Funding < 0.01% (Neutral/Negative)
                # If > 0.01% -> Retail FOMO -> Danger
                is_safe = fr < 0.0001
                log_msg(f"Funding Context {binance_symbol}: {fr:.6f} -> {'SAFE' if is_safe else 'DANGER'}")
                return is_safe
    except:
        pass # Many coins don't have perps
    return True # Default permissive



# --- BOT LOGIC ---
def run_job(mode="standard"):
    # Separate state files for A/B testing
    global STATE_FILE
    STATE_FILE = f"strategic_state_{mode}.json"
    
    log_msg(f"Running scheduled check ({mode}) using {STATE_FILE}...")
    
    state = load_state()
    # Ensure structure: state = {'positions': {token_id: {entry_price, amount}}, 'cash': 1000}

    if 'cash' not in state: state['cash'] = 1000.0 # Paper money
    if 'positions' not in state: state['positions'] = {}
    
    if not market_data:
        return

    # Select Strategy Class based on Mode
    global strategy
    strategy = get_strategy_for_mode(mode)

    # Process each token
    global_btc_context = True # Default
    if mode == 'echo':
        global_btc_context = fetch_btc_trend()

    for token_id, token_symbol in TOKENS.items():
        if token_id not in market_data: continue
            
        price = market_data[token_id]['price']
        
        # 1. Fetch History (Expensive call - do carefully)
        # We need this for AAMR signals
        df_hist = fetch_candle_history(token_id)
        if df_hist is None or len(df_hist) < 200:
            continue
            
        # 2. Get AAMR Signal
        current_pos_price = None
        highest_price = None

        if token_id in state['positions']:
            pos = state['positions'][token_id]
            current_pos_price = pos['entry_price']
            
            # --- TRAILING STOP STATE UPDATE ---
            # Initialize highest_price if missing
            if 'highest_price' not in pos:
                pos['highest_price'] = current_pos_price
            
            # Update peak if price went up
            if price > pos['highest_price']:
                pos['highest_price'] = price
                
            highest_price = pos['highest_price']
            
        # Prepare Context (Only needed for Echo usually, but safe to gather)
        ctx = {}
        if mode == 'echo':
            # Check Global Regime once per loop? No, inside loop for now is fine but inefficient.
            # Optimization: Move BTC check outside loop? Yes.
            ctx['btc_bullish'] = global_btc_context
            ctx['funding_ok'] = fetch_funding_rate(token_symbol)
            
        signal = strategy.get_signal(df_hist, current_pos_price, highest_price, mode, context=ctx)
        
        # 3. Execute
        if signal == 'BUY' and token_id not in state['positions']:
            # BUY LOGIC
            # Use Kelly Criterion for sizing
            # EXPERT SAFETY: Cap risk based on mode
            risk_cap = 0.12 # Standard (12%)
            if mode == 'flash':
                risk_cap = 0.06 # Flash (6% - High Risk Strategy)
            elif mode == 'echo':
                risk_cap = 0.03 # Echo (3% - Hardened Expert Safety)
            if mode == 'flash':
                risk_cap = 0.06 # Flash (6% - High Risk Strategy)
            elif mode == 'echo':
                risk_cap = 0.05 # Echo (5% - Expert Requirement)
                
            bet_size = calculate_kelly_bet(state['cash'], max_risk_pct=risk_cap)
            
            if state['cash'] >= bet_size:
                amount = bet_size / price
                state['cash'] -= bet_size
                state['positions'][token_id] = {
                    'entry_price': price,
                    'highest_price': price, # Init peak
                    'amount': amount,
                    'timestamp': time.time()
                }
                send_alert(f"BUY {token_symbol} ({mode.upper()}) at ${price:.2f} | Size: ${bet_size:.1f}")

        elif signal == 'SELL' and token_id in state['positions']:
            # SELL LOGIC
            pos = state['positions'][token_id]
            proceeds = pos['amount'] * price
            pnl_pct = (price - pos['entry_price']) / pos['entry_price']
            
            state['cash'] += proceeds
            del state['positions'][token_id]
            send_alert(f"SELL {token_symbol} at ${price:.2f} ({pnl_pct*100:.1f}%). Cash: ${state['cash']:.2f}")
            
        # Rate limit safety & Memory Check
        time.sleep(2)
        gc.collect()
        
    save_state(state)
    save_state(state)
    log_msg("Check complete.")

import sys

def main():
    log_msg("--- STRATEGIC BOT STARTED ---")
    
    # Check for Flash Crash Mode
    MODE = "standard"
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "flash":
            MODE = "flash"
            log_msg("!!! RUNNING IN FLASH CRASH MODE !!!")
        elif arg == "echo":
            MODE = "echo"
            log_msg("!!! RUNNING IN ECHO MODE (ELR) !!!")
        
    log_msg(f"Monitoring: {list(TOKENS.values())}")
    log_msg(f"Strategy: AAMR (Adaptive Mean Reversion)")
    
    # Run once immediately
    update_watchlist()
    run_job(MODE)
    
    # Schedule every hour (AAMR uses daily/hourly trends, frequent checks not needed)
    schedule.every(1).hours.do(run_job, mode=MODE)
    # Schedule weekly watchlist update (every Monday)
    schedule.every().monday.do(update_watchlist)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
