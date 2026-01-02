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
        
        # Bandwidth % (For Squeeze detection)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
        
        # 2. ATR (Volatility)
        df['tr'] = df['price'].diff().abs()
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        df['atr_pct'] = df['atr'] / df['price']
        
        # 3. Volume Metrics
        if 'total_volume' in df.columns:
            df['vol_ma'] = df['total_volume'].rolling(window=7).mean()
            # "Volume breakout > 3x 7-day average"
            df['vol_breakout'] = df['total_volume'] > (3.0 * df['vol_ma'])
        else:
            df['vol_breakout'] = False

        # 4. Dip Metric (Drop from 365d High)
        df['year_high'] = df['price'].rolling(window=365, min_periods=50).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        return df

    def run(self, df):
        df = self.calculate_indicators(df.copy())
        
        capital = 1000.0
        position = None
        equity = []
        
        start_idx = 365 # Need year lookback for ATH
        if len(df) < start_idx: start_idx = 50
        
        # Pre-fill
        for _ in range(start_idx): equity.append(1000.0)
            
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['price']
            
            # --- EXIT LOGIC ---
            if position:
                # 1. Profit Target: Sell 50% on Vol Breakout? (Simplified to Trailing for Backtest)
                # Expert: "Trailing Mechanism: 1.5x ATR from rebound peak"
                
                # Update Peak
                if price > position['peak_price']:
                    position['peak_price'] = price
                    
                # Trailing Stop Price
                # "Dynamic trail based on 1.5x ATR from rebound peak"
                # We use ATR at entry or current? Expert implies dynamic.
                current_atr = row['atr']
                if pd.isna(current_atr): current_atr = price * 0.05
                
                stop_price = position['peak_price'] - (1.5 * current_atr)
                
                # Invalidation Hard Stop (Using 50% Volume Drop rule is hard in backtest, use fixed)
                # Let's use the stop_price.
                
                if price < stop_price:
                    # SELL
                    capital = position['amount'] * price
                    position = None
                    
            # --- ENTRY LOGIC ---
            else:
                # 1. Filter: > 60% Dip
                is_deep_dip = row['drawdown'] > 0.60
                
                # 2. Signal: Low Liquidity/Vol Squeeze
                # BB Width < 10%
                is_squeeze = row['bb_width'] < self.squeeze_threshold
                
                # 3. Whale Proxy: Volume > Avg but Price Stable? 
                # Expert: "whale accumulation... net inflows"
                # We will proxy with: We are in a squeeze (done) AND Green Candle?
                # Let's add: Price is above SMA 20 (Mid Band) to confirm "Rebound" start
                is_reclaiming = price > row['bb_mid']
                
                if is_deep_dip and is_squeeze and is_reclaiming:
                    # BUY
                    amount = capital / price
                    position = {
                        'entry': price,
                        'amount': amount,
                        'peak_price': price
                    }
                    capital = 0
                    
            # Track Equity
            val = capital if not position else position['amount'] * price
            equity.append(val)
            
        roi = ((equity[-1] - 1000)/1000) * 100
        return roi, pd.Series(equity, index=df.index)
