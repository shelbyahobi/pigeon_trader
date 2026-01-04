import requests
import pandas as pd
import time
import os
from datetime import datetime

# The Pigeon Shortlist
TOKENS = [
    {'id': 'chainlink', 'symbol': 'LINK'},
    {'id': 'uniswap', 'symbol': 'UNI'},
    {'id': 'polkadot', 'symbol': 'DOT'},
    {'id': 'avalanche-2', 'symbol': 'AVAX'},
    {'id': 'near', 'symbol': 'NEAR'},
    {'id': 'fantom', 'symbol': 'FTM'},
    {'id': 'optimism', 'symbol': 'OP'},
    {'id': 'arbitrum', 'symbol': 'ARB'},
    {'id': 'fetch-ai', 'symbol': 'FET'},
    {'id': 'render-token', 'symbol': 'RNDR'},
    {'id': 'the-sandbox', 'symbol': 'SAND'},
    {'id': 'decentraland', 'symbol': 'MANA'},
    {'id': 'aave', 'symbol': 'AAVE'},
    {'id': 'injective-protocol', 'symbol': 'INJ'},
    {'id': 'immutable-x', 'symbol': 'IMX'},
    {'id': 'gala', 'symbol': 'GALA'},
    {'id': 'axie-infinity', 'symbol': 'AXS'},
    {'id': 'theta-token', 'symbol': 'THETA'},
    {'id': 'enjincoin', 'symbol': 'ENJ'},
    {'id': 'chiliz', 'symbol': 'CHZ'}
]

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def fetch_history(token_id, vs_currency='usd', days='max'):
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    params = {
        'vs_currency': vs_currency,
        'days': days,
        'interval': 'daily'
    }
    
    print(f"Fetching {token_id}...")
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 429:
            print("⚠️ Rate Limited! Waiting 60s...")
            time.sleep(60)
            return fetch_history(token_id, vs_currency, days)
            
        response.raise_for_status()
        data = response.json()
        
        prices = data.get('prices', [])
        volumes = data.get('total_volumes', [])
        
        if not prices:
            print(f"No data for {token_id}")
            return None
            
        # Structure: [timestamp, value]
        df_price = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df_vol = pd.DataFrame(volumes, columns=['timestamp', 'volume'])
        
        # Merge
        df = pd.merge(df_price, df_vol, on='timestamp', how='inner')
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.drop('timestamp', axis=1, inplace=True)
        
        # Filter for 2022-2025 (to catch 2022 bear and 2024 bull)
        df = df[df['date'] >= '2022-01-01']
        
        return df
        
    except Exception as e:
        print(f"Error fetching {token_id}: {e}")
        return None

def main():
    print("🦅 Pigeon History Fetcher 🦅")
    print("----------------------------")
    
    for token in TOKENS:
        symbol = token['symbol']
        token_id = token['id']
        filename = f"{DATA_DIR}/{symbol}_history.csv"
        
        if os.path.exists(filename):
            print(f"Skipping {symbol} (already exists)")
            continue
            
        df = fetch_history(token_id)
        if df is not None and not df.empty:
            df.to_csv(filename, index=False)
            print(f"✅ Saved {symbol} ({len(df)} days)")
        
        # Polite delay for public API
        time.sleep(10)

if __name__ == "__main__":
    main()
