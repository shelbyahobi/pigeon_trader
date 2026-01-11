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


# --- MARKET CAP CONFIG ---
MIN_MCAP = 500_000_000     # $500M
MAX_MCAP = 50_000_000_000  # $50B

def get_min_volume(mcap):
    """Volume requirements scale with market cap"""
    if mcap > 10_000_000_000:  # Large cap > $10B
        return 5_000_000       # $5M daily minimum
    elif mcap > 1_000_000_000: # Mid cap > $1B
        return 1_000_000       # $1M daily minimum
    else:                      # Small cap < $1B
        return 500_000         # $500K daily minimum

def classify_tier(mcap):
    if mcap > 10_000_000_000: return 'large'
    elif mcap > 5_000_000_000: return 'upper_mid'
    elif mcap > 2_000_000_000: return 'core_mid'
    elif mcap > 1_000_000_000: return 'lower_mid'
    else: return 'small'

def score_candidate(coin):
    """Rank candidates to ensure we always get the best 20 available."""
    score = 100 # Base score
    
    # 1. Tier Bonus (Preference for liquidity/reliability)
    # Mid Caps are the sweet spot, Large Caps are safe anchors
    if coin['tier'] in ['core_mid', 'upper_mid']: score += 30
    if coin['tier'] == 'large': score += 20
    
    # 2. Opportunity Bonus (Preference for crashes)
    # 50% Dip = +25 points. 90% Dip = +45 points.
    score += coin['dip_pct'] * 0.5
    
    # 3. Quality Bonus (Metadata) - Soft impact
    # Use 0 if None to handle missing data safely
    score += (coin.get('dev_score', 0) or 0) * 0.2
    score += (coin.get('liq_score', 0) or 0) * 0.2
    
    # 4. Expert Bonus (Flash Crash detection)
    if coin.get('is_flash_crash'): score += 50 
    
    # 5. Age Penalty (Slight penalty for very young coins)
    if coin.get('age_years', 0) < 3.0: score -= 10
    
    return score

def balance_watchlist(candidates):
    """
    OLD: Enforced strict tier % (Rejected valid tokens).
    NEW: Returns Top N candidates by Score.
    """
    # 1. Score every candidate
    for c in candidates:
        c['signal_score'] = score_candidate(c)
        
    # 2. Sort by Score (Highest first)
    candidates.sort(key=lambda x: x['signal_score'], reverse=True)
    
    # 3. Return Top N (Ensures we never return an empty list if ANY candidates exist)
    final_list = candidates[:MAX_CANDIDATES]
    
    # Log the scores for debugging
    print(f"DEBUG: Top Candidate Score: {final_list[0]['signal_score']:.1f} ({final_list[0]['symbol']})")
    
    return final_list

def screen_candidates():
    print(f"--- STARTING SCREENER (INTELLIGENCE MODE) ---")
    
    candidates = get_bnb_tokens()
    print(f"Fetched {len(candidates)} initial candidates.")
    
    valid_candidates = []
    
    for coin in candidates:
        symbol = coin['symbol'].upper()
        coin_id = coin['id']
        mcap = coin.get('market_cap', 0)
        vol = coin.get('total_volume', 0)
        
        # 1. Market Cap Filter
        if not (MIN_MCAP <= mcap <= MAX_MCAP):
            continue
            
        # 2. Dynamic Volume Filter
        if vol < get_min_volume(mcap):
            continue
            
        # 3. Dip Check
        ath = coin.get('ath', 0)
        if ath == 0: continue
        current_price = coin.get('current_price', 0)
        dip_pct = ((ath - current_price) / ath) * 100
        
        coin['dip_pct'] = dip_pct
        coin['tier'] = classify_tier(mcap)
        
        # 4. Expert Flash Crash Logic
        is_flash_crash = False
        change_14d = coin.get('price_change_percentage_14d_in_currency')
        should_check_expert = (change_14d and change_14d < -15.0)
        
        expert_reason = ""
        
        if should_check_expert:
            print(f"  [CHECK] {symbol} ({coin['tier']}) volatile ({change_14d:.1f}%). Fetching Chart...")
            chart = get_market_chart(coin_id)
            
            if chart and 'prices' in chart and 'total_volumes' in chart:
                prices = [p[1] for p in chart['prices']]
                volumes = [v[1] for v in chart['total_volumes']]
                
                if len(prices) >= 20:
                    high_14d = max(prices[-14:])
                    curr = prices[-1]
                    drop_from_high = (high_14d - curr) / high_14d
                    
                    avg_vol_20 = sum(volumes[-21:-1]) / 20 if len(volumes) > 20 else sum(volumes) / len(volumes)
                    vol_spike = volumes[-1] / avg_vol_20 if avg_vol_20 > 0 else 0
                    
                    ranges = []
                    for i in range(1, len(prices)):
                        ranges.append(abs(prices[i] - prices[i-1]) / prices[i-1])
                    atr_pct = sum(ranges[-14:]) / 14 if len(ranges) >= 14 else 0
                    
                    triggers = 0
                    if drop_from_high > 0.25: triggers += 1
                    if vol_spike > 2.5: triggers += 1
                    if atr_pct > 0.07: triggers += 1
                    
                    if triggers >= 1:
                        is_flash_crash = True
                        expert_reason = f"Drop: {drop_from_high*100:.1f}%, Vol: {vol_spike:.1f}x, ATR: {atr_pct*100:.1f}%"
                        print(f"  [ALERT] {symbol} EXPERT MATCH! {expert_reason}")

        coin['is_flash_crash'] = is_flash_crash
        
        # Filter Logic
        if (dip_pct < MIN_DIP_PERCENT) and (not is_flash_crash):
             continue

        # Add to valid list (without details yet)
        valid_candidates.append(coin)

    # Balance the list BEFORE fetching heavy details
    print(f"Found {len(valid_candidates)} candidates pre-balancing.")
    final_selection = balance_watchlist(valid_candidates)
    
    screened_list = {'echo': [], 'nia': []}
    
    # Now fetch details for the winners
    for coin in final_selection:
        symbol = coin['symbol'].upper()
        # Age Check & Metadata
        print(f"Checking details for {symbol} ({coin['tier']} | Dip: {coin['dip_pct']:.1f}%)...")
        details = get_coin_details(coin['id'])
        
        if not details: continue
        
        genesis_date_str = details.get('genesis_date')
        age_years = 0.0
        
        if genesis_date_str:
            try:
                genesis_date = datetime.datetime.strptime(genesis_date_str, '%Y-%m-%d')
                age_years = (datetime.datetime.now() - genesis_date).days / 365.0
            except ValueError:
                pass
        
        # INTELLIGENCE FIX: Trust Large/Mid Caps even if Genesis Date is missing
        # If Market Cap > $1B, it's not a rug pull.
        # LOGIC UPGRADE: Echo (Safe) vs NIA (Risky/Expert)
        is_safe_tier = coin['tier'] in ['large', 'upper_mid', 'core_mid']
        is_safe_age = (age_years >= MIN_AGE_YEARS) or (is_safe_tier and age_years == 0.0)
        is_expert_match = coin.get('is_flash_crash', False)
        
        token_data = {
            'id': coin['id'],
            'symbol': symbol,
            'age_years': age_years,
            'dip_pct': coin['dip_pct'],
            'price': coin.get('current_price', 0),
            'is_flash_crash': is_expert_match,
            'dev_score': details.get('developer_score', 0),
            'comm_score': details.get('community_score', 0),
            'liq_score': details.get('liquidity_score', 0),
            'categories': details.get('categories', [])
        }

        # 1. Expert Matches ALWAYS go to NIA (High Volatility Plays)
        if is_expert_match:
             print(f"  [NIA] {symbol}: Expert Flash Crash! (Age: {age_years:.1f}y)")
             screened_list['nia'].append(token_data)
             
        # 2. Safe Coins go to ECHO
        elif is_safe_age:
             if age_years == 0.0: age_years = 5.0 # Dummy fix for safe tier
             token_data['age_years'] = age_years
             
             print(f"  [ECHO] {symbol}: Age {age_years:.1f}y (Tier: {coin['tier']}), Dip {coin['dip_pct']:.1f}%")
             screened_list['echo'].append(token_data)
             
        # 3. Young/Risky but Valid Tier go to NIA
        elif coin['tier'] in ['lower_mid', 'small']:
             print(f"  [NIA] {symbol}: YoungSpec play (Age: {age_years:.1f}y, Tier: {coin['tier']})")
             screened_list['nia'].append(token_data)
        
        else:
            print(f"  [FAIL] {symbol}: Rejected (Too young/Unknown and not suitable for NIA)")

        time.sleep(3)
            
    return screened_list

if __name__ == "__main__":
    results = screen_candidates()
    print("\n=== SCREENER RESULTS ===")
    for c in results:
        print(f"{c['symbol']} ({c['id']}) - Dip: {c['dip_pct']:.1f}% - Age: {c['age_years']:.1f}y")
