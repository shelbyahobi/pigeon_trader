import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
try:
    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET'))
    
    # Check Balances
    link = client.get_asset_balance(asset='LINK')
    print(f"LINK Wallet Balance: {link}")
    
    usdc = client.get_asset_balance(asset='USDC')
    print(f"USDC Wallet Balance: {usdc}")

    uni = client.get_asset_balance(asset='UNI')
    print(f"UNI Wallet Balance: {uni}")
    
    # Check Symbol Info (Min Notation)
    info = client.get_symbol_info('LINKUSDC')
    for f in info['filters']:
        if f['filterType'] == 'NOTIONAL':
            print(f"Min Notional: {f['minNotional']}")
        if f['filterType'] == 'LOT_SIZE':
            print(f"Lot Size: {f}")

except Exception as e:
    print(f"Error: {e}")
