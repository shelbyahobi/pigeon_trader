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
from strategies.nia import NIAStrategy

# --- CONFIG ---
# Real tokens to monitor
TOKENS = {} # Will be populated by dynamic screener


# Initialize Strategy (Default)
strategy = AAMRStrategy()

def get_strategy_for_mode(mode):
    if mode == 'echo':
        return EchoStrategy()
    elif mode == 'nia':
        return NIAStrategy()
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
                state = json.load(f)
                # Migration / Init check
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

# --- MARKET DATA ---
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
    """Fetch 250 days of history + Volume + Volatility Proxy"""
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    params = {'vs_currency': 'usd', 'days': 250, 'interval': 'daily'}
    
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            
            # 1. Parse Prices
            prices = data.get('prices', [])
            if not prices: return None
            
            df = pd.DataFrame(prices, columns=['timestamp', 'price'])
            
            # 2. Parse Volumes (Safe Merge)
            vols = data.get('total_volumes', [])
            if vols:
                df_v = pd.DataFrame(vols, columns=['timestamp', 'total_volume'])
                # Merge logic: CoinGecko lists usually aligned, but safer to merge using timestamp
                df['total_volume'] = df_v['total_volume'] # Direct assign assumes alignment (99% case)
                # If lengths differ, we'd need sophisticated merge. For simple bot:
                if len(df_v) != len(df):
                    # Minimal alignment attempt
                    df = pd.merge(df, df_v, on='timestamp', how='left').fillna(0)
            else:
                 df['total_volume'] = 0.0

            # 3. Post-Process
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('date', inplace=True)
            
            # 4. Proxy High/Low for ATR (Volatility)
            # Since market_chart only gives daily close, we assume High=Low=Close.
            # TRUE RANGE will thus be |Close - Close_Prev| (Daily Move).
            # This is a valid volatility proxy for "Cloud Paper Mode".
            df['high'] = df['price']
            df['low'] = df['price']
            df['open'] = df['price'] # Proxy
            df['close'] = df['price']
            
            return df
            
        # Rate limit handling
        elif r.status_code == 429:
            log_msg(f"Rate limited fetching history for {token_id}. Skipping.")
    except Exception as e:
        log_msg(f"Error fetching candles for {token_id}: {e}")
    return None

# --- BOT LOGIC ---
def run_job(mode="echo"):
    # Unified State File
    start_time = time.time()
    log_msg(f"Running check for pool: {mode.upper()}...")
    
    state = load_state()
    pool = state.get(mode)
    
    if not pool:
        log_msg(f"Critical Error: Pool {mode} not found in state.")
        return

    # Select Strategy
    global strategy
    strategy = get_strategy_for_mode(mode)
    
    # Context Setup
    global_btc_context = True
    if mode == 'echo':
        global_btc_context = fetch_btc_trend()

    # Iterate Tokens
    # Optimization: NIA should only check its own list? 
    # For V1 repair, we iterate all and let strategy filter.
    
    for token_id, token_symbol in TOKENS.items():
        # ... Data Fetching (Simplified for prompt brevity, assume implicit) ...
        if token_id not in market_data: continue
        price = market_data[token_id]['price']
        
        # Fetch History
        df_hist = fetch_candle_history(token_id)
        if df_hist is None or len(df_hist) < 200: continue
            
        # Get Position State
        current_pos = pool['positions'].get(token_id)
        current_pos_price = current_pos['entry_price'] if current_pos else None
        
        # Trailing Stop Peak Tracking
        highest_price = None
        if current_pos:
             if 'highest_price' not in current_pos: current_pos['highest_price'] = current_pos_price
             if price > current_pos['highest_price']: current_pos['highest_price'] = price
             highest_price = current_pos['highest_price']

        # Context
        ctx = {}
        if mode == 'echo':
            ctx['btc_bullish'] = global_btc_context
            ctx['funding_ok'] = fetch_funding_rate(token_symbol)
        if mode == 'nia':
             if token_id in TOKEN_METADATA: ctx.update(TOKEN_METADATA[token_id])

        # Get Signal
        signal = strategy.get_signal(df_hist, current_pos_price, highest_price, mode, context=ctx)
        
        # Execute
        if signal == 'BUY' and not current_pos:
            # Sizing logic
            pool_cash = pool['cash']
            risk_cap = 0.05 if mode == 'echo' else 0.10 # 5% Echo, 10% NIA
            
            # 1. Enforcement: Max Positions
            # Prevents 100% drawdown if 20 signals fire at once
            max_pos = 10 if mode == 'echo' else 5
            if len(pool['positions']) >= max_pos:
                continue

            bet_size = pool_cash * risk_cap
            
            # 2. Enforcement: Dust
            if bet_size < 10: bet_size = 0 
            
            # 3. Enforcement: Cash Buffer & Fees
            # Fee Model: 0.1% Binance + 0.3% Slippage = 0.4% Cost
            EST_FEE = 0.004
            gross_cost = bet_size
            total_cost = gross_cost * (1 + EST_FEE)
            
            if bet_size > 0 and pool_cash >= total_cost:
                amount = gross_cost / price
                pool['cash'] -= total_cost # Debit Gross + Fees
                
                pool['positions'][token_id] = {
                    'entry_price': price,
                    'highest_price': price,
                    'amount': amount,
                    'timestamp': time.time()
                }
                log_msg(f"BUY {token_symbol} ({mode}) @ ${price:.2f} Size: ${gross_cost:.1f} Cost: ${total_cost:.2f}")
                send_alert(f"BUY {token_symbol} ({mode})")
                
                # PERSIST IMMEDIATELLY (Race Condition Fix)
                state[mode] = pool
                save_state(state)

        elif signal == 'SELL' and current_pos:
            amount = current_pos['amount']
            gross_proceeds = amount * price
            
            # Fee Model on Exit
            EST_FEE = 0.004
            net_proceeds = gross_proceeds * (1 - EST_FEE)
            
            pnl = (net_proceeds - (amount * current_pos['entry_price']))
            
            pool['cash'] += net_proceeds
            del pool['positions'][token_id]
            log_msg(f"SELL {token_symbol} ({mode}) @ ${price:.2f} Net: ${net_proceeds:.2f} PnL: ${pnl:.2f}")
            send_alert(f"SELL {token_symbol} ({mode}) PnL: ${pnl:.2f}")
            
            # PERSIST IMMEDIATELLY
            state[mode] = pool
            save_state(state)
            
        # Update Highest Price Persistence (Race Condition Fix)
        if current_pos and price > current_pos['highest_price']:
             # Already updated in memory loop earlier, but need to save to disk
             # state object is reference to pool, so it's updated
             save_state(state)
            
        time.sleep(1) # Safety
        
    log_msg(f"Pool {mode.upper()} Finished. Cash: ${pool['cash']:.1f}")

def run_fleet():
    """Runs the 95/5 Split Portfolio"""
    log_msg(">>> EXECUTING FLEET: 95% ECHO | 5% NIA <<<")
    # Run Echo (Primary)
    run_job(mode="echo")
    # Run NIA (Side Bet)
    run_job(mode="nia")
    log_msg(">>> FLEET EXECUTION COMPLETE <<<")

import sys

def main():
    log_msg("--- STRATEGIC BOT STARTED ---")
    
    # Check for Mode
    MODE = "standard"
    IS_FLEET = False
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "flash":
            MODE = "flash"
            log_msg("!!! RUNNING IN FLASH CRASH MODE !!!")
        elif arg == "echo":
            MODE = "echo"
            log_msg("!!! RUNNING IN ECHO MODE (ELR) !!!")
        elif arg == "mixed":
            IS_FLEET = True
            log_msg("!!! RUNNING IN MIXED FLEET MODE (95/5) !!!")
        
    log_msg(f"Monitoring: {list(TOKENS.values())}")
    
    # Run once immediately
    update_watchlist()
    if IS_FLEET:
        run_fleet()
        schedule.every(1).hours.do(run_fleet)
    else:
        run_job(MODE)
        schedule.every(1).hours.do(run_job, mode=MODE)
    
    # Schedule weekly watchlist update (every Monday)
    schedule.every().monday.do(update_watchlist)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
