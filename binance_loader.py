import requests
import pandas as pd
import datetime
import os
import time

# Metrics
TOKENS = {
    'CAKE': 'CAKEUSDT',
    'BNB': 'BNBUSDT',
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT'
}
DATA_DIR = 'data'

def fetch_binance_history(symbol, pair, start_str, end_str, tag):
    """
    Fetch daily klines from Binance.
    start_str/end_str format: '2022-01-01'
    """
    print(f"Fetching {symbol} ({tag}) from Binance...")
    
    # Convert dates to milliseconds timestamp
    start_ts = int(pd.Timestamp(start_str).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_str).timestamp() * 1000)
    
    all_data = []
    current_start = start_ts
    
    while current_start < end_ts:
        url = "https://api.binance.com/api/v3/klines"
        params = {
            'symbol': pair,
            'interval': '1d',
            'startTime': current_start,
            'endTime': end_ts,
            'limit': 1000
        }
        
        try:
            r = requests.get(url, params=params, timeout=10)
            if r.status_code != 200:
                print(f"Error {r.status_code}: {r.text}")
                break
                
            data = r.json()
            if not data:
                break
                
            all_data.extend(data)
            
            # Update start time to last candle + 1 day
            last_close_time = data[-1][6]
            current_start = last_close_time + 1
            
            # Respect limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Exception: {e}")
            break
            
    if not all_data:
        print(f"No data found for {symbol}")
        return
        
    # Columns: Open Time, Open, High, Low, Close, Volume, Close Time, ...
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'q_vol', 'trades', 'taker_buy_vol', 'taker_buy_q_vol', 'ignore'
    ])
    
    # Process
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['price'] = df['close'].astype(float)
    df = df[['date', 'timestamp', 'price']]
    df.set_index('date', inplace=True)
    
    # Filter range rigorously
    mask = (df.index >= pd.Timestamp(start_str)) & (df.index <= pd.Timestamp(end_str))
    df = df.loc[mask]
    
    # Save
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    filename = f"{DATA_DIR}/{symbol}_{tag}.csv"
    df.to_csv(filename)
    print(f"Saved {len(df)} days to {filename}")

def main():
    # 1. Bear Market (2022)
    start_bear = '2022-01-01'
    end_bear = '2022-12-31'
    
    # 2. Bull/Current (2023-2024)
    start_bull = '2023-01-01'
    end_bull = '2024-05-01' # Up to recent
    
    for symbol, pair in TOKENS.items():
        fetch_binance_history(symbol, pair, start_bear, end_bear, "BEAR")
        fetch_binance_history(symbol, pair, start_bull, end_bull, "BULL")

if __name__ == "__main__":
    main()
