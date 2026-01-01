import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from backtest_system import run_all_strategies, load_all_data

st.set_page_config(page_title="Pigeon Trader Dashboard", layout="wide")

st.title("🐦 Pigeon Trader - Strategy Dashboard")

# Run Analysis (Cache this in a real app)
@st.cache_data
def get_results():
    return run_all_strategies()

results = get_results()

# Sidebar
st.sidebar.header("Configuration")
selected_token = st.sidebar.selectbox("Select Token", list(results.keys()))

# Main Content
tab1, tab2 = st.tabs(["Standard Backtest", "Bull vs Bear (Heavy)"])

with tab1:
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

with tab2:
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

# Raw Data Expander
with st.expander("View Raw Logic Output"):

    st.write("Backtest ran on local CSV data from `data/` folder.")
    st.json(metrics)
