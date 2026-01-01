import requests
import pandas as pd
import os
import time

# --- CONFIG ---
TOKENS = {
    'pancakeswap-token': 'CAKE',
    'binancecoin': 'BNB',
    'ethereum': 'ETH',
    'bitcoin': 'BTC'
}
DATA_DIR = 'data'

def fetch_history(token_id, token_symbol, start_date=None, end_date=None, days=365):
    """
    Fetch history. 
    If start_date/end_date provided (UNIX timestamps), use range.
    Else use 'days'.
    """
    print(f"Fetching history for {token_symbol} ({token_id})...")
    
    url = f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart/range" if start_date else f"https://api.coingecko.com/api/v3/coins/{token_id}/market_chart"
    
    params = {'vs_currency': 'usd'}
    
    if start_date and end_date:
        params['from'] = start_date
        params['to'] = end_date
    else:
        params['days'] = days
        params['interval'] = 'daily'
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        # Rate limit handling
        if response.status_code == 429:
            print(f"Rate limited! Waiting 60s...")
            time.sleep(60)
            return fetch_history(token_id, token_symbol, start_date, end_date, days) # Retry
            
        data = response.json()
        
        if 'prices' not in data:
            print(f"Error fetching {token_symbol}: {data}")
            return False
            
        # Parse data
        df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('date', inplace=True)
        
        # Save to CSV with specific tag if range used
        tag = "_custom" if start_date else "_history"
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            
        filename = f"{DATA_DIR}/{token_symbol}{tag}.csv"
        df.to_csv(filename)
        print(f"Saved {len(df)} records to {filename}")
        return True
        
    except Exception as e:
        print(f"Exception for {token_symbol}: {e}")
        return False

def main():
    print("--- STARTING CYCLICAL DATA FETCH ---")
    
    # Define Cycles (UNIX Timestamps)
    # Bear Market 2022: Jan 1 2022 (1640995200) - Dec 31 2022 (1672444800)
    bear_start = 1640995200
    bear_end = 1672444800
    
    # Bull Run 2023-2024: Jan 1 2023 (1672531200) - Jan 1 2024 (1704067200)
    # (Or use last 365 days for recent bull)
    
    for token_id, symbol in TOKENS.items():
        # Fetch BEAR market data
        print(f"  > Fetching 2022 BEAR data...")
        fetch_history(token_id, symbol + "_BEAR", start_date=bear_start, end_date=bear_end)
        time.sleep(10) # Respect rate limit
        
        # Fetch Standard 1 Year (Recent/Bull)
        print(f"  > Fetching Recent data...")
        fetch_history(token_id, symbol, days=365)
        time.sleep(10)

if __name__ == "__main__":
    main()
