import pandas as pd
import matplotlib.pyplot as plt
import os
import glob
from strategies.aamr import AAMRStrategy
from strategies.phoenix import PhoenixStrategy
from strategies.echo import EchoStrategy
from strategies.ler import LERStrategy
from strategies.lvp import LVPStrategy

# Silence warnings
pd.options.mode.chained_assignment = None 

def load_data():
    """Loads CSVs."""
    data_map = {}
    files = glob.glob(f"data/*_history.csv")
    for f in files:
        symbol = os.path.basename(f).replace('_history.csv', '')
        df = pd.read_csv(f)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        data_map[symbol] = df
    return data_map

def run_backtest_loop(df, strategy, mode):
    capital = 1000.0
    position = None 
    equity = []
    
    # Calculate indicators once
    df_indic = strategy.calculate_indicators(df.copy())
    
    # Start loop
    start_idx = 200 # Need warm up for SMA 200
    
    # Pre-fill equity for warm-up period
    for _ in range(start_idx):
        equity.append(1000.0)
    
    for i in range(start_idx, len(df_indic)):
        # Simulation Slice
        curr_slice = df_indic.iloc[:i+1]
        price = curr_slice['price'].iloc[-1]
        
        curr_pos_price = position['entry'] if position else None
        curr_high = position['highest'] if position else None
        
        # Update Highest for Trailing Stop
        if position and price > position['highest']:
            position['highest'] = price
            curr_high = price
            
        signal = strategy.get_signal(curr_slice, curr_pos_price, curr_high, mode=mode)
        
        if signal == 'BUY' and not position:
            amount = capital / price
            position = {'entry': price, 'amount': amount, 'highest': price}
            capital = 0
            
        elif signal == 'SELL' and position:
            capital = position['amount'] * price
            position = None
            
        # Track Equity
        curr_val = capital if not position else position['amount'] * price
        equity.append(curr_val)
        
    return pd.Series(equity, index=df_indic.index)

def run_phoenix_loop(df, strategy):
    # Wrapper for Phoenix's own run method since it has custom logic
    roi, series = strategy.run(df)
    return series

def generate_comparison_plot():
    data = load_data()
    symbols = ['CAKE', 'BNB', 'ALPACA']
    
    if not data:
        print("No data found.")
        return

    strat_aamr = AAMRStrategy()
    strat_phoenix = PhoenixStrategy()
    strat_echo = EchoStrategy()
    strat_ler = LERStrategy()
    strat_lvp = LVPStrategy()
    
    plt.figure(figsize=(15, 20))
    
    # Plot layout
    # Add SOL and PEPE if they exist
    full_symbols = ['CAKE', 'BNB', 'ALPACA', 'SOL', 'PEPE']
    # Filter only those in data
    symbols = [s for s in full_symbols if s in data]
    
    for i, symbol in enumerate(symbols):
        if symbol not in data: continue
        
        df = data[symbol]
        
        # Run 4 Modes
        eq_std = run_backtest_loop(df, strat_aamr, mode='standard')
        eq_flash = run_backtest_loop(df, strat_aamr, mode='flash')
        eq_phoenix = run_phoenix_loop(df, strat_phoenix)
        eq_echo = run_phoenix_loop(df, strat_echo) 
        eq_ler = run_phoenix_loop(df, strat_ler)
        eq_lvp = run_phoenix_loop(df, strat_lvp)
        
        # Subplot
        plt.subplot(len(symbols), 1, i+1)
        plt.plot(eq_std.index, eq_std, label='Standard (Dip)', color='gray', linestyle='--', alpha=0.5)
        plt.plot(eq_flash.index, eq_flash, label='Flash (Crash)', color='blue', linewidth=1.5, alpha=0.5)
        plt.plot(eq_phoenix.index, eq_phoenix, label='Phoenix (Breakout)', color='red', linewidth=1.5, alpha=0.5)
        plt.plot(eq_echo.index, eq_echo, label='Echo (Rebound)', color='green', linewidth=1.5, alpha=0.5)
        plt.plot(eq_ler.index, eq_ler, label='LER (Regime)', color='purple', linewidth=1.5, alpha=0.6)
        plt.plot(eq_lvp.index, eq_lvp, label='LVP-SR (Vacuum)', color='black', linewidth=2.5) # Highlight the Challenger
        plt.plot(df.index, (df['price'] / df['price'].iloc[0]) * 1000, label='Buy & Hold', color='orange', alpha=0.2)
        
        plt.title(f"{symbol}: Benchmark (The Final Battle)")
        plt.legend(loc='upper left', fontsize='small')
        plt.grid(True, alpha=0.3)
        plt.ylabel("Value ($)")
        
    plt.tight_layout()
    plt.savefig('benchmark_challenger_compare.png')
    print("Chart saved to benchmark_challenger_compare.png")

if __name__ == "__main__":
    generate_comparison_plot()
