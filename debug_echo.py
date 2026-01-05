
import pandas as pd
import os
from strategies.echo import EchoStrategy

# Load sample data (SOL usually has good volatility)
CSV_PATH = 'data/SOL_history.csv'

if not os.path.exists(CSV_PATH):
    print(f"Error: {CSV_PATH} not found.")
    # Try to find any csv
    import glob
    csvs = glob.glob('data/*.csv')
    if csvs:
        CSV_PATH = csvs[0]
        print(f"Using {CSV_PATH} instead.")
    else:
        print("No data found.")
        exit()

print(f"Loading {CSV_PATH}...")
df = pd.read_csv(CSV_PATH)

# Normalize columns like backtest_system.py does
df.columns = [c.lower() for c in df.columns]
if 'volume' in df.columns:
    df['total_volume'] = df['volume']
if 'close' in df.columns:
    df['price'] = df['close']

# Ensure numeric
cols = ['open', 'high', 'low', 'price', 'total_volume']
for c in cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')

# Run Strategy
strategy = EchoStrategy()
print(f"Running Echo Strategy (Capital: ${strategy.capital})...")

roi, equity = strategy.run(df)

print("\n--- RESULTS ---")
print(f"ROI: {roi:.2f}%")
print(f"Trades found: {len(equity.unique()) - 1} (approx)") # rough check
print(f"Final Equity: ${equity.iloc[-1]:.2f}")

# Debug: Show reasons if 0%
if roi == 0:
    print("\nDEBUG: Why 0%?")
    df = strategy.calculate_indicators(df)
    print(f"Max Drawdown seen: {df['drawdown'].max():.2%}")
    print(f"Min BB Rank seen: {df['bb_width_rank'].min():.2%}")
    print(f"Vol Signals count: {df['vol_signal'].sum()}")
