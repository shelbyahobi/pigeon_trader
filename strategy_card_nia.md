# 🦅 Strategy Card: NIA (Narrative Ignition Asymmetry)

**"The Moonshot Sleeve (5% Allocation)"**

This strategy hunts for **Asymmetric Upside (100x)** by identifying projects where "Builders are Shipping" but "Price is Sleeping". It ignores price action and focuses on fundamental metadata.

---

## ⚙️ Core Logic (The Discovery)
The bot scans for **"Tier 1" Candidates** that meet these criteria:

### 1. Developer Persistence (Signal 1)
*   **Metric**: CoinGecko Developer Score > 50.
*   **Meaning**: The team is shipping code despite the bear market.

### 2. Narrative Potential (Signal 2 - *New*)
*   **Metric**: Must have at least one defined `Category` tag (e.g. "Gaming", "Layer 1").
*   **Meaning**: The project has a clear "Story" that can be sold to retail (Compressibility).

### 3. Liquidity Regime (Signal 3)
*   **Metric**: Spread Compression > 20% (vs 30d avg).
*   **Meaning**: Market Makers are returning to the order book.

---

## 🚀 Entry Logic (The Trigger)
We deploy the **5% Capital Sleeve** ("Tier 2") only if:
*   **Quiet Price**: Price is < 1.15x the 30-Day Low. (No FOMO).
*   **Organic Volume**: No 5x Volume Spikes (No Pump & Dumps).
*   **Deep Value**: Drawdown > 60% from ATH.

---

## 💎 Exit Logic (The Diamond Hands)
*   **No Stop Loss**: We accept 100% loss on this sleeve.
*   **Infinite Core**:
    *   If PnL > +300%: We **Hold**. (Simulated "Free Ride").
    *   **Target**: We only sell full position at **1000% (10x)** or upon **Macro Thesis Invalidation** (BTC Bear Market).
    *   *Note: Manual partial taking is recommended at +300% via exchange UI.*

---

## 🛡️ Risk Management
*   **Allocation**: Strictly 5% of Portfolio.
*   **Position Sizing**: Kelly Criterion capped at 1% per bet.
*   **Filter**: Bot ignores "Engineer Coins" (No Category) and "Dead Chains" (Dev Score < 50).

## 🛠️ Implementation Specs
*   **Proxies**: Built-in CoinGecko Metadata scraper (`screener.py`).
*   **Status**: Active in `mixed` mode.
