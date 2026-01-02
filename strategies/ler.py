from .base import BaseStrategy
import pandas as pd
import numpy as np

class LERStrategy(BaseStrategy):
    def __init__(self, vol_lookback=20, vol_rank_lookback=180, atr_period=14):
        super().__init__("Liquidity Erosion Reversal")
        self.vol_lookback = vol_lookback
        self.vol_rank_lookback = vol_rank_lookback
        self.atr_period = atr_period

    def calculate_indicators(self, df):
        # 1. Volatility Regime (Proxy for Parkinson)
        # We use annualized std dev of log returns as proxy since we lack High/Low
        df['log_ret'] = np.log(df['price'] / df['price'].shift(1))
        df['volatility'] = df['log_ret'].rolling(window=self.vol_lookback).std() * np.sqrt(365)
        
        # 2. Volatility Rank (Percentile over 180 days)
        df['vol_rank'] = df['volatility'].rolling(window=self.vol_rank_lookback).rank(pct=True)
        
        # 3. ATR (For Sizing & Trailing)
        df['tr'] = df['price'].diff().abs()
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        
        # 4. Volume Divergence Proxy
        # Price making Lower Low vs Volume Neutral/Higher?
        # We simplify to: "Volume stable/rising while Price drops slowly"
        if 'total_volume' in df.columns:
            df['vol_ma'] = df['total_volume'].rolling(window=20).mean()
            df['vol_stable'] = df['total_volume'] > (0.8 * df['vol_ma']) # Volume not dying
        else:
            df['vol_stable'] = True
            
        # 5. Drawdown (Context)
        df['year_high'] = df['price'].rolling(window=365, min_periods=50).max()
        df['drawdown'] = (df['year_high'] - df['price']) / df['year_high']
        
        return df

    def run(self, df):
        df = self.calculate_indicators(df.copy())
        
        capital = 1000.0
        position = None # {entry, amount, initial_size, size_remaining, peak_price, days_held}
        equity = []
        
        start_idx = self.vol_rank_lookback + 20
        if len(df) < start_idx: start_idx = 50
        
        # Pre-fill
        for _ in range(start_idx): equity.append(1000.0)
            
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['price']
            
            # --- MANAGE POSITION ---
            if position:
                position['days_held'] += 1
                
                # Update Peak for Trailing Stop
                if price > position['peak_price']:
                    position['peak_price'] = price
                    
                # 1. Take Profit (Asymmetric Scale Out)
                # Targets: +40% (sell 25%), +80% (sell 25%), +150% (sell 50%)
                roi_pct = (price - position['entry']) / position['entry']
                
                # We need to track realized gains to add to 'capital'
                # Simplification: We assume we sell a portion of the 'amount'
                
                # TP 1: +40%
                if roi_pct >= 0.40 and not position.get('tp1_hit'):
                    # Sell 25% of ORIGINAL size
                    sell_amt = position['initial_amount'] * 0.25
                    if position['amount'] >= sell_amt:
                        position['amount'] -= sell_amt
                        capital += sell_amt * price
                        position['tp1_hit'] = True
                        
                # TP 2: +80%
                if roi_pct >= 0.80 and not position.get('tp2_hit'):
                    sell_amt = position['initial_amount'] * 0.25
                    if position['amount'] >= sell_amt:
                        position['amount'] -= sell_amt
                        capital += sell_amt * price
                        position['tp2_hit'] = True
                        
                # TP 3: +150% (Sell Rest)
                if roi_pct >= 1.50:
                    capital += position['amount'] * price
                    position = None
                    equity.append(capital)
                    continue

                # 2. Trailing Stop (Active after +40%?)
                # Expert: "Once +40% profit reached, activate ATR-based trailing stop"
                if position.get('tp1_hit', False):
                    # Stop = Current_Price - (2.5 * ATR_14)
                    # Actually Expert said: "Adjusts daily". We assume trailing from High or Current?
                    # Usually Trailing Stop trails the Peak.
                    stop_price = position['peak_price'] - (2.5 * row['atr'])
                    
                    if price < stop_price:
                        # SELL REMAINING
                        capital += position['amount'] * price
                        position = None
                        equity.append(capital)
                        continue
                        
                # 3. Hard Stop Loss (-15%)
                if roi_pct <= -0.15:
                    capital += position['amount'] * price
                    position = None
                    equity.append(capital)
                    continue
                    
                # 4. Time Stop (120 days < 20% gain)
                if position['days_held'] >= 120 and roi_pct < 0.20:
                    capital += position['amount'] * price
                    position = None
                    equity.append(capital)
                    continue

            # --- ENTRY LOGIC ---
            else:
                # 1. Volatility Regime Shift (Lowest Quartile)
                # "20-day Vol drops to lowest quartile of past 180 days"
                is_vol_compressed = row['vol_rank'] < 0.25
                
                # 2. Drawdown Context (>60% from High)
                is_deep_value = row['drawdown'] > 0.60
                
                # 3. Volume filter
                is_vol_healthy = row['vol_stable']
                
                if is_vol_compressed and is_deep_value and is_vol_healthy:
                    # BUY
                    # Inverse Vol Sizing
                    # Size = (Capital * 1% Risk) / (ATR * Price * 1.5)
                    # Simplified: Risk 2% of equity, stop is 15%. So Size = 2% / 15% = ~13% of equity
                    # Expert Formula: Position Size = (Equity * 0.01) / (Dist to Stop?)
                    # Let's use fixed 15% of capital for backtest consistency vs others
                    
                    bet_size_cash = capital * 0.15 
                    if bet_size_cash < 10: bet_size_cash = capital # All in if low
                    
                    amount = bet_size_cash / price
                    capital -= bet_size_cash
                    
                    position = {
                        'entry': price,
                        'amount': amount,
                        'initial_amount': amount,
                        'peak_price': price,
                        'days_held': 0,
                        'tp1_hit': False,
                        'tp2_hit': False
                    }

            # Track Equity
            val = capital
            if position:
                val += position['amount'] * price
            equity.append(val)
            
        roi = ((equity[-1] - 1000)/1000) * 100
        return roi, pd.Series(equity, index=df.index)
