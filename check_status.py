import json
import os
from datetime import datetime

STATE_FILE = "strategic_state.json"

def check_status():
    if not os.path.exists(STATE_FILE):
        print("❌ State file not found!")
        return

    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            
        print("\n=== 🦅 PIGEON TRADER STATUS ===")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # ECHO
        echo = state.get('echo', {})
        print(f"\n🔵 ECHO POOL (Safe)")
        print(f"   Cash: ${echo.get('cash', 0):.2f}")
        positions = echo.get('positions', {})
        if positions:
            for sym, data in positions.items():
                print(f"   - {sym.upper()}: {data['amount']:.4f} units @ ${data['entry_price']:.2f} (High: ${data.get('highest_price', 0):.2f})")
        else:
            print("   (No Positions)")
            
        # NIA
        nia = state.get('nia', {})
        print(f"\n🔴 NIA POOL (Risky)")
        print(f"   Cash: ${nia.get('cash', 0):.2f}")
        positions = nia.get('positions', {})
        if positions:
            for sym, data in positions.items():
                print(f"   - {sym.upper()}: {data['amount']:.4f} units @ ${data['entry_price']:.2f}")
        else:
            print("   (No Positions)")
            
        print("\n===============================\n")
        
    except Exception as e:
        print(f"Error reading state: {e}")

if __name__ == "__main__":
    check_status()
