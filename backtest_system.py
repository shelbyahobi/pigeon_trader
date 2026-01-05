import pandas as pd
import os
import glob
from strategies.dip_buy import DipBuyStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.echo import EchoStrategy
from strategies.nia import NIAStrategy
from strategies.ler import LERStrategy

DATA_DIR = 'data'

def load_all_data():
    """Loads all CSVs from data/ directory."""
    data_map = {}
    files = glob.glob(f"{DATA_DIR}/*_history.csv")
    for f in files:
        # Extract symbol from filename "data\\CAKE_history.csv"
        symbol = os.path.basename(f).replace('_history.csv', '')
        df = pd.read_csv(f)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # Force numeric types (handle strings from CSV) for ALL columns
        for col in ['price', 'volume', 'high', 'low', 'open']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Alias 'volume' to 'total_volume' for ECHO/LER compatibility
        if 'volume' in df.columns:
            df['total_volume'] = df['volume']
            
        # Drop rows with NaN prices
        df.dropna(subset=['price'], inplace=True)
        
        df.sort_index(inplace=True)
        data_map[symbol] = df
    return data_map

def run_all_strategies():
    """
    Runs all strategies against all tokens.
    Returns a dictionary structure: results[token][strategy_name] = (roi, equity_curve)
    """
    data_map = load_all_data()
    
    # Instantiate Strategies
    strategies = [
        EchoStrategy(),
        NIAStrategy(),
        LERStrategy(),
        DipBuyStrategy(), # Baseline
        RSIStrategy()     # Baseline
    ]
    
    results = {}
    
    for symbol, df in data_map.items():
        results[symbol] = {}
        for strat in strategies:
            try:
                # Pre-check for required columns (Soft check)
                if strat.name == 'Narrative Ignition Asymmetry' and 'high' not in df.columns:
                    raise ValueError("Missing High/Low data for NIA")
                
                roi, equity_curve = strat.run(df)
                results[symbol][strat.name] = {
                    'roi': roi,
                    'equity_curve': equity_curve
                }
            except Exception as e:
                # Log error but don't crash dashboard
                print(f"⚠️ Error with {strat.name} on {symbol}: {e}")
                results[symbol][strat.name] = {
                    'roi': 0.0,
                    'equity_curve': pd.Series()
                }
            
    return results

if __name__ == "__main__":
    # Test run
    results = run_all_strategies()
    for token, strats in results.items():
        print(f"--- {token} ---")
        for strat_name, res in strats.items():
            print(f"  {strat_name}: {res['roi']:.2f}%")
