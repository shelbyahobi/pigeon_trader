import json
import os

STATE_FILE = "strategic_state.json"

def repair_state():
    if not os.path.exists(STATE_FILE):
        print("State file not found!")
        return

    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    print("--- BEFORE REPAIR ---")
    print(json.dumps(state['echo'], indent=2))

    # 1. FIX UNI (Zombie Position)
    # User has 1.26 UNI in wallet, but bot deleted it.
    print("Resurrecting UNI Position...")
    state['echo']['positions']['uniswap'] = {
        'amount': 1.26,
        'entry_price': 5.50, # Approximate recent price
        'highest_price': 5.54, # Restore previous high
        'entry_timestamp': 1736450000 # Approximate timestamp (Jan 9)
    }

    # 2. FIX LINK (Already Sold)
    if 'chainlink' in state['echo']['positions']:
        print("Removing Phantom 'chainlink' position...")
        del state['echo']['positions']['chainlink']

    # 3. RECONCILE CASH
    # Total USDC in Wallet: 139.00
    # Allowed for NIA: 45.0
    # Left for Echo: 94.0
    state['echo']['cash'] = 94.0
    
    print("--- AFTER REPAIR ---")
    print(json.dumps(state['echo'], indent=2))

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

    print("--- REPAIR COMPLETE ---")

if __name__ == "__main__":
    repair_state()
