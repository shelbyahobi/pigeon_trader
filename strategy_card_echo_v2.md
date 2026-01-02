# 🦅 Strategy Card: Echo Hardened (v2)

**"The Professional's Alpha Hunter"**

This is the revised, expert-reviewed version of the Echo strategy. It removes the "gambling" elements and adds "Regime Awareness" and "Professional Risk Management".

---

## ⚙️ Core Logic (The Setup)

### 1. The Filter (Deep Value)
*   **Deep Value**: Price must be **-60%** from its 1-Year High.
*   **Regime Check (NEW)**: 
    *   **BTC Trend**: BTC price must be > **21-Week EMA** (Bull Market Regime). If BTC is Bearish, the bot **Sleeps**.
    *   **Funding Rate**: Futures Funding Rate must be **< 0.01%** (Neutral/Negative). No buying into overheated retail FOMO.

### 2. The Trigger (The Squeeze & Trend)
*   **Squeeze (NEW)**: Bollinger Band Width must be in the **Lowest 20%** of the last 6 months. (Relative Squeeze).
*   **Volume Trend (NEW)**: 
    *   Volume > **1.5x** 7-Day Average.
    *   **AND** Volume Rising for **3 Consecutive Days** (Accumulation confirmation, not blow-off top).

### 3. The Exit (The Discipline)
*   **Dynamic Trail**: Trailing Stop at **1.5x ATR** from peak.
*   **Hard Stop**: **-15%** fixed.

---

## 🛡️ Risk Management (Hardened)
*   **Max Risk/Trade**: **3%** (Reduced from 5%).
*   **Max Open Positions**: 5 (Max 15% Total Exposure).
*   **Capital Preservation**: If BTC is below 21-Week EMA, cash position = 100%.

---

## 🛠️ Changes vs v1
*   [x] **Volume**: Fixed "Late Entry" by targeting 3-day build-up instead of 1-day spike.
*   [x] **Blind Spot**: Added `fetch_funding_rate()` to detect hidden leverage risks.
*   [x] **Bear Trap**: Added `fetch_btc_trend()` to avoid buying during crashes.
*   [x] **Account Safety**: Reduced risk cap to 3%.

## 🚀 Deployment Status
*   **Code**: Updated in `strategic_bot.py` and `strategies/echo.py`.
*   **Mode**: Ready for Real-Money (Phase 2) after 24h Paper Test.
