import json
import os

STATE_FILE = "strategic_state.json"

def repair_state():
    if not os.path.exists(STATE_FILE):
        print("State file not found!")
        return

    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    # 1. SYNC UNI (1.26)
    print("Syncing UNI Position...")
    state['echo']['positions']['uniswap'] = {
        'amount': 1.26,
        'entry_price': 5.50,
        'highest_price': 5.57,
        'entry_timestamp': 1736450000
    }

    # 2. SYNC LINK (0.98) - It bought back!
    # If the key is 'chainlink', update it. If 'link', update it.
    # We want ONE entry key "chainlink" (CoinGecko ID).
    print("Syncing LINK Position...")
    # Remove duplicates if any
    if 'link' in state['echo']['positions']: del state['echo']['positions']['link']
    
    state['echo']['positions']['chainlink'] = {
        'amount': 0.98,
        'entry_price': 13.17, # From recent buy log
        'highest_price': 13.49, # From screenshot/recent high
        'entry_timestamp': 1736670000 # Today
    }

    # 3. SYNC CASH
    # Wallet USDC: 126.09
    # NIA Allowance: 45.0
    # Available for Echo: 81.09
    print(f"Syncing Echo Cash to $81.09")
    state['echo']['cash'] = 81.09
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

    print("--- REALITY SYNC COMPLETE ---")

if __name__ == "__main__":
    repair_state()
