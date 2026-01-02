import requests
import datetime
import time

# --- CONFIG ---
MIN_AGE_YEARS = 2
MIN_VOLUME_USD = 1_000_000
MIN_DIP_PERCENT = 50.0

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
        'price_change_percentage': '30d,200d' # Fetch recent changes
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
        'community_data': 'false',
        'developer_data': 'false'
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

def screen_candidates():
    print(f"--- STARTING SCREENER ---")
    print(f"Criteria: Age >= {MIN_AGE_YEARS}y, Vol >= ${MIN_VOLUME_USD:,.0f}, Dip >= {MIN_DIP_PERCENT}%")
    
    candidates = get_bnb_tokens()
    print(f"Fetched {len(candidates)} initial candidates.")
    
    screened_list = []
    
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
        
        # 2.5 Recent Crash Check (Flash Crash Strategy)
        # Check if dropped > 40% in last 30 days (Crash)
        crash_30d = coin.get('price_change_percentage_30d_in_currency')
        is_flash_crash = False
        if crash_30d and crash_30d < -40.0:
            print(f"  [ALERT] {symbol} is a Flash Crash Candidate! ({crash_30d:.1f}% in 30d)")
            is_flash_crash = True
        
        # LOGIC FIX: Pass if (Dip > 50%) OR (Flash Crash)
        if (dip_pct < MIN_DIP_PERCENT) and (not is_flash_crash):
             # Not dipped enough AND not a flash crash
             continue
             
        # 3. Age Check (Slow - requires Detail Call)
        print(f"Checking details for {symbol} (Dip: {dip_pct:.1f}%)...")
        details = get_coin_details(coin_id)
        
        if not details:
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
                screened_list.append({
                    'id': coin_id,
                    'symbol': symbol,
                    'age_years': age_years,
                    'dip_pct': dip_pct,
                    'price': current_price,
                    'is_flash_crash': is_flash_crash
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
