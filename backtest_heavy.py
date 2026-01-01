import pandas as pd
import matplotlib.pyplot as plt
from strategies.dip_buy import DipBuyStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.aamr import AAMRStrategy
import os

# CONFIG
DATA_DIR = 'data'
CYCLES = ['BEAR', 'BULL']
TOKENS = ['CAKE', 'BNB', 'BTC', 'ETH']

def load_data(symbol, cycle):
    path = f"{DATA_DIR}/{symbol}_{cycle}.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    return df

def run_simulation():
    # Define Strategies to Compare
    strategies = [
        DipBuyStrategy(dip_threshold=0.50), # Original settings
        RSIStrategy(rsi_period=14, buy_threshold=30, sell_threshold=70), # Standard
        AAMRStrategy() # New Adaptive Strategy
    ]

    
    report = []
    
    print(f"{'CYCLE':<6} | {'TOKEN':<5} | {'STRATEGY':<20} | {'ROI %':<8} | {'TRADES'}")
    print("-" * 65)
    
    for cycle in CYCLES:
        print(f"--- {cycle} MARKET ---")
        for token in TOKENS:
            df = load_data(token, cycle)
            if df is None: continue
            
            # Baseline (Hodl)
            start_price = df['price'].iloc[0]
            end_price = df['price'].iloc[-1]
            hodl_roi = ((end_price - start_price) / start_price) * 100
            
            report.append({
                'Cycle': cycle,
                'Token': token,
                'Strategy': 'Hold (Baseline)',
                'ROI': hodl_roi,
                'Trades': 1
            })
            print(f"{cycle:<6} | {token:<5} | {'Hold (Baseline)':<20} | {hodl_roi:>7.2f}% | 1")
            
            for strat in strategies:
                roi, equity = strat.run(df)
                # Count trades (approximate from equity changes - or update base strategy to track)
                # For now just showing ROI
                
                print(f"{cycle:<6} | {token:<5} | {strat.name:<20} | {roi:>7.2f}% | -")
                
                report.append({
                    'Cycle': cycle,
                    'Token': token,
                    'Strategy': strat.name,
                    'ROI': roi,
                    'Trades': 0 # TODO: Track trade count
                })
        print("")

    # Best Performer Summary
    df_res = pd.DataFrame(report)
    return df_res

if __name__ == "__main__":
    results = run_simulation()
    
    print("\n=== SUMMARY: AVERAGE ROI BY STRATEGY ===")
    summary = results.groupby(['Cycle', 'Strategy'])['ROI'].mean().unstack()
    print(summary)
    
    # Save to file
    results.to_csv("backtest_heavy_results.csv")
