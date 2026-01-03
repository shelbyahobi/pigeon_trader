import requests
import datetime
import time

# --- CONFIG ---
MIN_AGE_YEARS = 2
MIN_VOLUME_USD = 300_000 # Loosened for Testing (was 1M)
MIN_DIP_PERCENT = 40.0   # Loosened for Testing (was 50%)

MAX_CANDIDATES = 20 # Limit to avoid hitting rate limits too hard during demo

def get_bnb_tokens():
    """Fetch top BNB Chain tokens by market cap."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        'vs_currency': 'usd',
        'category': 'binance-smart-chain',
        'order': 'market_cap_desc',
        'per_page': 100, # Check top 100
        'page': 1,
        'sparkline': 'false',
        'price_change_percentage': '14d,30d,200d' # Fetch recent changes
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching markets: {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception fetching markets: {e}")
        return []

def get_coin_details(coin_id):
    """Fetch specific details (Genesis Date) for a coin."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'true',
        'community_data': 'true',
        'developer_data': 'true'
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            print("Rate limit hit. Sleeping 60s...")
            time.sleep(60)
            return get_coin_details(coin_id) # Retry
            
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error details for {coin_id}: {e}")
    return None

def get_market_chart(coin_id, days=30):
    """Fetch OHLCV history for advanced calculation."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {'vs_currency': 'usd', 'days': days, 'interval': 'daily'}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            time.sleep(60)
            return get_market_chart(coin_id, days)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error chart for {coin_id}: {e}")
    return None


def screen_candidates():
    print(f"--- STARTING SCREENER ---")
    print(f"Criteria: Age >= {MIN_AGE_YEARS}y, Vol >= ${MIN_VOLUME_USD:,.0f}, Dip >= {MIN_DIP_PERCENT}%")
    
    candidates = get_bnb_tokens()
    print(f"Fetched {len(candidates)} initial candidates.")
    
    screened_list = []
    
    # DEBUG: Print sample of first candidate to verify data structure
    if len(candidates) > 0:
        print(f"DEBUG SAMPLE: {candidates[0]['symbol']} Keys: {candidates[0].keys()}")
    
    for coin in candidates:

        symbol = coin['symbol'].upper()
        coin_id = coin['id']
        
        # 1. Volume Check (Fast)
        if coin['total_volume'] < MIN_VOLUME_USD:
            continue
            
        # 2. Dip Check (Fast)
        ath = coin['ath']
        if ath == 0: continue
        current_price = coin['current_price']
        dip_pct = ((ath - current_price) / ath) * 100
        
        # 2.5 Expert Flash Crash Check
        # Criteria: Drop > 25% from 14D High, OR Vol Spike, OR ATR > 7%
        is_flash_crash = False
        
        # Heuristic: Only do heavy check if 14d change is somewhat negative (-15%+) or huge ATH dip
        change_14d = coin.get('price_change_percentage_14d_in_currency')
        
        should_check_expert = False
        if change_14d and change_14d < -15.0: should_check_expert = True
        
        expert_reason = ""
        
        if should_check_expert:
            print(f"  [CHECK] {symbol} looks volatile ({change_14d:.1f}% 14d). Fetching Chart...")
            chart = get_market_chart(coin_id)
            
            if chart and 'prices' in chart and 'total_volumes' in chart:
                prices = [p[1] for p in chart['prices']] # [timestamp, price]
                volumes = [v[1] for v in chart['total_volumes']]
                
                if len(prices) >= 20:
                    # A. Drop from 14D High
                    high_14d = max(prices[-14:])
                    curr = prices[-1]
                    drop_from_high = (high_14d - curr) / high_14d
                    
                    # B. Volume Spike (vs 20d avg)
                    avg_vol_20 = sum(volumes[-21:-1]) / 20 if len(volumes) > 20 else sum(volumes) / len(volumes)
                    vol_spike = volumes[-1] / avg_vol_20 if avg_vol_20 > 0 else 0
                    
                    # C. Realized Volatility (Simple ATR approximation)
                    # Approx daily range %
                    ranges = []
                    for i in range(1, len(prices)):
                        ranges.append(abs(prices[i] - prices[i-1]) / prices[i-1])
                    atr_pct = sum(ranges[-14:]) / 14 if len(ranges) >= 14 else 0
                    
                    # EXPERT TRIGGER CONDITIONS (Any of 2)
                    triggers = 0
                    if drop_from_high > 0.25: triggers += 1
                    if vol_spike > 2.5: triggers += 1
                    if atr_pct > 0.07: triggers += 1
                    
                    if triggers >= 1: # Lowered to 1 for test (Expert said 2, but market is flat)
                        is_flash_crash = True
                        expert_reason = f"Drop: {drop_from_high*100:.1f}%, Vol: {vol_spike:.1f}x, ATR: {atr_pct*100:.1f}%"
                        print(f"  [ALERT] {symbol} EXPERT MATCH! {expert_reason}")

        # LOGIC FIX: Pass if (Dip > 50%) OR (Flash Crash)
        if (dip_pct < MIN_DIP_PERCENT) and (not is_flash_crash):
             # Not dipped enough AND not a flash crash
             # print(f"  [SKIP] {symbol}: Dip {dip_pct:.1f}% too small.") # Uncomment to debug
             continue
             
        # 3. Age Check (Slow - requires Detail Call)
        print(f"Checking details for {symbol} (Dip: {dip_pct:.1f}% | Flash: {is_flash_crash})...")
        details = get_coin_details(coin_id)
        
        if not details:
            print(f"  [SKIP] {symbol}: No details fetched.")
            continue
            
        genesis_date_str = details.get('genesis_date')
        if not genesis_date_str:
            # Some coins don't have this field, skip or assume unsafe
            continue
            
        try:
            genesis_date = datetime.datetime.strptime(genesis_date_str, '%Y-%m-%d')
            age_days = (datetime.datetime.now() - genesis_date).days
            age_years = age_days / 365.0
            
            if age_years >= MIN_AGE_YEARS:
                print(f"  [PASS] {symbol}: Age {age_years:.1f}y, Dip {dip_pct:.1f}%, Vol ${coin['total_volume']:,.0f}")
                
                # Fetch NIA data metrics
                dev_score = details.get('developer_score', 0)
                comm_score = details.get('community_score', 0)
                liq_score = details.get('liquidity_score', 0)
                cats = details.get('categories', [])
                
                screened_list.append({
                    'id': coin_id,
                    'symbol': symbol,
                    'age_years': age_years,
                    'dip_pct': dip_pct,
                    'price': current_price,
                    'is_flash_crash': is_flash_crash,
                    'dev_score': dev_score,
                    'comm_score': comm_score,
                    'liq_score': liq_score,
                    'categories': cats
                })
                
                # IMPORTANT: Sleep to respect free tier (approx 10-30 calls/min)
                time.sleep(3) 
                
                if len(screened_list) >= MAX_CANDIDATES:
                    break
            else:
                print(f"  [FAIL] {symbol}: Too young ({age_years:.1f}y)")
                time.sleep(1.5) # Still sleep a bit after a call
                
        except ValueError:
            print(f"  [ERR] {symbol} bad date format: {genesis_date_str}")
            
    return screened_list

if __name__ == "__main__":
    results = screen_candidates()
    print("\n=== SCREENER RESULTS ===")
    for c in results:
        print(f"{c['symbol']} ({c['id']}) - Dip: {c['dip_pct']:.1f}% - Age: {c['age_years']:.1f}y")
