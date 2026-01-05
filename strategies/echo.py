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
        # Calculate Rolling Rank (Percentile) of current width vs last 180 days
        # Use pandas rolling rank
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
            # Use iloc[-1] > [-2] > [-3] in logic? No, easier to map here.
            v = df['total_volume']
            df['vol_rising'] = (v > v.shift(1)) & (v.shift(1) > v.shift(2))
            
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
            
            # --- NEW EXIT LOGIC (Fix #2) ---
            import time
            pnl_pct = (price - current_pos_price) / current_pos_price
            
            # 1. Hard Profit Target (+25%) - Secure the bag
            if pnl_pct > 0.25:
                return 'SELL'
                
            # 2. Time Stop (7 days if < 10% profit) - Don't hold dead money
            entry_timestamp = context.get('entry_timestamp', time.time())
            # Default to now (0 days held) if missing, to be safe
            if not entry_timestamp: entry_timestamp = time.time()
            
            days_held = (time.time() - float(entry_timestamp)) / 86400
            
            if days_held > 7 and pnl_pct < 0.10:
                print(f"  --> TIME STOP: Held {days_held:.1f} days with low profit ({pnl_pct:.1%})")
                return 'SELL'

            # 3. Trailing Stop
            atr = row['atr'] if not pd.isna(row['atr']) else price * 0.05
            
            # Highest price since entry is tracked by bot
            stop_price = highest_price - (1.5 * atr)
            
            # Hard Stop (-15%)
            hard_stop = current_pos_price * 0.85
            
            if price < max(stop_price, hard_stop):
                return 'SELL'
                
        # --- BUY LOGIC ---
        # --- BUY LOGIC ---
        else:
            # 1. Context Filters (Passed via context dict)
            btc_bullish = context.get('btc_bullish', True) # Default True if check fails
            funding_ok = context.get('funding_ok', True)   # Default True
            
            # TEMPORARY: Comment out regime filters for testing as requested
            # if not btc_bullish: return 'HOLD' # "Regime Awareness"
            # if not funding_ok: return 'HOLD'  # "No Blind Spot"
            
            # 2. Hardened Logic: Weighted Scoring System (0-100 points)
            score = 0
            
            # A. Deep Value (0-40 points)
            drawdown = row['drawdown'] if not pd.isna(row['drawdown']) else 0
            if drawdown > 0.70:
                score += 40
            elif drawdown > 0.60:
                score += 30
            elif drawdown > 0.50:
                score += 20
            elif drawdown > 0.40:
                score += 10
            
            # B. Volatility Squeeze (0-35 points)
            bb_rank = row['bb_width_rank'] if not pd.isna(row['bb_width_rank']) else 1.0
            if bb_rank < 0.15:
                score += 35
            elif bb_rank < 0.25:
                score += 25
            elif bb_rank < 0.35:
                score += 15
            elif bb_rank < 0.50:
                score += 5
            
            # C. Volume Signal (0-25 points)
            vol_signal = row.get('vol_signal', False)
            if vol_signal:
                score += 25
            else:
                # Partial credit for spike without rising trend
                vol_spike = row.get('vol_spike', False)
                if vol_spike:
                    score += 12
            
            # Debug Logic: Log Score to bot.log
            # We print because nohup redirects stdout to bot.log
            symbol = context.get('symbol', 'UNKNOWN')
            from datetime import datetime
            
            # Only log interesting scores to avoid spam
            if score > 20: 
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {symbol}: Score={score:.0f} (DD:{drawdown:.0%}, BB:{bb_rank:.0%}, Vol:{vol_signal})")

            # BUY if score >= 45 (Testing Threshold)
            if score >= 45:
                print(f"  --> BUY TRIGGERED for {symbol} (Score {score})")
                return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        # 1. Pre-calculate indicators (Simulate "what the bot sees")
        df = self.calculate_indicators(df.copy())
        
        capital = self.capital
        position = None # {entry, amount, peak_price}
        equity_curve = []
        
        # Start after warm-up period (need ~180 days for bb_rank)
        start_idx = 180
        if len(df) < start_idx:
             # Handle short history gracefully
             start_idx = 20
        
        # Fill equity for warmup
        for _ in range(start_idx): equity_curve.append(capital)
            
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['price']
            date = df.index[i]
            
            # --- MANAGE POSITION ---
            if position:
                # Update Peak
                if price > position['peak_price']:
                    position['peak_price'] = price
                    
                # 1. Take Profit (Scaled) - Simplified for Backtest
                # In live bot, we might scale out. Here let's model a simple "Trailing Stop" based exit.
                # Strategy: Hold until Trailing Stop or Hard Stop hits.
                
                # Check Stops
                atr = row['atr'] if not pd.isna(row['atr']) else price * 0.05
                stop_price = position['peak_price'] - (1.5 * atr)
                hard_stop = position['entry'] * 0.85
                
                exit_price = max(stop_price, hard_stop)
                
                if price < exit_price:
                    # SELL SIGNAL
                    capital = position['amount'] * price
                    position = None
                    equity_curve.append(capital)
                    continue
                    
            # --- ENTRY LOGIC ---
            else:
                # Use EXACT same Scoring Logic as get_signal
                score = 0
                
                # A. Deep Value
                drawdown = row['drawdown'] if not pd.isna(row['drawdown']) else 0
                if drawdown > 0.70: score += 40
                elif drawdown > 0.60: score += 30
                elif drawdown > 0.50: score += 20
                elif drawdown > 0.40: score += 10
                
                # B. Squeeze
                bb_rank = row['bb_width_rank'] if not pd.isna(row['bb_width_rank']) else 1.0
                if bb_rank < 0.15: score += 35
                elif bb_rank < 0.25: score += 25
                elif bb_rank < 0.35: score += 15
                elif bb_rank < 0.50: score += 5
                
                # C. Volume
                vol_signal = row.get('vol_signal', False)
                if vol_signal: score += 25
                else:
                    if row.get('vol_spike', False): score += 12
                    
                # Threshold
                if score >= 45:
                    # BUY
                    position = {
                        'entry': price,
                        'amount': capital / price,
                        'peak_price': price
                    }
                    capital = 0 # All in
                    
            # Track Equity
            val = capital
            if position:
                val = position['amount'] * price
            equity_curve.append(val)
            
        # Calc Stats
        final_val = equity_curve[-1]
        roi = ((final_val - self.capital) / self.capital) * 100
        return roi, pd.Series(equity_curve, index=df.index)
