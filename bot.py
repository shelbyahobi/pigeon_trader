import time
import requests
import json
from web3 import Web3
from datetime import datetime
import config

# --- SETUP ACCESS TO CONFIG ---
PAPER_MODE = config.PAPER_MODE
RPC_URL = config.BSC_RPC_URL
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# --- GLOBAL STATE ---
positions = {}  # {token_address: {'entry_price': float, 'amount': float, 'symbol': str, 'timestamp': float}}

# --- LOGGING SETUP ---
def log_trade(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    with open("trade_log.txt", "a") as f:
        f.write(log_entry + "\n")

# --- UTILS ---
def get_token_price(token_address):
    """
    Fetches price of a token in USD from DexScreener.
    """
    try:
        url = f"{config.DEXSCREENER_API_URL}{token_address}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get("pairs"):
            # Get the first pair (usually the most liquid one)
            pair = data["pairs"][0]
            price_usd = pair.get("priceUsd")
            return float(price_usd) if price_usd else None
    except Exception as e:
        print(f"Error fetching price for {token_address}: {e}")
    return None

def check_safety(token_address):
    """
    Checks if a token is a honeypot using Honeypot.is API.
    Returns: (is_safe, reason)
    """
    try:
        url = f"{config.HONEYPOT_API_URL}?address={token_address}&chainID=56"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Honeypot.is returns 'honeypotResult' key
        # If 'isHoneypot' is True, it's unsafe.
        if "honeypotResult" in data:
            result = data["honeypotResult"]
            if result.get("isHoneypot"):
                return False, "HONEYPOT DETECTED"
            else:
                return True, "SAFE"
        else:
            # If API fails or data is weird, assume unsafe to be cautious
            # Debug: print keys to see what happened
            return False, f"UNKNOWN/API ERROR. Data keys: {list(data.keys())}"
            
    except Exception as e:
        return False, f"CHECK FAILED: {e}"

# --- TRADING LOGIC ---
def buy_token(token_address, token_symbol="TOKEN"):
    """
    Simulates a buy in PAPER_MODE.
    """
    price = get_token_price(token_address)
    if not price:
        log_trade(f"FAILED TO BUY {token_address}: Could not fetch price.")
        return

    if PAPER_MODE:
        amount_bnb = config.TRADE_AMOUNT_BNB
        log_trade(f"[PAPER BUY] Bought {token_symbol} ({token_address}) at ${price} USD (Simulated Amount: {amount_bnb} BNB)")
        
        # Track position
        positions[token_address] = {
            'entry_price': price,
            'amount': amount_bnb,
            'symbol': token_symbol,
            'timestamp': time.time()
        }
        return price
    else:
        log_trade("REAL TRADE NOT IMPLEMENTED YET - SAFETY LOCK")

def monitor_positions():
    """
    Checks active positions for take-profit or stop-loss.
    """
    if not positions:
        return

    # Create a copy of keys to modify dict during iteration
    for token_address in list(positions.keys()):
        data = positions[token_address]
        current_price = get_token_price(token_address)
        
        if not current_price:
            continue

        entry_price = data['entry_price']
        symbol = data['symbol']
        
        # Calculate performance
        multiplier = current_price / entry_price
        
        # Take Profit: 2x (2.0) | Stop Loss: -20% (0.8)
        if multiplier >= 2.0:
            log_trade(f"[PAPER SELL] TAKE PROFIT: {symbol} at ${current_price} ({multiplier:.2f}x)")
            del positions[token_address]
        elif multiplier <= 0.8:
            log_trade(f"[PAPER SELL] STOP LOSS: {symbol} at ${current_price} ({multiplier:.2f}x)")
            del positions[token_address]
        # else:
        #     # Optional: Log status every now and then? warning: spammy
        #     pass

# --- MAIN SCANNER ---
def scan_and_trade():
    """
    Main loop to find new opportunites.
    For this demo, we will check a specific 'hot' list or just search for recently updated tokens 
    via DexScreener to simulate finding something 'new'.
    """
    log_trade("Bot started in scanning mode...")
    
    # In a real sniper, we might listen to Mempool or specific factory events.
    # For this simpler version, let's fetch 'latest' profiles or search for a generic term 
    # to find active tokens, OR just user can input a token to 'test' the safety check.
    
    # Let's simulate scanning by asking the user to input a token, 
    # OR we can just fetch some trending tokens to test the logic.
    
    # DEMO: Fetch some trending tokens from DexScreener to 'simulate' finding them
    # Updated Scanner with Filters
    while True:
        try:
            # User defined filters
            params = {
                "q": "WBNB", # Search for pairs with WBNB
                # Note: DexScreener search API is a bit limited, strict key=value filtering 
                # might need to happen post-fetch or via specific endpoint if documented.
                # However, the user provided a 'search' style URL pattern.
                # Let's try to construct a search query that implies some order if possible, 
                # but DexScreener /search/ mainly takes 'q'. 
                # We will fetch results and FILTER MANUALLY for liquidity/volume to be sure.
            }
            
            # Using the search endpoint to find WBNB pairs specifically
            url = f"{config.DEXSCREENER_SEARCH}WBNB"
            # Add a timestamp to avoid caching
            url += f"&ts={int(time.time())}"
            
            response = requests.get(url)
            data = response.json()
            
            if not data.get("pairs"):
                 log_trade("No tokens found in scan.")
                 time.sleep(10)
                 continue # Wait and retry

            pairs = data['pairs']
            log_trade(f"Found {len(pairs)} pairs. Filtering...")
            
            filtered_count = 0
            
            for pair in pairs:
                # 1. Platform/Chain Filter
                if pair.get('chainId') != 'bsc':
                    continue
                    
                # 2. Liquidity Filter (> $10k)
                liquidity = pair.get('liquidity', {}).get('usd', 0)
                if liquidity < 10000:
                    continue
                    
                # 3. Volume Filter (> $5k)
                volume = pair.get('volume', {}).get('h24', 0)
                if volume < 5000:
                    continue

                token_address = pair['baseToken']['address']
                token_symbol = pair['baseToken']['symbol']
                
                # Avoid re-buying if we already hold it
                if token_address in positions:
                    continue
                
                log_trade(f"Analyzing {token_symbol} ({token_address}) | Liq: ${liquidity} | Vol: ${volume}")
                
                # 4. Safety Check
                is_safe, reason = check_safety(token_address)
                if not is_safe:
                    # log_trade(f"SKIPPING {token_symbol}: {reason}") # Reduce spam
                    continue
                
                log_trade(f"SAFETY PASS: {token_symbol} is marked safe. Buying...")
                
                # 5. Buy (Paper)
                buy_token(token_address, token_symbol)
                filtered_count += 1
                
                # Limit to buying a few per scan loop to avoid blowing up limits
                if filtered_count >= 5:
                    break
                
                time.sleep(1)

            # Monitor positions after the scan
            log_trade(f"Scan complete. Monitoring {len(positions)} positions...")
            # Simple loop to monitor for a bit (e.g. 1 minute) before rescanning
            # in a real bot this would be async or a separate thread.
            # For this script, we'll just check once per main loop iteration.
            monitor_positions()
            
            time.sleep(60) # Wait 60s before next scan to mimic a regular interval

        except Exception as e:
            log_trade(f"Scan loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    if web3.is_connected():
        print("Connected to BSC Node!")
    else:
        print("Failed to connect to BSC Node.")
        
    scan_and_trade()
