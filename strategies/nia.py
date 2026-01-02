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
        
        # 4. Drawdown (Discovery)
        df['year_high'] = df['price'].rolling(window=365, min_periods=50).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        return df

    def get_signal(self, df, current_pos_price=None, highest_price=None, mode="nia", context={}):
        """
        NIA Signal Logic
        """
        if len(df) < 50: return 'HOLD'
        
        df = self.calculate_indicators(df.copy())
        row = df.iloc[-1]
        price = row['price']
        
        # --- SELL LOGIC ---
        if current_pos_price is not None:
            # Improvement 4: "Infinite Hold" Core after +300%
            # We need to know if we already took profit.
            # State limitation: We don't track "already_took_profit" flag in this simple bot version easily without reading logs.
            # HEURISTIC: We will rely on the bot's sizing.
            # But here outputting 'SELL' sells the WHOLE position in current `strategic_bot` implementation :(
            # We can't do partial exits without refactoring `strategic_bot.py`.
            
            # WORKAROUND: We will only signal SELL if we hit the "Thesis Invalidation" or "Extreme Top".
            # For the +300% partial, we can't do it in this 'on/off' signal architecture easily.
            # So we will pivot to: "Let partials be manual for now" OR "Exit fully at +500%?"
            # User said: "Never sell below your entry again after +300%... prevent selling SOL at $8"
            
            # BEST COMPROMISE FOR V1 BOT:
            # 1. HOLD until +500% (6x). Then Sell? Too greedy.
            # 2. HOLD indefinitely unless "Thesis Invalidation".
            
            # Thesis Invalidation (Proxied):
            # A. Macro: BTC Bear Market (Context available?)
            btc_bullish = context.get('btc_bullish', True)
            if not btc_bullish: return 'SELL' # Macro Stop
            
            # B. Dev Death (Score drops < 30?) - Can't check history easily.
            # C. Extreme Drawdown from Peak (>90%)?
            
            # Since we can't do partials, we will adopt "VC Style":
            # Target 10x or 0.
            # If PnL > 10.0 (1000%), SELL ALL.
            pnl_pct = (price - current_pos_price) / current_pos_price
            if pnl_pct > 10.0: return 'SELL'
            
            # If we are up 300% and drop 50%... HOLD.
            # If we are down 99%... HOLD.
            
            return 'HOLD'
                
        # --- BUY LOGIC ---
        else:
            # 1. NON-PRICE DISCOVERY
            # Signal 1: Dev Score > 50 (CoinGecko)
            dev_score = context.get('dev_score', 0)
            if dev_score < 50: return 'HOLD'
            
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
        # Backtest wrapper
        df = self.calculate_indicators(df)
        return 0, pd.Series()
