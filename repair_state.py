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

    # 1. Remove Phantom LINK
    if 'chainlink' in state['echo']['positions']:
        print("Removing Phantom 'chainlink' position...")
        del state['echo']['positions']['chainlink']
    else:
        print("LINK not found in positions (?)")

    # 2. Reconcile Cash
    # Actual Binance Balance (USDC): 139.00
    # NIA Allowance: 45.0
    # Echo Correct Cash: 94.0
    
    print(f"Old Echo Cash: {state['echo']['cash']}")
    state['echo']['cash'] = 94.0
    print(f"New Echo Cash: {state['echo']['cash']}")

    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

    print("--- REPAIR COMPLETE ---")

if __name__ == "__main__":
    repair_state()
