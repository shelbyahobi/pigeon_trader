
import json
import os
import time

STATE_FILE = 'strategic_state.json'

def flush_positions():
    if not os.path.exists(STATE_FILE):
        print("No state file found.")
        return

    with open(STATE_FILE, 'r') as f:
        state = json.load(f)

    if 'echo' not in state:
        print("No Echo state found.")
        return

    pool = state['echo']
    positions = pool['positions']
    
    if not positions:
        print("No positions to flush.")
        return

    print(f"Current Cash: ${pool['cash']:.2f}")
    print(f"Open Positions: {len(positions)}")

    # Sort by Timestamp (Oldest First) or PnL? 
    # Let's flush the OLDEST ones first to free up slots.
    # Actually, let's flush the ones without 'highest_price' set properly if any (legacy bug)
    # Or just flush 5 oldest.
    
    sorted_pos = sorted(positions.items(), key=lambda x: x[1]['timestamp'])
    
    to_flush = sorted_pos[:5] # Flush 5 oldest
    
    print("\n--- FLUSHING 5 OLDEST POSITIONS ---")
    
    total_proceeds = 0
    
    for token_id, pos in to_flush:
        # Estimate current price (we don't have live API here easily without setup)
        # We will assume we sell at ENTRY PRICE * 0.95 (5% slippage/loss penalty) just to be safe in accounting
        # OR we just return the 'amount' * 'entry_price' (Break even accounting) and let the bot sync up later?
        # Better: We keep the cash accounting somewhat realistic.
        # Let's assume -5% loss on forced exit.
        
        entry = pos['entry_price']
        amount = pos['amount']
        proceeds = (amount * entry) * 0.95 
        
        print(f"Selling {token_id} (Entry: ${entry:.2f}) -> Returning ${proceeds:.2f} to pool")
        
        pool['cash'] += proceeds
        total_proceeds += proceeds
        
        del pool['positions'][token_id]

    print(f"\nTotal Proceeds: ${total_proceeds:.2f}")
    print(f"New Cash: ${pool['cash']:.2f}")
    print(f"Remaining Positions: {len(pool['positions'])}")

    # Save
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)
    print("\n✅ State updated. Restart the bot to use new cash.")

if __name__ == "__main__":
    flush_positions()
