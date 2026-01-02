from .base import BaseStrategy
import pandas as pd
import numpy as np

class AAMRStrategy(BaseStrategy):
    def __init__(self, slow_sma=200, fast_sma=50, rsi_period=14, rsi_buy=35, rsi_sell=65, vol_threshold=0.05):
        super().__init__("AAMR (Adaptive)")
        self.slow_sma = slow_sma
        self.fast_sma = fast_sma
        self.rsi_period = rsi_period
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.vol_threshold = vol_threshold
        
        return df

    def calculate_indicators(self, df):
        # SMA
        df['sma_fast'] = df['price'].rolling(window=self.fast_sma).mean()
        df['sma_slow'] = df['price'].rolling(window=self.slow_sma).mean()
        
        # RSI
        delta = df['price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatility (Standard Deviation of % returns over 24h)
        df['returns'] = df['price'].pct_change()
        df['volatility'] = df['returns'].rolling(window=24).std() # Annualized or raw
        
        # --- EXPERT: Bollinger Bands (20, 2) ---
        df['bb_mid'] = df['price'].rolling(window=20).mean()
        df['bb_std'] = df['price'].rolling(window=20).std()
        df['bb_lower'] = df['bb_mid'] - (2.0 * df['bb_std'])
        df['bb_upper'] = df['bb_mid'] + (2.0 * df['bb_std'])
        
        # --- EXPERT: ATR (Approximate using Close-to-Close) ---
        # Since we might not have High/Low, we use abs(diff)
        df['tr'] = df['price'].diff().abs()
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        return df

    def run(self, df):
        df = df.copy()
        df = self.calculate_indicators(df)
        
        capital = self.capital
        position = 0 # 0 or amount
        entry_price = 0
        
        equity_curve = []
        
        for index, row in df.iterrows():
            curr_price = row['price']
            
            # --- STATUS ---
            is_bull_trend = row['sma_fast'] > row['sma_slow']
            is_oversold = row['rsi'] < self.rsi_buy
            is_overbought = row['rsi'] > self.rsi_sell
            high_vol = row['volatility'] > self.vol_threshold
            
            # --- BUY LOGIC ---
            if position == 0:
                buy_signal = False
                
                # 1. Bull Market Entry: Trend Pullback (Aggressive)
                # If Golden Cross active, buy on ANY dip (RSI < 50 instead of 35)
                if is_bull_trend and row['rsi'] < 55:
                    buy_signal = True
                    
                # 2. Bear Market Entry: High Volatility Panic (Arb Proxy)
                # Keep strict to avoid catching falling knives
                elif not is_bull_trend and high_vol and is_oversold:
                    buy_signal = True
                    
                if buy_signal:
                    amount = capital / curr_price
                    position = amount
                    entry_price = curr_price
                    capital = 0
                    
            # --- SELL LOGIC ---
            elif position > 0:
                pct_change = (curr_price - entry_price) / entry_price
                
                sell_signal = False
                
                # 1. Take Profit (Adaptive)
                # If Bull Trend, let it run! Only sell if Extreme Overbought
                if is_bull_trend:
                    if pct_change > 0.50: # huge gain fallback
                        sell_signal = True
                    elif row['rsi'] > 85: # Extreme top
                        sell_signal = True
                    elif not is_bull_trend: # Trend broke
                        sell_signal = True
                else:
                    # Bear/Chop Mode: Quick Scalps
                    target = 0.15 
                    if high_vol: target = 0.20
                    if pct_change >= target:
                        sell_signal = True
                    
                # 2. Stop Loss (Fixed)
                if pct_change <= -0.10:
                    sell_signal = True
                    
                if sell_signal:
                    capital = position * curr_price
                    position = 0
                    entry_price = 0
            
            # Record Equity
            current_equity = capital if position == 0 else position * curr_price
            equity_curve.append(current_equity)
            
        roi = ((equity_curve[-1] - self.capital) / self.capital) * 100
        return roi, pd.Series(equity_curve, index=df.index)

    def get_signal(self, df, current_position_avg_price=None, highest_price_since_entry=None, mode="standard"):
        """
        Analyze the LATEST row of the dataframe to generate a live signal.
        Returns: 'BUY', 'SELL', or 'HOLD'
        """
        if len(df) < self.slow_sma:
            return 'HOLD' # Not enough data
            
        df = self.calculate_indicators(df)
        row = df.iloc[-1]
        
        # Current Price
        curr_price = row['price']
        
        # Indicators
        is_bull_trend = row['sma_fast'] > row['sma_slow']
        is_oversold = row['rsi'] < self.rsi_buy
        
        # Use more responsive RSI for Bull Trend or Flash Mode
        if is_bull_trend:
            is_oversold = row['rsi'] < 55
            
        is_extreme_overbought = row['rsi'] > 85
        high_vol = row['volatility'] > self.vol_threshold
        
        # --- BUY SIGNAL ---
        if current_position_avg_price is None:
            
            # 1. FLASH MODE (Expert Entry)
            if mode == 'flash':
                # Entry: Price < Lower Bollinger Band (2.0) AND Volatilty Spike
                # We interpret "Volatilty Spike" as ATR > 3% of price (High noise)
                current_atr_pct = row['atr'] / curr_price if curr_price > 0 else 0
                
                if curr_price < row['bb_lower'] and current_atr_pct > 0.03:
                    return 'BUY'
                    
            # 2. STANDARD MODE (AAMR Entry)
            else:
                if is_bull_trend and is_oversold:
                    return 'BUY'
                if not is_bull_trend and high_vol and row['rsi'] < self.rsi_buy:
                    return 'BUY'
                
        # --- SELL SIGNAL ---
        elif current_position_avg_price is not None:
            pct_change = (curr_price - current_position_avg_price) / current_position_avg_price
            
            # --- FLASH CRASH EXIT (Trailing Stop) ---
            if mode == 'flash' and highest_price_since_entry:
                # Expert Exit: Peak - (2.0 * ATR)
                # If ATR is missing, fallback to 10%
                current_atr = row['atr']
                if pd.isna(current_atr) or current_atr == 0:
                    stop_distance = highest_price_since_entry * 0.10
                else:
                    stop_distance = 2.0 * current_atr
                
                stop_price = highest_price_since_entry - stop_distance
                
                if curr_price < stop_price:
                    return 'SELL'
                    
                # Hard Stop Loss checking is below (acts as backup)
                
            # --- STANDARD EXIT ---
            else: 
                # 1. Take Profit
                if is_bull_trend:
                    # Let it run! Only sell if extreme or huge gain
                    if pct_change > 0.50 or is_extreme_overbought:
                        return 'SELL'
                    if not is_bull_trend: # Trend broke
                        return 'SELL'
                else:
                    # Bear Mode: Scalp
                    target = 0.15
                    if high_vol: target = 0.20
                    if pct_change >= target:
                        return 'SELL'
            
            # 2. Hard Stop Loss (Universal Safety Net)
            if pct_change <= -0.10:
                return 'SELL'
                
        return 'HOLD'
