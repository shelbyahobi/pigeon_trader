import pandas as pd
from .base import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, rsi_period=14, buy_threshold=30, sell_threshold=70, stop_loss=0.10):
        super().__init__("RSI Mean-Reversion")
        self.rsi_period = rsi_period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.stop_loss = stop_loss

    def calculate_rsi(self, series):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def run(self, df):
        df = df.copy()
        df['rsi'] = self.calculate_rsi(df['price'])
        
        cash = self.capital
        holdings = 0
        entry_price = 0
        equity_curve = []
        
        for date, row in df.iterrows():
            price = row['price']
            rsi = row['rsi']
            
            if pd.isna(rsi):
                equity_curve.append(cash + (holdings * price))
                continue
            
            if holdings == 0:
                # Buy Signal: RSI < 30 (Oversold)
                if rsi < self.buy_threshold:
                    holdings = cash / price
                    entry_price = price
                    cash = 0
            else:
                # Sell Signal: RSI > 70 (Overbought) OR Stop Loss
                pnl_pct = (price - entry_price) / entry_price
                
                if rsi > self.sell_threshold:
                    # Take Profit (Mean Reversion)
                    cash = holdings * price
                    holdings = 0
                    entry_price = 0
                elif pnl_pct <= -self.stop_loss:
                    # Stop Loss
                    cash = holdings * price
                    holdings = 0
                    entry_price = 0
                    
            equity_curve.append(cash + (holdings * price))
            
        if not equity_curve:
             return 0.0, pd.Series()
             
        final_equity = equity_curve[-1]
        roi = ((final_equity - self.capital) / self.capital) * 100
        return roi, pd.Series(equity_curve, index=df.index)
