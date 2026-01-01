import requests
import pandas as pd
import os
import time

# --- CONFIG ---
TOKENS = {
    'pancakeswap-token': 'CAKE',
    'alpaca-finance': 'ALPACA',
    'binancecoin': 'BNB'
}
DAYS = 365 # Free tier limit is 365 days
DATA_DIR = 'data'

def fetch_history(token_id, token_symbol):
    print(f"Fetching {DAYS} days of history for {token_symbol} ({token_id})...")
    
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    params = {
        'vs_currency': 'usd',
        'days': DAYS,
        'interval': 'daily' 
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        # Rate limit handling (free tier is strict)
        if response.status_code == 429:
            print(f"Rate limited! Waiting 60s...")
            time.sleep(60)
            response = requests.get(url, params=params, timeout=15)
            
        data = response.json()
        
        if 'prices' not in data:
            print(f"Error fetching {token_symbol}: {data}")
            return False
            
        # Parse data
        # data['prices'] is a list of [timestamp, price]
        df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
        
        # Convert timestamp (ms) to datetime
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('date', inplace=True)
        
        # Save to CSV
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
        filename = f"{DATA_DIR}/{token_symbol}_history.csv"
        df.to_csv(filename)
        print(f"Saved {len(df)} records to {filename}")
        return True
        
    except Exception as e:
        print(f"Exception for {token_symbol}: {e}")
        return False

def main():
    print("--- STARTING DATA FETCH ---")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    for token_id, symbol in TOKENS.items():
        success = fetch_history(token_id, symbol)
        if success:
            # Respect rate limits between calls
            time.sleep(10) 
        else:
            print(f"Failed to fetch {symbol}")

if __name__ == "__main__":
    main()
