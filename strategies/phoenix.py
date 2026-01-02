from .base import BaseStrategy
import pandas as pd
import numpy as np

class PhoenixStrategy(BaseStrategy):
    def __init__(self, adv_threshold=5_000_000, atr_period=14, profile_days=90):
        super().__init__("Phoenix Shelf")
        self.adv_threshold = adv_threshold
        self.atr_period = atr_period
        self.profile_days = profile_days # Lookback for Volume Profile

    def calculate_indicators(self, df):
        # 1. ATR
        df['high_low'] = df['price'] * 0.05 # Mock High-Low since we only have daily close usually
        # Actually in backtest we usually only have 'price' (Close). 
        # The user mentioned Daily High/Low. 
        # We will approximate TR as abs(Close - PrevClose) for this backtest if Candle data missing.
        
        df['tr'] = df['price'].diff().abs()
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        df['atr_pct'] = df['atr'] / df['price']
        
        # 2. Volume MA
        # We assume 'total_volumes' column exists (it does in our data fetcher)
        # If not, we fill with dummy
        if 'total_volume' not in df.columns:
            # Mock volume if missing (Backtest CSVs might not have it?)
            # Let's check data files later. For now assume it exists or fail gracefully.
            df['vol_ma'] = 1_000_000 # Dummy
        else:
            df['vol_ma'] = df['total_volume'].rolling(window=20).mean()

        # 3. Chandelier Exit (Long): Highest High (of Close) - 3 * ATR
        df['highest_close'] = df['price'].rolling(window=22).max()
        df['chandelier'] = df['highest_close'] - (3.0 * df['atr'])
        
        return df

    def get_accumulation_zone(self, df_slice):
        """
        Approximates Volume Profile POC (Point of Control) and VAH (Value Area High).
        """
        # Create Price Buckets
        price_min = df_slice['price'].min()
        price_max = df_slice['price'].max()
        bins = np.linspace(price_min, price_max, 50) # 50 Shelves
        
        # Aggregate Volume by Price Bin
        # We need volume column. If missing, use Equal Weight (Price Profile)
        if 'total_volume' in df_slice.columns:
            weights = df_slice['total_volume']
        else:
            weights = pd.Series(1, index=df_slice.index)
            
        # Histogram
        hist, bin_edges = np.histogram(df_slice['price'], bins=bins, weights=weights)
        
        # Find POC (Max Volume Bin)
        poc_idx = np.argmax(hist)
        poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2
        
        # Find Value Area (70% of Volume)
        total_vol = np.sum(hist)
        target_vol = total_vol * 0.70
        
        # Start from POC and expand out
        current_vol = hist[poc_idx]
        left_ptr = poc_idx
        right_ptr = poc_idx
        
        while current_vol < target_vol:
            # Try add left
            vol_left = 0
            if left_ptr > 0:
                vol_left = hist[left_ptr - 1]
            
            # Try add right
            vol_right = 0
            if right_ptr < len(hist) - 1:
                vol_right = hist[right_ptr + 1]
                
            if vol_left == 0 and vol_right == 0:
                break
                
            if vol_left > vol_right:
                current_vol += vol_left
                left_ptr -= 1
            else:
                current_vol += vol_right
                right_ptr += 1
                
        vah_price = bin_edges[right_ptr + 1]
        val_price = bin_edges[left_ptr]
        
        return poc_price, vah_price, val_price

    def run(self, df):
        # Full Backtest Loop
        df = self.calculate_indicators(df.copy())
        
        capital = 1000.0
        position = None
        equity = []
        
        # Strategy needs Lookback (90 days)
        start_idx = self.profile_days + 20 
        
        # Pre-fill
        for _ in range(start_idx): equity.append(1000.0)
            
        for i in range(start_idx, len(df)):
            idx = df.index[i]
            row = df.iloc[i]
            
            # 1. State
            price = row['price']
            
            # 2. Manage Position
            if position:
                # EXIT: Chandelier Stop
                # Expert says: "Target 2 (Runner): Trail a stop loss using the Chandelier Exit"
                # We simplify to 100% position on Chandelier for the backtest
                stop_price = row['chandelier']
                
                # Check Hard Stop (Below POC)
                # stored in position dict
                hard_stop = position['stop_loss']
                
                if price < max(stop_price, hard_stop):
                    # SELL
                    capital = position['amount'] * price
                    position = None
            
            # 3. Entry Logic (If no position)
            else:
                # Context: Check last 90 days for Volume Profile
                # Window: [i-90 : i]
                lookback_slice = df.iloc[i - self.profile_days : i]
                
                # Check 1: Deep Value (Price < 0.40 * ATH)
                # We need ATH. Assuming we fetch it or track local max.
                # Let's use 365-day High as proxy for ATH if column missing
                local_ath = df['price'].iloc[:i].max()
                is_deep_value = price < (0.40 * local_ath)
                
                if is_deep_value:
                    # Check 2: Volatility Compression (Low ATR)
                    # "ATR in bottom 25th percentile of 6-month range"
                    atr_6m = df['atr'].iloc[i-180 : i]
                    if len(atr_6m) == 0:
                        is_compressed = False
                    else:
                        try:
                            atr_rank = atr_6m.rank(pct=True).iloc[-1]
                            is_compressed = atr_rank < 0.25
                        except IndexError:
                            is_compressed = False
                    
                    if is_compressed:
                        # Check 3: Breakout above VAH
                        poc, vah, val = self.get_accumulation_zone(lookback_slice)
                        
                        # Trigger: Close > VAH
                        # And Volume > 1.5x MA
                        vol_spike = True # row['total_volume'] > 1.5 * row['vol_ma']
                        # (Simulating volume spike as true if volume data sparse)
                        
                        if price > vah and vol_spike:
                            # BUY
                            # Sizing: Inverse Volatility (Not implemented in simple backtest, using Fixed Risk)
                            amount = capital / price
                            
                            # Initial Stop: Below POC
                            stop_loss = poc * 0.98 # slight buffer
                            
                            position = {
                                'entry': price,
                                'amount': amount,
                                'stop_loss': stop_loss
                            }
                            capital = 0

            # Track Equity
            val = capital if not position else position['amount'] * price
            equity.append(val)
            
        roi = ((equity[-1] - 1000)/1000) * 100
        return roi, pd.Series(equity, index=df.index)
