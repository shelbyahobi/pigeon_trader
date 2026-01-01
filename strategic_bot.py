import time
import schedule
import requests
import json
import os
from datetime import datetime
import config

# --- CONFIG ---
# Real tokens to monitor
TOKENS = {
    'pancakeswap-token': 'CAKE',
    'alpaca-finance': 'ALPACA',
    'binancecoin': 'BNB'
}

# Strategy Settings
DIP_THRESHOLD = 0.50 # Buy if Price < 50% of ATH
TAKE_PROFIT = 0.20   # Sell if Price > +20% from Entry
STOP_LOSS = 0.20     # Sell if Price < -20% from Entry

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

# --- BOT LOGIC ---
def run_job():
    log_msg("Running scheduled check...")
    
    state = load_state()
    # Ensure structure: state = {'positions': {token_id: {entry_price, amount}}, 'cash': 1000}
    if 'cash' not in state: state['cash'] = 1000.0 # Paper money
    if 'positions' not in state: state['positions'] = {}
    
    market_data = fetch_market_data(list(TOKENS.keys()))
    if not market_data:
        return

    for token_id, token_symbol in TOKENS.items():
        if token_id not in market_data:
            continue
            
        data = market_data[token_id]
        price = data['price']
        ath = data['ath']
        
        # 1. Manage Active Position
        if token_id in state['positions']:
            pos = state['positions'][token_id]
            entry_price = pos['entry_price']
            amount = pos['amount']
            
            pnl_pct = (price - entry_price) / entry_price
            
            # Check Exit Conditions
            if pnl_pct >= TAKE_PROFIT:
                # TAKE PROFIT
                proceeds = amount * price
                profit = proceeds - (amount * entry_price)
                state['cash'] += proceeds
                del state['positions'][token_id]
                
                msg = f"SOLD {token_symbol} (TP). Entry: ${entry_price:.2f}, Exit: ${price:.2f} (+{pnl_pct*100:.1f}%). Cash: ${state['cash']:.2f}"
                send_alert(msg)
                
            elif pnl_pct <= -STOP_LOSS:
                # STOP LOSS
                proceeds = amount * price
                loss = (amount * entry_price) - proceeds
                state['cash'] += proceeds
                del state['positions'][token_id]
                
                msg = f"SOLD {token_symbol} (SL). Entry: ${entry_price:.2f}, Exit: ${price:.2f} ({pnl_pct*100:.1f}%). Cash: ${state['cash']:.2f}"
                send_alert(msg)
                
            # else: Hold

        # 2. Look for New Entry (if no position)
        else:
            # Check Dip Buy Condition: Price < 50% of ATH
            if price < (ath * DIP_THRESHOLD):
                # Valid setup
                
                # Check if we have cash (Paper Logic: Invest fixed $100 per trade)
                bet_size = 100.0
                if state['cash'] >= bet_size:
                    amount_to_buy = bet_size / price
                    state['cash'] -= bet_size
                    state['positions'][token_id] = {
                        'entry_price': price,
                        'amount': amount_to_buy,
                        'timestamp': time.time()
                    }
                    
                    msg = f"BOUGHT {token_symbol} (Dip). Price: ${price:.2f} (ATH: ${ath:.2f}). Invested: ${bet_size}"
                    send_alert(msg)
                else:
                    # Not enough cash, maybe log once in a while
                    pass

    save_state(state)
    log_msg("Check complete.")

def main():
    log_msg("--- STRATEGIC BOT STARTED ---")
    log_msg(f"Monitoring: {list(TOKENS.values())}")
    log_msg(f"Strategies: Dip Buy (<{DIP_THRESHOLD*100}% ATH), TP (+{TAKE_PROFIT*100}%), SL (-{STOP_LOSS*100}%)")
    
    # Run once immediately
    run_job()
    
    # Schedule every 15 minutes
    schedule.every(15).minutes.do(run_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
