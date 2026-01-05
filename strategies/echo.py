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
        self.capital = 1000.0 # Default Capital for Backtest

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
        Implements 'Lifecycle Exit Framework' for Production Safety.
        """
        if len(df) < 20: return 'HOLD' # Use 20 for logic, handled by df length check
        
        df = self.calculate_indicators(df.copy())
        row = df.iloc[-1]
        price = row['price']
        symbol = context.get('symbol', 'UNKNOWN')
        
        # --- 1. SELL LOGIC (PRIORITY) ---
        if current_pos_price:
            import time
            from datetime import datetime
            
            # --- CONTEXT ---
            entry_timestamp = context.get('entry_timestamp', time.time())
            if not entry_timestamp: entry_timestamp = time.time()
            
            days_held = (time.time() - float(entry_timestamp)) / 86400
            pnl_pct = (price - current_pos_price) / current_pos_price
            
            # ATR Handling
            atr = row['atr'] if not pd.isna(row['atr']) else price * 0.05
            if not highest_price: highest_price = current_pos_price
            
            # --- DIAGNOSTICS ---
            # Print heartbeat to prove we are evaluating exits
            print(f"[{datetime.now().strftime('%H:%M:%S')}] EXIT CHECK {symbol}: PnL {pnl_pct:+.2%} | Held {days_held:.1f}d | High ${highest_price:.2f}")

            # --- LIFECYCLE STAGES ---
            exit_reason = None
            
            # STAGE 1: INFANCY (0-3 Days) -> SURVIVE
            if days_held < 3:
                # Wide Stops Only
                hard_stop = current_pos_price * 0.90 # -10% Hard Stop
                vol_stop = highest_price - (2.0 * atr) # Loose Trailing
                
                if price < hard_stop: exit_reason = f"Infancy Hard Stop (-10%)"
                elif price < vol_stop: exit_reason = f"Infancy Vol Stop (-2 ATR)"
                
            # STAGE 2: ADOLESCENCE (3-7 Days) -> PROVE WORTH
            elif days_held < 7:
                # Must be profitable by now
                if pnl_pct < 0: exit_reason = f"Adolescence Time Stop (PnL < 0%)"
                
                # Tighten Stops
                vol_stop = highest_price - (1.5 * atr)
                if price < vol_stop: exit_reason = f"Adolescence Trailing (-1.5 ATR)"
                
                # Take Profit?
                if pnl_pct > 0.15: exit_reason = f"Adolescence Profit Target (+15%)"
                
            # STAGE 3: MATURITY (7-14 Days) -> HARVEST
            elif days_held < 14:
                # Must be winning significantly
                if pnl_pct < 0.05: exit_reason = f"Maturity Time Stop (PnL < 5%)"
                
                # Very Tight Stops
                vol_stop = highest_price - (1.0 * atr)
                if price < vol_stop: exit_reason = f"Maturity Trailing (-1.0 ATR)"
                
            # STAGE 4: EXPIRY (14+ Days) -> RECYCLE
            else:
                exit_reason = f"Expiry Force Exit (>14 Days)"
            
            # GLOBAL: Hard Profit Target (Moonbag)
            if pnl_pct > 0.30:
                exit_reason = f"Global Profit Target (+30%)"
            
            # --- EXECUTION ---
            if exit_reason:
                print(f"  --> SELL SIGNAL for {symbol}: {exit_reason}")
                return 'SELL'
            else:
                # Log why we held (Verbose)
                # print(f"  -> HOLDing {symbol} (No exit condition met)")
                return 'HOLD'

        # --- 2. BUY LOGIC ---
        else:
            # Context Filters
            btc_bullish = context.get('btc_bullish', True)
            funding_ok = context.get('funding_ok', True)
            
            # Calculate Score
            score = 0
            
            # A. Deep Value (0-40)
            drawdown = row['drawdown'] if not pd.isna(row['drawdown']) else 0
            if drawdown > 0.70: score += 40
            elif drawdown > 0.60: score += 30
            elif drawdown > 0.50: score += 20
            elif drawdown > 0.40: score += 10
            
            # B. Squeeze (0-35)
            bb_rank = row['bb_width_rank'] if not pd.isna(row['bb_width_rank']) else 1.0
            if bb_rank < 0.15: score += 35
            elif bb_rank < 0.25: score += 25
            elif bb_rank < 0.35: score += 15
            elif bb_rank < 0.50: score += 5
            
            # C. Volume (0-25)
            vol_signal = row.get('vol_signal', False)
            if vol_signal: score += 25
            elif row.get('vol_spike', False): score += 12
            
            # Debug Logic
            if score > 20: 
                # Avoid spamming logs unless interesting
                # print(f"[{symbol}] Score={score}")
                pass

            # BUY Trigger
            if score >= 45:
                print(f"  --> BUY TRIGGERED for {symbol} (Score {score})")
                return 'BUY'
                
        return 'HOLD'

    def run(self, df):
        """
        Backtest the Echo strategy on historical data
        Returns: (ROI, equity_series)
        """
        # 1. Pre-calculate indicators
        df = self.calculate_indicators(df.copy())
        
        capital = self.capital
        position = None  # {entry, amount, peak_price}
        equity_curve = []
        
        # Start after warm-up period
        start_idx = 180
        if len(df) < start_idx:
            start_idx = 20
        
        # Fill equity for warmup
        for _ in range(start_idx):
            equity_curve.append(capital)
        
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            price = row['price']
            
            # --- MANAGE POSITION ---
            if position:
                # Update Peak
                if price > position['peak_price']:
                    position['peak_price'] = price
                
                # Check Stops
                atr = row['atr'] if not pd.isna(row['atr']) else price * 0.05
                stop_price = position['peak_price'] - (1.5 * atr)
                hard_stop = position['entry'] * 0.85
                
                exit_price = max(stop_price, hard_stop)
                
                if price < exit_price:
                    # SELL
                    capital += position['amount'] * price
                    position = None
            
            # --- ENTRY LOGIC ---
            else:
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
                    vol_spike = row.get('vol_spike', False)
                    if vol_spike:
                        score += 12
                
                # BUY if score >= 45
                if score >= 45 and capital > 10:
                    bet_size = capital * 0.05  # 5% position
                    amount = bet_size / price
                    position = {
                        'entry': price,
                        'amount': amount,
                        'peak_price': price
                    }
                    capital -= bet_size
            
            # Update equity curve
            position_value = position['amount'] * price if position else 0
            equity = capital + position_value
            equity_curve.append(equity)
        
        # Close any open position at end
        if position:
            final_price = df.iloc[-1]['price']
            capital += position['amount'] * final_price
        
        # Calculate ROI
        roi = (capital - self.capital) / self.capital
        equity_series = pd.Series(equity_curve, index=df.index)
        
        return roi, equity_series
