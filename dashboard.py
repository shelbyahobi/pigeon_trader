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

# Raw Data Expander
with st.expander("View Raw Logic Output"):
    st.write("Backtest ran on local CSV data from `data/` folder.")
    st.json(metrics)
