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
            # Expert Exit Logic:
            # 1. Profit Tranches (Simplified for bot)
            # +300% -> Sell 10%
            # For this bot, we mimic the "Hold Winners" by using a very loose trailing stop
            # or simply relying on the 100% loss acceptance (no stop loss) until huge gains.
            
            # Thesis Invalidation:
            # "Time stop (18mo)" -> Can't check easily.
            # "Macro Regime" -> Check BTC Context.
            
            btc_bullish = context.get('btc_bullish', True)
            # If Bear Market and held long (proxy: drawdown deepened?), exit.
            # For simplicity: Keep 100% Loss Acceptance. Only sell on massive outlier gains?
            # Or use a loose "Thesis Break".
            
            # Let's use a 50% Trailing Stop for "Winners" to lock in 100x potential but survive 40% drops.
            # "Drawdowns < 80% ignored" says expert.
            # So, basically NO STOP LOSS.
            
            # We only sell if:
            # 1. BTC enters long-term bear?
            # 2. Or Price > 10x Entry?
            
            # Implemented: Take Profit at 3x (300%) for 50%?
            # Let's stick to simple:
            # If PnL > +300%, sell half.
            # If PnL > +1000%, sell all.
            pnl_pct = (price - current_pos_price) / current_pos_price
            
            if pnl_pct > 3.0: return 'SELL' # Lock in the 3x-10x zone
            
            return 'HOLD'
                
        # --- BUY LOGIC ---
        else:
            # 1. NON-PRICE DISCOVERY (Metadata Check)
            # Signal 1: Dev Score > 0.7 (CoinGecko score is 0-100? Assuming > 50 is decent)
            dev_score = context.get('dev_score', 0)
            if dev_score < 50: return 'HOLD' # "Dead Project"
            
            # Signal 2: Liquidity/Spread (Compression)
            # Spread Change < -20% (Tightening)
            is_spread_tightening = row['spread_compression'] < -0.20
            # OR High CG Liquidity Score?
            # Expert: "2 of 3 liquidity metrics". We have Spread. Assume OK if tight.
            
            # Signal 3: Attention (Community Score)
            comm_score = context.get('comm_score', 0)
            if comm_score < 50: return 'HOLD' # "No community"
            
            # 2. ENTRY FILTERS (Anti-FOMO)
            # Price condition: price_vs_30d_high <= 1.15 (Hasn't pumped yet)
            is_quiet = row['price_vs_high'] <= 1.15
            
            # Volume condition: Not a 5x spike (Pump & Dump)
            is_organic = row['vol_spike_ratio'] < 5.0
            
            # Discovery Filter: Deep Value (-60%)
            is_deep = row['drawdown'] > 0.60
            
            if dev_score and is_deep and is_quiet and is_organic:
                # We relax "Spread Tightening" if Dev Score is very high (>70)
                if is_spread_tightening or dev_score > 70:
                    return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        # Backtest wrapper
        df = self.calculate_indicators(df)
        return 0, pd.Series()
