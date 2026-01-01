import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

# --- CONFIG ---
DATA_DIR = 'data'
INITIAL_CAPITAL = 100.0
RISK_PER_TRADE = 0.02 # 2% risk not fully used in simple models, but good for sizing
OUTPUT_IMAGE = 'strategy_comparison.png'

def load_data(symbol):
    path = f"{DATA_DIR}/{symbol}_history.csv"
    if not os.path.exists(path):
        print(f"Data for {symbol} not found.")
        return None
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    return df

# --- STRATEGIES ---

def strategy_hodl(df):
    """Buy on Day 1, Hold forever."""
    if df.empty: return 0, []
    
    start_price = df.iloc[0]['price']
    df = df.copy()
    df['holdings'] = INITIAL_CAPITAL / start_price
    df['equity'] = df['holdings'] * df['price']
    
    final_equity = df.iloc[-1]['equity']
    roi = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    return roi, df['equity']

def strategy_dip_buy(df):
    """
    Dip Buy: 
    1. Calculate All-Time High (ATH) up to current day.
    2. If Price < 0.5 * ATH (50% Dip) AND we have cash: BUY.
    3. Sell if Price > 1.2 * Entry (20% Profit).
    4. Stop Loss? Let's say -20% (0.8 * Entry).
    """
    cash = INITIAL_CAPITAL
    holdings = 0
    entry_price = 0
    equity_curve = []
    
    ATH = 0
    
    for date, row in df.iterrows():
        price = row['price']
        
        # Update ATH
        if price > ATH: ATH = price
        
        # Logic
        if holdings == 0:
            # Look to buy
            if ATH > 0 and price < (0.5 * ATH):
                # BUY signal
                holdings = cash / price
                entry_price = price
                cash = 0
        else:
            # Look to sell
            # Take Profit (+20%)
            if price >= (entry_price * 1.2):
                cash = holdings * price
                holdings = 0
                entry_price = 0
            # Stop Loss (-20%)
            elif price <= (entry_price * 0.8):
                cash = holdings * price
                holdings = 0
                entry_price = 0
                
        # Track Equity
        current_equity = cash + (holdings * price)
        equity_curve.append(current_equity)

    final_equity = equity_curve[-1]
    roi = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    return roi, pd.Series(equity_curve, index=df.index)

def strategy_sma_crossover(df):
    """
    SMA 50/200 Crossover.
    Buy/Hold when SMA50 > SMA200.
    Sell/Cash when SMA50 < SMA200.
    """
    df = df.copy()
    df['SMA50'] = df['price'].rolling(window=50).mean()
    df['SMA200'] = df['price'].rolling(window=200).mean()
    
    cash = INITIAL_CAPITAL
    holdings = 0
    equity_curve = []
    
    for date, row in df.iterrows():
        price = row['price']
        sma50 = row['SMA50']
        sma200 = row['SMA200']
        
        if pd.isna(sma50) or pd.isna(sma200):
            # Not enough data yet, stay in cash
            equity_curve.append(cash + (holdings * price))
            continue
            
        if holdings == 0:
            # Buy Signal: Golden Cross
            if sma50 > sma200:
                holdings = cash / price
                cash = 0
        else:
            # Sell Signal: Death Cross
            if sma50 < sma200:
                cash = holdings * price
                holdings = 0
                
        equity_curve.append(cash + (holdings * price))
        
    final_equity = equity_curve[-1]
    roi = ((final_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    return roi, pd.Series(equity_curve, index=df.index)

def main():
    tokens = ['CAKE', 'ALPACA', 'BNB']
    results = []
    
    plt.figure(figsize=(12, 8))
    
    for token in tokens:
        print(f"\nAnalyzing {token}...")
        df = load_data(token)
        if df is None: continue
        
        # Run Strategies
        roi_hodl, eq_hodl = strategy_hodl(df)
        roi_dip, eq_dip = strategy_dip_buy(df)
        roi_sma, eq_sma = strategy_sma_crossover(df)
        
        print(f"  HODL ROI: {roi_hodl:.2f}%")
        print(f"  DIP ROI:  {roi_dip:.2f}%")
        print(f"  SMA ROI:  {roi_sma:.2f}%")
        
        results.append({
            'Token': token,
            'HODL': roi_hodl,
            'DIP': roi_dip,
            'SMA': roi_sma
        })
        
        # Plot only DIP vs HODL for clarity for one token, or aggregate?
        # Let's plot DIP strategy for all tokens to see how it performed
        plt.plot(eq_dip.index, eq_dip, label=f'{token} (Dip Buy)')
        
    plt.title('Dip Buy Strategy Performance (1 Year)')
    plt.xlabel('Date')
    plt.ylabel('Equity ($)')
    plt.legend()
    plt.grid(True)
    plt.savefig(OUTPUT_IMAGE)
    print(f"\nComparison chart saved to {OUTPUT_IMAGE}")
    
    # Summary Table
    res_df = pd.DataFrame(results)
    print("\n=== FINAL ROI COMPARISON ===")
    print(res_df.to_string(index=False))

if __name__ == "__main__":
    main()
