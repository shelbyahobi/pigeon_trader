import pandas as pd
import matplotlib.pyplot as plt
import re

LOG_FILE = 'trade_log.txt'

def parse_log():
    trades = []
    
    try:
        with open(LOG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                # Regex for BUY
                # Supports old format: Bought 0x... at $1.23 USD
                # Supports new format: Bought TOKEN (0x...) at $1.23 USD
                if '[PAPER BUY]' in line:
                    # Try new format first
                    match_new = re.search(r'Bought (\w+) \((0x[a-fA-F0-9]+)\) at \$([\d\.]+) USD', line)
                    if match_new:
                        trades.append({
                            'type': 'buy',
                            'symbol': match_new.group(1),
                            'addr': match_new.group(2),
                            'price': float(match_new.group(3))
                        })
                        continue
                        
                    # Try old format
                    match_old = re.search(r'Bought (0x[a-fA-F0-9]+) at \$([\d\.]+) USD', line)
                    if match_old:
                        trades.append({
                            'type': 'buy',
                            'symbol': 'UNKNOWN',
                            'addr': match_old.group(1),
                            'price': float(match_old.group(2))
                        })
                        continue

                # Regex for SELL
                # Format: [PAPER SELL] TYPE: SYMBOL at $PRICE (MULTx)
                elif '[PAPER SELL]' in line:
                    match_sell = re.search(r'PAPER SELL\] (.*): (\w+) at \$([\d\.]+) \(([\d\.]+)x\)', line)
                    if match_sell:
                        action_type = match_sell.group(1) # TAKE PROFIT / STOP LOSS
                        symbol = match_sell.group(2)
                        price = float(match_sell.group(3))
                        mult = float(match_sell.group(4))
                        profit_pct = (mult - 1) * 100
                        
                        trades.append({
                            'type': 'sell',
                            'symbol': symbol,
                            'price': price,
                            'profit_pct': profit_pct,
                            'action': action_type
                        })

    except FileNotFoundError:
        print(f"File {LOG_FILE} not found.")
        return []

    return trades

def visualize():
    trades = parse_log()
    df = pd.DataFrame(trades)
    
    if df.empty:
        print("No trades found to visualize.")
        return

    print(f"Parsed {len(df)} trade events.")
    print(df.head())

    sells = df[df['type'] == 'sell']
    if not sells.empty:
        # Plot Cumulative Profit
        plt.figure(figsize=(10, 6))
        sells['profit_pct'].cumsum().plot(kind='line', title='Cumulative Profit % (Paper Trading)', marker='o')
        plt.xlabel('Trade #')
        plt.ylabel('Cumulative Profit %')
        plt.grid(True)
        plt.savefig('profits.png')
        print("\nProfit chart saved to 'profits.png'.")
        
        # Metrics
        total_trades = len(sells)
        wins = len(sells[sells['profit_pct'] > 0])
        win_rate = (wins / total_trades) * 100
        avg_profit = sells['profit_pct'].mean()
        
        print("\n--- PERFORMANCE METRICS ---")
        print(f"Total Completed Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Average Profit per Trade: {avg_profit:.2f}%")
        print(f"Best Trade: +{sells['profit_pct'].max():.2f}%")
        print(f"Worst Trade: {sells['profit_pct'].min():.2f}%")
        
    else:
        print("No completed SELL trades found yet.")
        if not df[df['type']=='buy'].empty:
            print(f"Found {len(df[df['type']=='buy'])} active BUY positions.")

if __name__ == "__main__":
    visualize()
