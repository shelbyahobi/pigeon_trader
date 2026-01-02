from .base import BaseStrategy
import pandas as pd
import numpy as np

class EchoStrategy(BaseStrategy):
    def __init__(self, bb_period=20, bb_std=2.0, squeeze_threshold=0.10, atr_period=14):
        super().__init__("Echo Liquidity Rebound")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.squeeze_threshold = squeeze_threshold
        self.atr_period = atr_period

    def calculate_indicators(self, df):
        # 1. Bollinger Bands
        df['bb_mid'] = df['price'].rolling(window=self.bb_period).mean()
        df['bb_std'] = df['price'].rolling(window=self.bb_period).std()
        df['bb_upper'] = df['bb_mid'] + (self.bb_std * df['bb_std'])
        df['bb_lower'] = df['bb_mid'] - (self.bb_std * df['bb_std'])
        
        # Bandwidth Rank (Percentile) - "Self-Adjusting Squeeze"
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        df['bb_width_rank'] = df['bb_width'].rolling(window=180).rank(pct=True)
        
        # 2. ATR (Volatility)
        df['tr'] = df['price'].diff().abs()
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        
        # 3. Volume Trend (Hardened Check)
        if 'total_volume' in df.columns:
            df['vol_ma_7'] = df['total_volume'].rolling(window=7).mean()
            # A. Magnitude: > 1.5x Avg (Not 3x)
            df['vol_spike'] = df['total_volume'] > (1.5 * df['vol_ma_7'])
            # B. Trend: Rising for 3 days (Accumulation Build-up)
            df['vol_rising'] = (df['total_volume'] > df['total_volume'].shift(1)) & \
                               (df['total_volume'].shift(1) > df['total_volume'].shift(2))
            
            df['vol_signal'] = df['vol_spike'] & df['vol_rising']
        else:
            df['vol_signal'] = False

        # 4. Dip Metric (Drop from 365d High)
        df['year_high'] = df['price'].rolling(window=365, min_periods=50).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        return df

    def get_signal(self, df, current_pos_price=None, highest_price=None, mode="echo", context={}):
        """
        Live Signal Generation for Strategic Bot.
        """
        if len(df) < 180: return 'HOLD'
        
        df = self.calculate_indicators(df.copy())
        row = df.iloc[-1]
        price = row['price']
        
        # --- SELL LOGIC ---
        if current_pos_price:
            # Dynamic Trailing Stop (1.5x ATR)
            # Expert Rule: "Loosen stop if pumping, tighten if stalling" - complex, keeping 1.5x ATR for simplicity
            atr = row['atr'] if not pd.isna(row['atr']) else price * 0.05
            
            # Highest price since entry is tracked by bot
            stop_price = highest_price - (1.5 * atr)
            
            # Hard Stop (-15%)
            hard_stop = current_pos_price * 0.85
            
            if price < max(stop_price, hard_stop):
                return 'SELL'
                
        # --- BUY LOGIC ---
        else:
            # 1. Context Filters (Passed via context dict)
            btc_bullish = context.get('btc_bullish', True) # Default True if check fails
            funding_ok = context.get('funding_ok', True)   # Default True
            
            if not btc_bullish: return 'HOLD' # "Regime Awareness"
            if not funding_ok: return 'HOLD'  # "No Blind Spot"
            
            # 2. Hardened Logic
            # A. Deep Value (-60%)
            is_deep = row['drawdown'] > 0.60
            
            # B. Squeeze (Percentile based)
            # < 20th Percentile of past 6 months
            is_squeeze = row['bb_width_rank'] < 0.20
            
            # C. Volume Trend
            is_vol_trend = row['vol_signal']
            
            if is_deep and is_squeeze and is_vol_trend:
                return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        # Backtest wrapper (simplified)
        df = self.calculate_indicators(df.copy())
        # ... (Rest of backtest logic would go here, simulating context is hard without extensive data)
        # For now, preserving structure for get_signal to work
        return 0, pd.Series()
