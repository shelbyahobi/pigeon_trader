import json
import os
import time
import subprocess
from datetime import datetime

STATE_FILE = "strategic_state.json"
LOG_FILE = "bot.log"

def get_process_status():
    try:
        # Check if strategic_bot.py is running
        res = subprocess.check_output(["pgrep", "-f", "strategic_bot.py"])
        return True, res.decode().strip().replace('\n', ', ')
    except:
        return False, None

def get_log_freshness():
    if not os.path.exists(LOG_FILE):
        return "Missing"
    
    mtime = os.path.getmtime(LOG_FILE)
    ago = time.time() - mtime
    
    if ago < 120: return f"🟢 Active ({int(ago)}s ago)"
    if ago < 600: return f"🟡 Slow ({int(ago)}s ago)"
    return f"🔴 STALLED ({int(ago/60)}m ago)"

def check_status():
    print("\n=== 🦅 PIGEON TRADER HEALTH CHECK ===")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. SYSTEM HEALTH
    is_running, pids = get_process_status()
    log_status = get_log_freshness()
    
    print("\n[SYSTEM]")
    print(f"   Status: {'✅ RUNNING' if is_running else '❌ STOPPED'}")
    if pids: print(f"   PID(s): {pids}")
    print(f"   Logs:   {log_status}")

    # 2. STRATEGY HEALTH
    if not os.path.exists(STATE_FILE):
        print("❌ State file not found!")
        return

    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            
        total_equity = 0
        total_cash = 0
        
        # ECHO
        echo = state.get('echo', {})
        print(f"\n[ECHO POOL] (Safe Core)")
        print(f"   Cash:      ${echo.get('cash', 0):.2f}")
        total_cash += echo.get('cash', 0)
        
        positions = echo.get('positions', {})
        pos_val = 0
        if positions:
            for sym, data in positions.items():
                amt = data['amount']
                entry = data['entry_price']
                curr_val = amt * entry # Approx
                pos_val += curr_val
                print(f"   - {sym.upper():<6} {amt:<8.4f} units @ ${entry:<6.2f} (Est: ${curr_val:.2f})")
        else:
            print("   (No Positions)")
        
        total_equity += (echo.get('cash', 0) + pos_val)

        # NIA
        nia = state.get('nia', {})
        print(f"\n[NIA POOL] (Alpha Hunter)")
        print(f"   Cash:      ${nia.get('cash', 0):.2f}")
        total_cash += nia.get('cash', 0)
        
        positions = nia.get('positions', {})
        pos_val = 0
        if positions:
            for sym, data in positions.items():
                amt = data['amount']
                entry = data['entry_price']
                curr_val = amt * entry 
                pos_val += curr_val
                print(f"   - {sym.upper():<6} {amt:<8.4f} units @ ${entry:<6.2f} (Est: ${curr_val:.2f})")
        else:
            print("   (No Positions)")
            
        total_equity += (nia.get('cash', 0) + pos_val)

        # 3. SCALING ADVICE
        print("\n[SCALING ADVICE]")
        print(f"   Total Equity: ${total_equity:.2f}")
        cash_ratio = total_cash / total_equity if total_equity > 0 else 0
        print(f"   Cash Reserve: {cash_ratio:.1%}")
        
        if not is_running:
             print("   ⚠️  BOT STOPPED. Restart before adding funds.")
        elif cash_ratio < 0.20:
             print("   🟢  AGGRESSIVE: Cash low (<20%). Safe to add funds to capture more opportunities.")
        elif cash_ratio > 0.80:
             print("   🟡  PASSIVE: High cash reserves. Wait for bot to deploy capital before adding more.")
        else:
             print("   🔵  BALANCED: Portfolio is healthy. Add funds if you want to scale up position sizes.")

        print("\n===================================\n")
        
    except Exception as e:
        print(f"Error reading state: {e}")

if __name__ == "__main__":
    check_status()
