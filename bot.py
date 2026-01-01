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
def buy_token(token_address):
    """
    Simulates a buy in PAPER_MODE.
    """
    price = get_token_price(token_address)
    if not price:
        log_trade(f"FAILED TO BUY {token_address}: Could not fetch price.")
        return

    if PAPER_MODE:
        amount_bnb = config.TRADE_AMOUNT_BNB
        log_trade(f"[PAPER BUY] Bought {token_address} at ${price} USD (Simulated Amount: {amount_bnb} BNB)")
        # In a real bot, you'd track this position to sell later.
        # For this simple scanner, we just log the opportunity.
        return price
    else:
        log_trade("REAL TRADE NOT IMPLEMENTED YET - SAFETY LOCK")

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
    try:
        # This endpoint fetches pairs. Use with a search query or just specific tokens for test.
        # Let's search for "PEPE" just to get some list of tokens to check safety on as a demo.
        # DEMO: Fetch WBNB pairs to guarantee we get BSC tokens for the test
        url = f"{config.DEXSCREENER_API_URL}{config.WBNB_ADDRESS}" 
        response = requests.get(url)
        data = response.json()
        
        if not data.get("pairs"):
             log_trade("No tokens found in scan.")
             return

        log_trade(f"Found {len(data['pairs'])} pairs. Scanning top 20 for BSC...")
        for i, pair in enumerate(data['pairs'][:20]):
            # Filter for BSC chain only
            if pair.get('chainId') != 'bsc':
                continue

            token_address = pair['baseToken']['address']
            token_symbol = pair['baseToken']['symbol']
            
            log_trade(f"Analyzing {token_symbol} ({token_address})...")
            
            # 1. Safety Check
            is_safe, reason = check_safety(token_address)
            if not is_safe:
                log_trade(f"SKIPPING {token_symbol}: {reason}")
                continue
            if not is_safe:
                log_trade(f"SKIPPING {token_symbol}: {reason}")
                continue
            
            log_trade(f"SAFETY PASS: {token_symbol} is marked safe.")
            
            # 2. Buy (Paper)
            buy_token(token_address)
            
            # Wait a bit between checks to not spam
            time.sleep(2)

    except Exception as e:
        log_trade(f"Scan loop error: {e}")

if __name__ == "__main__":
    if web3.is_connected():
        print("Connected to BSC Node!")
    else:
        print("Failed to connect to BSC Node.")
        
    scan_and_trade()
