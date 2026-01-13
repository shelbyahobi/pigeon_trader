import json
import os
import sys
from binance.client import Client
from dotenv import load_dotenv

# Load Env
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_SECRET')

STATE_FILE = "strategic_state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, 'r') as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def add_funds():
    print("--- 💸 PIGEON TELLER MACHINE ---")
    
    # 1. Connect to Binance
    try:
        client = Client(API_KEY, API_SECRET)
        bal = client.get_asset_balance(asset='USDC')
        real_cash = float(bal['free'])
        print(f"🏦 Real Binance Balance: ${real_cash:.2f}")
    except Exception as e:
        print(f"❌ Error connecting to Binance: {e}")
        return

    # 2. Load Internal State
    state = load_state()
    if not state:
        print("❌ strategic_state.json not found!")
        return
    
    echo_cash = state['echo']['cash']
    nia_cash = state['nia']['cash']
    bot_cash = echo_cash + nia_cash
    
    print(f"🤖 Bot Internal Cash:   ${bot_cash:.2f} (Echo: ${echo_cash:.2f} | NIA: ${nia_cash:.2f})")
    
    # 3. Calculate Surplus
    surplus = real_cash - bot_cash
    
    if surplus < 1.0:
        print(f"\n🤷 No significant surplus found (Diff: ${surplus:.2f}).")
        print("   (Deposit funds to Binance first, then run this script).")
        return
    
    print(f"\n💰 FRESH CAPITAL DETECTED: ${surplus:.2f}")
    
    # 4. Allocation Interface
    print("\nHow would you like to allocate these funds?")
    print("1. 50/50 Split (Balanced)")
    print("2. 100% to Echo (Types 'safe')")
    print("3. 100% to NIA (Type 'risk')")
    
    choice = input("\nEnter choice [1/2/3]: ").strip()
    
    alloc_echo = 0.0
    alloc_nia = 0.0
    
    if choice == '1':
        alloc_echo = surplus * 0.5
        alloc_nia = surplus * 0.5
    elif choice == '2':
        alloc_echo = surplus
    elif choice == '3':
        alloc_nia = surplus
    else:
        print("❌ Invalid choice. Aborting.")
        return
        
    # 5. Execute
    print(f"\nUpdating Ledger...")
    state['echo']['cash'] += alloc_echo
    state['nia']['cash'] += alloc_nia
    
    save_state(state)
    
    print(f"✅ SUCCESS! Funds Added.")
    print(f"   New Echo Cash: ${state['echo']['cash']:.2f}")
    print(f"   New NIA Cash:  ${state['nia']['cash']:.2f}")
    print("\nThe bot will use these funds on the next hourly run.")

if __name__ == "__main__":
    add_funds()
