import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    Calculate all technical indicators needed by strategies (Echo, NIA, AAMR).
    Returns: DataFrame with added columns.
    """
    if len(df) < 50:
        return df
    
    # ensure we have working columns
    # In 'Cloud Paper Mode' (High=Low=Close), we must be careful.
    
    # 1. BOLLINGER BANDS (Echo needs this)
    # ------------------------------------
    df['bb_middle'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_middle'] + (2 * df['bb_std'])
    df['bb_lower'] = df['bb_middle'] - (2 * df['bb_std'])
    
    # BB Width (normalized)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close']
    
    # BB Width Rank (percentile over 180 days)
    df['bb_width_rank'] = df['bb_width'].rolling(180).rank(pct=True)
    
    # 2. ATR (Volatility)
    # ------------------------------------
    # True Range. If High=Low=Close, TR = Abs(Close - PrevClose)
    # This effectively measures "Daily Move"
    df['price_change'] = df['close'].diff().abs()
    df['atr'] = df['price_change'].rolling(14).mean()
    
    # 3. VOLUME SIGNALS (Echo needs this)
    # ------------------------------------
    df['vol_7d'] = df['total_volume'].rolling(7).mean()
    df['vol_30d'] = df['total_volume'].rolling(30).mean()
    
    # Trigger 1: Volume Spike Ratio
    # Avoid div by zero
    df['vol_ratio'] = df['vol_7d'] / df['vol_30d'].replace(0, 1)
    
    # Trigger 2: Rising Volume (3 days)
    # v > v-1 > v-2
    v = df['total_volume']
    df['vol_rising'] = (
        (v > v.shift(1)) &
        (v.shift(1) > v.shift(2))
    )
    
    # Composite Signal
    df['vol_signal'] = (df['vol_ratio'] > 1.5) & df['vol_rising']
    
    # Trigger 3: Spike Ratio (NIA uses 5.0 check on RAW volume)
    df['vol_ma_30'] = df['vol_30d']
    df['vol_spike_ratio'] = df['total_volume'] / df['vol_ma_30'].replace(0, 1)

    # 4. DRAWDOWN (Both need this)
    # ------------------------------------
    df['high_365d'] = df['high'].rolling(365, min_periods=180).max()
    df['drawdown'] = (df['high_365d'] - df['close']) / df['high_365d']
    
    # 5. PRICE VS HIGH (NIA needs this)
    # ------------------------------------
    df['high_30d'] = df['high'].rolling(30).max()
    df['price_vs_high'] = df['close'] / df['high_30d']
    
    # 6. SPREAD COMPRESSION PROXY (NIA needs this)
    # ------------------------------------
    # Since we lack order books, we use a "Liquidity Proxy".
    # Logic: Higher Volume / DailyMove = Thicker Liquidity.
    # Logic: Lower Volume / DailyMove = Thinner Liquidity.
    # Note: If DailyMove is 0, replace with small epsilon to avoid infinity.
    
    daily_move_pct = df['close'].pct_change().abs().replace(0, 0.0001)
    df['liquidity_proxy'] = df['total_volume'] / (df['close'] * daily_move_pct)
    
    # Smoothing
    df['liquidity_ma'] = df['liquidity_proxy'].rolling(30).mean()
    
    # Indicator: Change in Liquidity
    # > 0 means Liquidity Improving (Tightening)
    # < 0 means Liquidity Worsening (Widening)
    # NIA looks for "Tightening" (Improving) -> Compression
    df['spread_compression'] = df['liquidity_ma'].pct_change(14)
    
    # Clean NaNs
    df.fillna(0, inplace=True)
    
    return df
