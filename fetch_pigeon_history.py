import yfinance as yf
import pandas as pd
import time
import os

# Mapping CoinGecko IDs (used in bot) to Yahoo Tickers
TOKEN_MAP = {
    'chainlink': 'LINK-USD',
    'uniswap': 'UNI-USD',
    'polkadot': 'DOT-USD',
    'avalanche-2': 'AVAX-USD',
    'near': 'NEAR-USD',
    'fantom': 'FTM-USD',
    'optimism': 'OP-USD',
    'arbitrum': 'ARB-USD',
    'fetch-ai': 'FET-USD',
    'render-token': 'RNDR-USD',
    'the-sandbox': 'SAND-USD',
    'decentraland': 'MANA-USD',
    'aave': 'AAVE-USD',
    'injective-protocol': 'INJ-USD',
    'immutable-x': 'IMX-USD',
    'gala': 'GALA-USD',
    'axie-infinity': 'AXS-USD',
    'theta-token': 'THETA-USD',
    'enjincoin': 'ENJ-USD',
    'chiliz': 'CHZ-USD',
    # Benchmarks
    'bitcoin': 'BTC-USD',
    'ethereum': 'ETH-USD',
    'solana': 'SOL-USD',
    'binancecoin': 'BNB-USD',
    'pancakeswap-token': 'CAKE-USD',
}

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def fetch_history(token_id, ticker):
    print(f"Fetching {ticker} for {token_id}...")
    try:
        # Download data from 2022-01-01 to Present
        df = yf.download(ticker, start="2022-01-01", progress=False)
        
        if df.empty:
            print(f"⚠️ No data for {ticker}")
            return
        
        # Yahoo Finance returns a MultiIndex sometimes, or specific columns.
        # We generally get: Open, High, Low, Close, Adj Close, Volume
        # We need to flatten it and keep 'Close' as 'price' and 'Volume' as 'volume'
        
        df = df.reset_index()
        
        # Standardize columns (ensure lowercase 'date', 'price', 'volume')
        # YF columns are usually Title Case: Date, Open, High, Low, Close, Volume
        
        df.rename(columns={
            'Date': 'date',
            'Close': 'price',
            'Volume': 'volume'
        }, inplace=True)
        
        # Filter to keep only needed columns
        keep_cols = ['date', 'price', 'volume']
        # If High/Low/Open exist, keep them for more advanced strats if needed, but min req is price/vol
        for c in ['Open', 'High', 'Low']:
            if c in df.columns:
                df.rename(columns={c: c.lower()}, inplace=True)
                keep_cols.append(c.lower())
                
        df = df[keep_cols]
        
        # Save
        # Map back to the filename format the bot expects: "SYMBOL_history.csv"
        # We need the symbol from the ID.
        # Quick hack: ID is mapped, but we save as "SYMBOL_history.csv" 
        # The bot uses IDs internally but loads files based on... wait using os.path.basename in backtest.
        # Actually backtest_system.py does: `symbol = os.path.basename(f).replace('_history.csv', '')`
        # So if we save as `LINK_history.csv`, the key in backtest will be `LINK`. 
        # The bot watchlist uses `symbol` so this matches.
        
        symbol = ticker.split('-')[0]
        filename = f"{DATA_DIR}/{symbol}_history.csv"
        
        df.to_csv(filename, index=False)
        print(f"✅ Saved {symbol} ({len(df)} days)")
        
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")

def main():
    print("🦅 Pigeon History Fetcher (Yahoo Edition) 🦅")
    print("------------------------------------------")
    
    for token_id, ticker in TOKEN_MAP.items():
        fetch_history(token_id, ticker)
        # Yahoo is nicer than CoinGecko, but let's be polite
        time.sleep(1)

if __name__ == "__main__":
    main()
