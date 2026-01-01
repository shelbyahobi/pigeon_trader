import pandas as pd
from .base import BaseStrategy

class DipBuyStrategy(BaseStrategy):
    def __init__(self, dip_threshold=0.5, take_profit=0.2, stop_loss=0.2):
        super().__init__("Dip Buy")
        self.dip_threshold = dip_threshold
        self.take_profit = take_profit
        self.stop_loss = stop_loss

    def run(self, df):
        cash = self.capital
        holdings = 0
        entry_price = 0
        equity_curve = []
        
        ATH = 0
        
        for date, row in df.iterrows():
            price = row['price']
            
            # Update ATH
            if price > ATH: ATH = price
            
            # Logic
            if holdings == 0:
                # Look to buy
                if ATH > 0 and price < (self.dip_threshold * ATH):
                    # BUY signal
                    holdings = cash / price
                    entry_price = price
                    cash = 0
            else:
                # Look to sell
                pnl_pct = (price - entry_price) / entry_price
                
                # Take Profit
                if pnl_pct >= self.take_profit:
                    cash = holdings * price
                    holdings = 0
                    entry_price = 0
                # Stop Loss
                elif pnl_pct <= -self.stop_loss:
                    cash = holdings * price
                    holdings = 0
                    entry_price = 0
                    
            # Track Equity
            current_equity = cash + (holdings * price)
            equity_curve.append(current_equity)

        # Handle empty DataFrames
        if not equity_curve:
            return 0.0, pd.Series()

        final_equity = equity_curve[-1]
        roi = ((final_equity - self.capital) / self.capital) * 100
        return roi, pd.Series(equity_curve, index=df.index)
