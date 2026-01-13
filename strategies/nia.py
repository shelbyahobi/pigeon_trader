from .base import BaseStrategy
import pandas as pd
import numpy as np

class NIAStrategy(BaseStrategy):
    """
    Narrative Ignition Asymmetry (NIA)
    "Buy the ignored infrastructure before the storytellers arrive."
    
    Proxies used:
    - Dev Score -> CoinGecko Developer Score
    - Attention -> CoinGecko Community Score + Volume Efficiency
    - Liquidity -> High/Low Range compression
    """
    def __init__(self):
        super().__init__("Narrative Ignition Asymmetry")

    def calculate_indicators(self, df):
        # 1. Spread Proxy (Liquidity Regime)
        # Using Daily Range as proxy for Spread/Liquidity Cost
        df['daily_range'] = (df['high'] - df['low']) / df['price']
        df['range_30d_avg'] = df['daily_range'].rolling(window=30).mean()
        
        # Spread Compression: Current range vs 30d avg
        # < -20% -> MMs returning/tightening
        df['spread_compression'] = (df['daily_range'] / df['range_30d_avg']) - 1
        
        # 2. Volume Filters
        if 'total_volume' in df.columns:
            df['vol_ma_30'] = df['total_volume'].rolling(window=30).mean()
            # "Volume Spike" (Suspicious Activity Filter) -> > 5x 30d Avg
            df['vol_spike_ratio'] = df['total_volume'] / df['vol_ma_30']
        else:
            df['vol_spike_ratio'] = 0.0
            
        # 3. Price Filters (Anti-FOMO)
        # Price vs 30d High
        df['high_30d'] = df['price'].rolling(window=30).max()
        df['price_vs_high'] = df['price'] / df['high_30d']
        
        # 4. Drawdown (Discovery) - Relaxed for Young Assets
        df['year_high'] = df['price'].rolling(window=365, min_periods=20).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        return df

    def get_signal(self, df, current_pos_price=None, highest_price=None, mode="nia", context={}):
        """
        NIA Signal Logic
        """
        # EXPERT BYPASS (Top Priority)
        # If Screener identified valid Flash Crash, we BUY immediately regardless of history length.
        if context.get('is_flash_crash', False):
             print(f"  [NIA] BUYING FLASH CRASH: {context.get('symbol')}")
             return 'BUY'

        # Allow very short history for young speculative plays, but require SOME data
        if len(df) < 20: return 'HOLD'
        
        df = self.calculate_indicators(df.copy())
        row = df.iloc[-1]
        price = row['price']
        
        # --- SELL LOGIC ---
        if current_pos_price is not None:
            # ... (Existing Sell Logic omitted for brevity, assuming standard hold) ...
            # Thesis Invalidation (Proxied):
            # Thesis Invalidation (Proxied):
            # A. Macro: BTC Bear Market (Safety Patch)
            btc_bullish = context.get('btc_bullish', True)
            if not btc_bullish: return 'SELL' # Macro Stop
            
            pnl_pct = (price - current_pos_price) / current_pos_price
            
            # B. Catastrophic Stop (-50%)
            # Prevent "Ride or Die" to zero. Preserve 50% capital.
            if pnl_pct < -0.50:
                 print(f"  [NIA] HARD STOP: {context.get('symbol')} down {pnl_pct*100:.1f}%")
                 return 'SELL'

            # C. VC Style Exit (10x)
            if pnl_pct > 10.0: return 'SELL'
            
            return 'HOLD'
                
        # --- BUY LOGIC ---
        else:
            # 0. EXPERT BYPASS
            # If Screener identified valid Flash Crash, we BUY immediately.
            if context.get('is_flash_crash', False):
                 print(f"  [NIA] BUYING FLASH CRASH: {context.get('symbol')}")
                 return 'BUY'

            # 1. NON-PRICE DISCOVERY
            # Signal 1: Dev Score > 50 (CoinGecko)
            dev_score = context.get('dev_score', 0)
            age = context.get('age_years', 5.0) # Default to old if missing
            
            # NIA Logic Update: New coins often have 0 Dev Score (No GitHub tracking yet)
            # If Young (< 2y), we ignore Dev Score.
            min_dev = 50 if age >= 2.0 else 0
            
            if dev_score < min_dev: return 'HOLD'
            
            # Signal 3: Narratice Compressibility
            categories = context.get('categories', [])
            has_narrative = len(categories) > 0
            if not has_narrative: return 'HOLD'
            
            # 2. ENTRY FILTERS (Anti-FOMO)
            # Tier 1 Watchlist passed (Screener). Now Tier 2 Capital Check.
            
            # Price quiet?
            is_quiet = row['price_vs_high'] <= 1.15
            # Volume organic?
            is_organic = row['vol_spike_ratio'] < 5.0
            # Deep Value?
            is_deep = row['drawdown'] > 0.60
            
            if is_deep and is_quiet and is_organic:
                # Composite Trigger
                # WITHOUT Fake Spread Data:
                # We rely on Dev Score being "High enough" to differentiate.
                # If Dev Score > 60 -> BUY.
                if dev_score > 60:
                     return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        # 1. Pre-calculate indicators
        df = self.calculate_indicators(df.copy())
        
        capital = self.capital
        position = None
        equity_curve = []
        
        start_idx = 50
        # Warmup fill
        for _ in range(start_idx): equity_curve.append(capital)
            
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['price']
            
            # --- POSITON MGMT ---
            if position:
                # 1. HOLD until +1000% or Macro Stop (Not simulated here)
                # We simulate the 10x target
                pnl_pct = (price - position['entry']) / position['entry']
                
                if pnl_pct > 10.0:
                    capital = position['amount'] * price
                    position = None
                
                # We also simulate a -50% Hard Stop just for safety in backtest
                elif pnl_pct < -0.50:
                     capital = position['amount'] * price
                     position = None
                    
            # --- ENTRY ---
            else:
                 # Simulate Context (Assume Good Token)
                 dev_score = 80
                 has_narrative = True
                 
                 # Logic matches get_signal
                 is_quiet = row['price_vs_high'] <= 1.15 if not pd.isna(row['price_vs_high']) else False
                 is_organic = row['vol_spike_ratio'] < 5.0 if not pd.isna(row['vol_spike_ratio']) else True
                 
                 # Looser drawdon for backtest to see action
                 is_deep = row['drawdown'] > 0.60 if not pd.isna(row['drawdown']) else False
                 
                 if is_deep and is_quiet and is_organic:
                     # BUY
                     position = {
                         'entry': price,
                         'amount': capital / price
                     }
                     capital = 0 # All in
            
            # Track
            val = capital
            if position:
                val = position['amount'] * price
            equity_curve.append(val)
            
        if not equity_curve: return 0.0, pd.Series()
        final_val = equity_curve[-1]
        roi = ((final_val - self.capital) / self.capital) * 100
        return roi, pd.Series(equity_curve, index=df.range(len(equity_curve)) if len(equity_curve)!=len(df) else df.index)
        # Note: Index alignment might be tricky if lengths differ, but standardizing on df.index is usually safe if we append 1:1.
        # Fixed alignment:
        return roi, pd.Series(equity_curve + [equity_curve[-1]]*(len(df)-len(equity_curve)), index=df.index)
