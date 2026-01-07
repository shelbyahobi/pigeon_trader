#!/usr/bin/env python3
"""
Pre-deployment verification script.
Supports --local flag for testing without Binance API connection.
"""

import os
import json
import sys
from dotenv import load_dotenv

def verify_local_only():
    """
    Run checks that don't require Binance API connection.
    Safe to run from anywhere.
    """
    print("="*70)
    print("LOCAL PRE-FLIGHT CHECKS (No API Connection)")
    print("="*70)
    
    errors = []
    warnings = []
    
    # Check 1: .env exists
    print("\n[1/6] Checking .env file...")
    if not os.path.exists('.env'):
        errors.append(".env file not found")
    else:
        load_dotenv('.env')
        api_key = os.getenv('BINANCE_API_KEY')
        secret = os.getenv('BINANCE_SECRET')
        
        if not api_key or not secret:
            errors.append("API credentials not in .env")
        else:
            print("✅ .env file exists with credentials")
            print(f"   API Key: {len(api_key)} characters")
            print(f"   Secret: {len(secret)} characters")
    
    # Check 2: .env not in git
    print("\n[2/6] Checking git tracking...")
    # Windows/PowerShell compatible check
    if os.path.exists('.git'):
        if os.system("git ls-files --error-unmatch .env >nul 2>&1") == 0:
            errors.append(".env IS TRACKED BY GIT - CRITICAL SECURITY RISK!")
        else:
            print("✅ .env is not tracked by git")
    else:
        print("✅ Git not initialized (Skipping git check)")

    # Check 3: .gitignore has .env
    print("\n[3/6] Checking .gitignore...")
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            if '.env' in f.read():
                print("✅ .env is in .gitignore")
            else:
                warnings.append(".env not found in .gitignore")
    else:
        warnings.append(".gitignore file not found")
    
    # Check 4: PAPER_MODE setting
    print("\n[4/6] Checking PAPER_MODE...")
    if not os.path.exists('config.py'):
        errors.append("config.py not found")
    else:
        with open('config.py', 'r') as f:
            config_content = f.read()
            if 'PAPER_MODE = True' in config_content:
                errors.append("PAPER_MODE is still True - must be False for live trading")
            elif 'PAPER_MODE = False' in config_content:
                print("✅ PAPER_MODE is False (live mode)")
            else:
                warnings.append("PAPER_MODE setting not found in config.py")
    
    # Check 5: State file validation
    print("\n[5/6] Checking strategic_state.json...")
    if not os.path.exists('strategic_state.json'):
        errors.append("strategic_state.json not found")
    else:
        try:
            with open('strategic_state.json', 'r') as f:
                state = json.load(f)
            
            # Validate structure
            if 'echo' not in state or 'nia' not in state:
                errors.append("State file missing 'echo' or 'nia' pools")
            else:
                echo_cash = state['echo'].get('cash', 0)
                nia_cash = state['nia'].get('cash', 0)
                echo_positions = len(state['echo'].get('positions', {}))
                nia_positions = len(state['nia'].get('positions', {}))
                total_positions = echo_positions + nia_positions
                
                print(f"✅ State file valid")
                print(f"   Echo: ${echo_cash:.2f} cash, {echo_positions} positions")
                print(f"   NIA:  ${nia_cash:.2f} cash, {nia_positions} positions")
                print(f"   Total capital allocated: ${echo_cash + nia_cash:.2f}")
                
                if total_positions > 0:
                    warnings.append(f"State has {total_positions} positions - should be 0 for clean start")
                
                # Check allocation ratios
                if echo_cash + nia_cash > 0:
                    echo_pct = (echo_cash / (echo_cash + nia_cash)) * 100
                    nia_pct = (nia_cash / (echo_cash + nia_cash)) * 100
                    print(f"   Allocation: Echo {echo_pct:.0f}% / NIA {nia_pct:.0f}%")
                    
                    if abs(echo_pct - 70) > 5:
                        warnings.append(f"Echo allocation ({echo_pct:.0f}%) not standard 70%")
        
        except json.JSONDecodeError:
            errors.append("State file is not valid JSON")
        except Exception as e:
            errors.append(f"Error reading state file: {e}")
    
    # Check 6: Bot file exists
    print("\n[6/6] Checking strategic_bot.py...")
    if not os.path.exists('strategic_bot.py'):
        errors.append("strategic_bot.py not found")
    else:
        print("✅ strategic_bot.py exists")
        
        # Check for enhancements
        with open('strategic_bot.py', 'r', encoding='utf-8') as f:
            bot_content = f.read()
            
            enhancements = {
                'validate_binance_balance': 'validate_binance_balance' in bot_content,
                'check_circuit_breaker': 'check_circuit_breaker' in bot_content,
                'verify_position_sync': 'verify_position_sync' in bot_content,
            }
            
            print("   Safety enhancements:")
            for name, present in enhancements.items():
                status = "✅" if present else "❌"
                print(f"   {status} {name}")
                if not present:
                    warnings.append(f"Missing enhancement: {name}")
    
    # Summary
    print("\n" + "="*70)
    print("LOCAL VERIFICATION SUMMARY")
    print("="*70)
    
    if errors:
        print("\n❌ ERRORS (Must fix before deployment):")
        for i, err in enumerate(errors, 1):
            print(f"   {i}. {err}")
    
    if warnings:
        print("\n⚠️  WARNINGS (Review recommended):")
        for i, warn in enumerate(warnings, 1):
            print(f"   {i}. {warn}")
    
    if not errors and not warnings:
        print("✅ ALL LOCAL CHECKS PASSED")
    elif not errors:
        print("✅ No critical errors found")
    
    print("\n📌 NEXT STEP: Upload to VPS and run with --vps flag")
    print("="*70)
    
    return len(errors) == 0


def verify_vps():
    """
    Run checks that require Binance API connection.
    Only works on whitelisted IP (VPS).
    """
    print("="*70)
    print("VPS DEPLOYMENT CHECKS (With API Connection)")
    print("="*70)
    
    errors = []
    warnings = []
    
    # First run local checks
    print("\n[PHASE 1] Running local checks first...\n")
    if not verify_local_only():
        print("\n❌ Local checks failed. Fix errors before testing connection.")
        return False
    
    # Now test API connection
    print("\n" + "="*70)
    print("[PHASE 2] Testing Binance API Connection")
    print("="*70)
    
    try:
        from binance.client import Client
        load_dotenv('.env')
        
        print("\n[1/4] Initializing Binance client...")
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
        print("✅ Client initialized")
        
        print("\n[2/4] Testing connection...")
        account = client.get_account()
        print("✅ Connection successful")
        print(f"   Account type: {account.get('accountType', 'UNKNOWN')}")
        
        print("\n[3/4] Checking API permissions...")
        perms = client.get_account_api_permissions()
        
        spot_enabled = perms.get('enableSpotAndMarginTrading', False)
        withdrawals_enabled = perms.get('enableWithdrawals', True)
        ip_restricted = perms.get('ipRestrict', False)
        
        print(f"   Spot Trading: {'✅ Enabled' if spot_enabled else '❌ Disabled'}")
        print(f"   Withdrawals: {'🚨 ENABLED (FIX!)' if withdrawals_enabled else '✅ DISABLED'}")
        print(f"   IP Restriction: {'✅ Enabled' if ip_restricted else '⚠️  Disabled'}")
        
        if withdrawals_enabled:
            errors.append("API key has WITHDRAWALS ENABLED - CRITICAL SECURITY RISK!")
        
        if not spot_enabled:
            errors.append("Spot trading not enabled on API key")
        
        if not ip_restricted:
            warnings.append("IP restriction not enabled - consider enabling for security")
        
        print("\n[4/4] Checking USDT balance...")
        usdt = client.get_asset_balance(asset='USDT')
        balance = float(usdt['free'])
        print(f"✅ Balance check successful: ${balance:.2f} USDT")
        
        # Load state and compare
        with open('strategic_state.json', 'r') as f:
            state = json.load(f)
        
        internal_cash = state['echo']['cash'] + state['nia']['cash']
        print(f"   Internal allocated capital: ${internal_cash:.2f}")
        print(f"   Binance free balance: ${balance:.2f}")
        
        # 50% threshold as per strategic_bot.py
        if balance < internal_cash * 0.5:
            errors.append(f"Binance balance (${balance:.2f}) too low for internal allocation (${internal_cash:.2f})")
        elif balance < 50:
            warnings.append(f"Low balance (${balance:.2f}) - minimum $50 recommended")
        
    except ImportError:
        errors.append("python-binance not installed. Run: pip3 install python-binance")
    except Exception as e:
        errors.append(f"Binance connection failed: {e}")
        print(f"\n❌ Connection Error: {e}")
        print("\nCommon causes:")
        print("   • IP not whitelisted on Binance")
        print("   • Invalid API keys")
        print("   • API key expired/deleted")
        print("   • Network connectivity issues")
    
    # Final summary
    print("\n" + "="*70)
    print("VPS VERIFICATION SUMMARY")
    print("="*70)
    
    if errors:
        print("\n❌ CRITICAL ERRORS:")
        for i, err in enumerate(errors, 1):
            print(f"   {i}. {err}")
        print("\n🚫 DEPLOYMENT BLOCKED - Fix all errors before proceeding")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for i, warn in enumerate(warnings, 1):
            print(f"   {i}. {warn}")
    
    if not errors and not warnings:
        print("\n✅✅✅ ALL CHECKS PASSED - READY FOR DEPLOYMENT ✅✅✅")
    elif not errors:
        print("\n✅ No critical errors - Review warnings before deployment")
    
    print("="*70)
    
    return len(errors) == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and '--local' in sys.argv:
        success = verify_local_only()
    elif len(sys.argv) > 1 and '--vps' in sys.argv:
        success = verify_vps()
    else:
        print("Usage:")
        print("  pythonverify_deployment.py --local  # Test locally without API")
        print("  python verify_deployment.py --vps    # Full test on VPS")
        # Default to local if no args? Or error? Let's default to usage.
        sys.exit(1)
    
    sys.exit(0 if success else 1)
