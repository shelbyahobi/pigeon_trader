import random
import pandas as pd

# --- CONFIG ---
# --- CONFIG ---
NUM_SIMULATIONS = 5  # Specific 5-token demo
CAPITAL_TOTAL = 100.0
CAPITAL_PER_TOKEN = CAPITAL_TOTAL / NUM_SIMULATIONS
# Simulate ~9 months (270 days)
SIMULATION_DAYS = 270 
PRICE_INTERVAL_HOURS = 4 # Less granular for long timeframe
STEPS = (SIMULATION_DAYS * 24) // PRICE_INTERVAL_HOURS

def generate_price_curve():
    """
    Generates a random price curve simulating different token scenarios for 2025.
    Start Price is always 1.0 (normalized).
    """
    prices = [1.0]
    current_price = 1.0
    
    # Determine scenario (Weighted for realism: Most fail, few moon)
    # Scenarios: 'rug' (goes to 0), 'dump' (slow bleed), 'pump_dump' (spike then 0), 'moon' (10x+), 'volatile' (up/down)
    scenario = random.choices(
        ['rug', 'dump', 'pump_dump', 'moon', 'volatile'],
        weights=[30, 30, 20, 10, 10], # 10% chance of mooning
        k=1
    )[0]
    
    for _ in range(STEPS):
        change_pct = 0
        
        if scenario == 'rug':
             # High chance of dying
             if random.random() < 0.02: change_pct = -0.99
             else: change_pct = random.gauss(0, 0.05)
             
        elif scenario == 'dump':
            # Trend down
            change_pct = random.gauss(-0.01, 0.05)
            
        elif scenario == 'pump_dump':
            # Spike early then crash
            if len(prices) < STEPS * 0.1: change_pct = random.gauss(0.1, 0.1) # Pump
            else: change_pct = random.gauss(-0.05, 0.1) # Dump
            
        elif scenario == 'moon':
            # Trend up
            change_pct = random.gauss(0.01, 0.05) 
            
        elif scenario == 'volatile':
            # Wild swings
            change_pct = random.gauss(0, 0.15)

        # Update price
        current_price = current_price * (1 + change_pct)
        if current_price < 0.000001: current_price = 0.000001
        prices.append(current_price)
        
    return prices, scenario

def run_strategy(prices, tp_mult, sl_mult, hold_days=None):
    """
    Runs a strategy on a price curve.
    Returns: (profit_usd, exit_step, exit_reason)
    """
    entry_price = prices[0]
    hold_steps = (hold_days * 24) // PRICE_INTERVAL_HOURS if hold_days else STEPS
    
    for i, price in enumerate(prices):
        if i == 0: continue
        if i >= hold_steps:
             # Time exit
             mult = price / entry_price
             pnl = (mult * CAPITAL_PER_TOKEN) - CAPITAL_PER_TOKEN
             return pnl, i, 'TIME'
        
        mult = price / entry_price
        
        # Take Profit
        if tp_mult and mult >= tp_mult:
            pnl = (mult * CAPITAL_PER_TOKEN) - CAPITAL_PER_TOKEN
            return pnl, i, 'TP'
            
        # Stop Loss
        if sl_mult and mult <= sl_mult:
            pnl = (mult * CAPITAL_PER_TOKEN) - CAPITAL_PER_TOKEN
            return pnl, i, 'SL'
            
    # HODL until end of simulation
    final_mult = prices[-1] / entry_price
    pnl = (final_mult * CAPITAL_PER_TOKEN) - CAPITAL_PER_TOKEN
    return pnl, len(prices), 'HODL'

def main():
    print(f"--- BACKTEST DEMO: 5 TOKENS in 2025 ---")
    print(f"Capital: ${CAPITAL_TOTAL} ($20/token) | Duration: {SIMULATION_DAYS} Days")
    
    strategies = [
        {'name': '2x / -20%',   'tp': 2.0, 'sl': 0.8, 'hold': None},
        {'name': '3x / -30%',   'tp': 3.0, 'sl': 0.7, 'hold': None},
        {'name': 'Hold 90 Days','tp': None,'sl': None,'hold': 90}
    ]
    
    # Generate 5 random token names for flavor
    token_names = [f"TOKEN_{i+1}_{random.choice(['PEPE', 'DOGE', 'MOON', 'SAFE', 'ELON'])}" for i in range(NUM_SIMULATIONS)]
    
    # Generate price curves
    market_data = []
    print("\nGenerated Market Scenarios:")
    for name in token_names:
        prices, scenario = generate_price_curve()
        market_data.append((prices, scenario))
        end_price = prices[-1]
        print(f"  {name}: {scenario.upper()} (Final Price: {end_price:.4f}x)")

    results = []
    
    for strat in strategies:
        strat_pnl = []
        wins = 0
        
        # print(f"\nRunning {strat['name']}...")
        for (prices, scenario), token_name in zip(market_data, token_names):
            pnl, steps, reason = run_strategy(prices, strat['tp'], strat['sl'], strat['hold'])
            strat_pnl.append(pnl)
            if pnl > 0: wins += 1
            # print(f"  {token_name}: ${pnl:.2f} ({reason})")
            
        total_pnl = sum(strat_pnl)
        roi_pct = (total_pnl / CAPITAL_TOTAL) * 100
        win_rate = (wins / NUM_SIMULATIONS) * 100
        
        results.append({
            'Strategy': strat['name'],
            'Net Profit': f"${total_pnl:.2f}",
            'ROI %': f"{roi_pct:.2f}%",
            'Win Rate': f"{win_rate:.0f}%"
        })

    # Display Report
    df = pd.DataFrame(results)
    print("\n=== STRATEGY COMPARISON ===")
    print(df.to_string(index=False))
    print("\n(Note: Simulated data based on 2025 realistic volatility scenarios)")

if __name__ == "__main__":
    main()
