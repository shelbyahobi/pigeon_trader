import json
import os
import time

def check_watchlist():
    if not os.path.exists("watchlist.json"):
        print("❌ watchlist.json not found! (Bot hasn't run fully yet?)")
        return

    mtime = os.path.getmtime("watchlist.json")
    ago = time.time() - mtime
    print(f"Watchlist (Updated {int(ago/60)}m ago):")
    
    with open("watchlist.json", "r") as f:
        data = json.load(f)
        
    print(f"{'SYMBOL':<10} {'TIER':<12} {'ACT':<6} {'STATUS'}")
    print("-" * 50)
    
    for c in data:
        symbol = c['symbol'].upper()
        tier = c.get('tier', 'n/a')
        
        # Determine likely pool (Echo/NIA) based on flags
        # This mirrors Screener logic logic but simplified for display
        is_flash = c.get('is_flash_crash', False)
        age = c.get('age_years', 0)
        
        # Inferred Type
        if is_flash:
            act = "NIA⚡"
            note = "FLASH CRASH"
        elif age < 2.0 and tier in ['small', 'lower_mid']:
            act = "NIA👶"
            note = "YoungSpec"
        else:
            act = "ECHO🛡️"
            note = f"Age {age:.1f}y"
            
        print(f"{symbol:<10} {tier:<12} {act:<6} {note}")
        
    print("-" * 50)
    print(f"Total Candidates: {len(data)}")

if __name__ == "__main__":
    check_watchlist()
