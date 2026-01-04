import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import time
from backtest_system import run_all_strategies, load_all_data

st.set_page_config(page_title="Pigeon Trader Dashboard", layout="wide")

st.title("🐦 Pigeon Trader - Command Center")

# --- LIVE MONITOR FUNCTIONS ---
def load_json_safe(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

# Sidebar
st.sidebar.header("Configuration")
page_mode = st.sidebar.radio("Mode", ["Live Monitor", "Strategy Backtest", "Historical Stress Test"])

if page_mode == "Live Monitor":
    st.header("🔴 Live Bot Status")
    
    # Refresh Button
    if st.button("Refresh Data"):
        st.rerun()

    # Load State
    state = load_json_safe("strategic_state.json")
    watchlist = load_json_safe("watchlist.json")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("💰 Fleet Status")
        if state:
            echo_cash = state.get('echo', {}).get('cash', 0)
            nia_cash = state.get('nia', {}).get('cash', 0)
            total_cash = echo_cash + nia_cash
            st.metric("Total Free Cash", f"${total_cash:.2f}")
            st.metric("Echo Pool", f"${echo_cash:.2f}")
            st.metric("NIA Pool", f"${nia_cash:.2f}")
        else:
            st.error("Bot State not found (Run bot first)")

    with col2:
        st.subheader("🦅 Active Watchlist")
        if watchlist:
            st.metric("Total Candidates", len(watchlist))
            
            # Show top 5
            df_wl = pd.DataFrame(watchlist)
            
            if not df_wl.empty:
                # Ensure columns exist
                if 'signal_score' not in df_wl.columns:
                    df_wl['signal_score'] = 0.0 # Default for fallback
                if 'dip_pct' not in df_wl.columns:
                    df_wl['dip_pct'] = 0.0
                if 'tier' not in df_wl.columns:
                    df_wl['tier'] = 'unknown'

                df_wl = df_wl.sort_values('signal_score', ascending=False)
                st.dataframe(df_wl[['symbol', 'signal_score', 'tier', 'dip_pct']].head(20))
            else:
                st.write("Watchlist is empty.")
        else:
            st.warning("No Watchlist found.")

    with col3:
        st.subheader("📦 Open Positions")
        if state:
            all_pos = []
            for mode in ['echo', 'nia']:
                positions = state.get(mode, {}).get('positions', {})
                for tid, pos in positions.items():
                    pos['mode'] = mode
                    pos['token'] = tid
                    all_pos.append(pos)
            
            if all_pos:
                st.dataframe(pd.DataFrame(all_pos))
            else:
                st.info("No active trades.")
                
    st.divider()
    st.subheader("Recent Logs")
    if os.path.exists("strategic_log.txt"):
        with open("strategic_log.txt", "r") as f:
            lines = f.readlines()
            st.code("".join(lines[-20:])) # Show last 20 lines

elif page_mode == "Strategy Backtest":
    # Run Analysis (Cache this in a real app)
    @st.cache_data
    def get_results():
        return run_all_strategies()
    
    results = get_results()
    
    # --- Category Filter ---
    # Hardcoded mapping for demo purposes (would ideally come from config)
    TOKEN_CATEGORIES = {
        'BTC': 'Large Cap', 'ETH': 'Large Cap', 'SOL': 'Large Cap',
        'LINK': 'Mid Cap', 'UNI': 'Mid Cap', 'DOT': 'Mid Cap', 'AVAX': 'Large Cap',
        'FET': 'Mid Cap', 'RNDR': 'Mid Cap', 'INJ': 'Mid Cap', 'AAVE': 'Mid Cap',
        'ALPACA': 'Micro Cap', 'GALA': 'Small Cap', 'SAND': 'Mid Cap'
    }
    
    categories = ["All"] + sorted(list(set(TOKEN_CATEGORIES.values())))
    selected_cat = st.sidebar.selectbox("Filter by Category", categories, index=0)
    
    # Filter tokens
    available_tokens = list(results.keys())
    if selected_cat != "All":
        available_tokens = [t for t in available_tokens if TOKEN_CATEGORIES.get(t, 'Unknown') == selected_cat]
    
    if available_tokens:
        selected_token = st.sidebar.selectbox("Select Token", available_tokens)
    else:
        st.sidebar.warning(f"No data for {selected_cat}")
        selected_token = None

    if selected_token:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"Performance Metrics: {selected_token}")
            
            # Create Metrics Table
            strats = results[selected_token]
            metrics = []
            for name, res in strats.items():
                metrics.append({
                    "Strategy": name,
                    "ROI %": f"{res['roi']:.2f}%"
                })
            st.table(pd.DataFrame(metrics))

        with col2:
            st.subheader("Equity Curves")
            
            # Plotting
            fig, ax = plt.subplots()
            for name, res in strats.items():
                equity = res['equity_curve']
                if not equity.empty:
                    ax.plot(equity.index, equity, label=name)
            
            ax.set_xlabel("Date")
            ax.set_ylabel("Equity ($)")
            ax.legend()
            ax.grid(True)
            st.pyplot(fig)

elif page_mode == "Historical Stress Test":
    st.header("Historical Stress Test (2022 vs 2024)")
    
    try:
        df_heavy = pd.read_csv("backtest_heavy_results.csv")
        
        # Summary Pivot
        st.subheader("Average ROI by Market Cycle")
        summary = df_heavy.groupby(['Cycle', 'Strategy'])['ROI'].mean().unstack()
        st.dataframe(summary.style.format("{:.2f}%").background_gradient(cmap='RdYlGn'))
        
        st.subheader("Detailed Results")
        st.dataframe(df_heavy)
        
        st.markdown("""
        **Key Insights:**
        *   **Bear Market (2022)**: Look for strategies with positive ROI (Green). RSI usually wins here.
        *   **Bull Market (2024)**: HODL is hard to beat. Look for strategies that Capture >50% of the HODL gain.
        """)
        
    except FileNotFoundError:
        st.warning("`backtest_heavy_results.csv` not found. Please run `py backtest_heavy.py` first.")
