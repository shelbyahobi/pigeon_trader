import json
import os

STATE_FILE = "strategic_state.json"

def repair_state():
    if not os.path.exists(STATE_FILE):
        print("State file not found!")
        return

    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    echo_pos = state['echo'].get('positions', {})
    
    print("--- CURRENT POSITIONS ---")
    print(list(echo_pos.keys()))

    # 1. AGGRESSIVE LINK DELETION
    # Delete anything that looks like Chainlink
    to_delete = []
    for pid in echo_pos.keys():
        if 'link' in pid.lower() or 'chainlink' in pid.lower():
            to_delete.append(pid)
            
    for pid in to_delete:
        print(f"👻 Deleting Phantom: {pid}")
        del state['echo']['positions'][pid]

    # 2. ENSURE UNI IS SAFE
    # Only adding if missing, preserving specific data if existing.
    # Actually, let's FORCE correct data just in case of drift.
    print("Refreshing UNI Position Data...")
    state['echo']['positions']['uniswap'] = {
        'amount': 1.26,
        'entry_price': 5.50, 
        'highest_price': 5.54, 
        'entry_timestamp': 1736450000 
    }

    # 3. FORCE CASH SYNC
    # You have $139.00 USDC.
    # $45 allocated to NIA.
    # Available for Echo = $94.00
    print(f"Correction Cash from ${state['echo']['cash']:.2f} -> $94.00")
    state['echo']['cash'] = 94.0
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

    print("--- REPAIR SUCCESSFUL ---")

if __name__ == "__main__":
    repair_state()
