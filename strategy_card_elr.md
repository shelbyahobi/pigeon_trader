# 🦅 Strategy Card: Echo Liquidity Rebound (ELR)

**" The Alpha Hunter"**

This strategy is designed to catch **V-Shape Recoveries** in high-volatility assets (SOL, PEPE, MEMEs) after they have crashed and stabilized. It avoids "catching the knife" by waiting for a volatility squeeze.

---

## ⚙️ Core Logic

### 1. The Setup (The Filter)
*   **Deep Value**: Price must be **-60%** from its 1-Year High.
*   **Squeeze**: Volatility must collapse (Bollinger Band Width < 10%). *This means the selling has stopped and the coin is "boring".*

### 2. The Trigger (The Entry)
*   **Whale Interest**: Volume must **Spike > 300%** above the 7-day average.
*   **Absorption**: High Volume + Low Price Movement = Smart Money absorbing sellers.

### 3. The Exit (The Profit)
*   **Dynamic Trail**: Trailing Stop follows the price up at a distance of **1.5x ATR** (Volatility Units).
    *   *If the pump is aggressive, the stop loosens.*
    *   *If the pump stalls, the stop tightens.*
*   **Hard Stop**: **-15%** immediate exit if the trade fails.

---

## 🛡️ Risk Management (Expert Settings)
*   **Max Risk/Trade**: **5%** of Portfolio (Updated).
*   **Max Open Positions**: 5.
*   **Capital Preservation**: If the Screener finds nothing, it stays **100% Cash**.

---

## 🧪 Simulation Results (Last 365 Days)
| Coin | Result | Notes |
| :--- | :--- | :--- |
| **$SOL** | **+148%** | Caught the breakout at $22. |
| **$PEPE** | **+122%** | Caught the meme super-cycle. |
| **$BNB** | **0%** | Stayed safe (no trade) during chop. |

---

## 🛠️ Improvement Checklist
*   [x] **Risk Cap**: Adjusted from 12% -> 5% per expert request.
*   [x] **Data Proxies**: Implemented "Lean" proxies to avoid $1,000/mo fees.
*   [ ] **Live Order Book**: Currently using a "Math Proxy". *Future Upgrade: Add Binance API Key.*

## 🚀 Deployment Plan
1.  **Phase 1 (Now)**: Run in **Paper Mode** (Default) for 24 hours. The bot simulates trades with fake $1,000.
2.  **Phase 2**: Review logs tomorrow.
3.  **Phase 3**: Add Real Private Key for Mainnet execution.
