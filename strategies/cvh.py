from .base import BaseStrategy
import pandas as pd
import numpy as np

class CVHStrategy(BaseStrategy):
    def __init__(self, spread_lookback=7, vol_lookback=30):
        super().__init__("Capitulation Vortex Harvest")
        self.spread_lookback = spread_lookback
        self.vol_lookback = vol_lookback

    def calculate_indicators(self, df):
        # 1. Spread Proxy (High-Low Range relative to Price)
        # Real spread requires Order Book, we use Daily Range as proxy to "Volatility/Liquidity Cost"
        df['daily_range'] = (df['high'] - df['low']) / df['price']
        
        # Spread "Narrowing" (Compression)
        # We want current range to be 20% tighter than 7-day peak
        df['range_7d_max'] = df['daily_range'].rolling(window=7).max()
        df['spread_narrowing'] = (df['range_7d_max'] - df['daily_range']) / df['range_7d_max']
        
        # 2. Narrative Ignition Proxy (Volume + Price Strength)
        if 'total_volume' in df.columns:
            df['vol_ma_30'] = df['total_volume'].rolling(window=30).mean()
            # "Semantic Spike" Proxy: Volume > 2x 30d Avg
            df['narrative_spike'] = df['total_volume'] > (2.0 * df['vol_ma_30'])
        else:
            df['narrative_spike'] = False
            
        # 3. Drawdown (Discovery Filter)
        df['year_high'] = df['price'].rolling(window=365, min_periods=50).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        # 4. Spread Volatility (For Sizing)
        df['spread_std'] = df['daily_range'].rolling(window=14).std()

        return df

    def get_signal(self, df, current_pos_price=None, highest_price=None, mode="cvh", context={}):
        """
        CVH Signal Logic
        """
        if len(df) < 50: return 'HOLD'
        
        df = self.calculate_indicators(df.copy())
        row = df.iloc[-1]
        price = row['price']
        
        # --- SELL LOGIC ---
        if current_pos_price is not None:
            # 1. Moonbag Exit (Laddered)
            # This is handled by position sizing logic usually, but here we return basic SELL
            # if we hit stops or final targets.
            
            # Trail Remainder: "Exit if spread widens > 30% from rebound avg"
            # Proxy: If Daily Range spikes > 1.3x 
            current_range = row['daily_range']
            # We don't have "rebound avg" stored easily without complex state.
            # Use simplified Trailing Stop for bot framework compatibility.
            # User said: "Drawdowns < 80% ignored". This means NO STOP LOSS usually.
            # But "100% loss acceptance".
            
            # We will use the "Spread Widening" as the only exit.
            # If range explodes (Volatility returns = End of Vortex), we exit?
            # Or if price creates a lower low?
            
            # For safety in this framework, we stick to the Expert's "10x" target or "Spread Widening".
            # Let's implement a "Volatility Expansion" exit.
            if current_range > (row['range_7d_max'] * 1.3):
                return 'SELL' # Spread/Vol blew out
            
            return 'HOLD'
                
        # --- BUY LOGIC ---
        else:
            # 1. Discovery Filters
            is_deep_value = row['drawdown'] > 0.60
            
            # 2. Vortex Entry
            # Spread Narrowing > 20%
            is_vortex_tight = row['spread_narrowing'] > 0.20
            
            # 3. Narrative Ignition
            is_narrative = row['narrative_spike']
            
            if is_deep_value and is_vortex_tight and is_narrative:
                return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        # Backtest wrapper
        df = self.calculate_indicators(df.copy())
        return 0, pd.Series()
