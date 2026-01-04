# Config for Pigeon Trader

# --- API ENDPOINTS ---
BSC_RPC_URL = "https://bsc-dataseed.binance.org/"  # Official public node
# Alternative: "https://1rpc.io/bnb" or "https://bscrpc.com"

# DexScreener API for scanning new pairs and fetching prices
DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens/"
DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search/?q="

# Honeypot.is API for safety checks
HONEYPOT_API_URL = "https://api.honeypot.is/v2/IsHoneypot"

# --- TRADING SETTINGS ---
PAPER_MODE = True  # Set to True for dry-run (no real money), False for real trades
TRADE_AMOUNT_BNB = 0.01  # Amount to "spend" per trade
SLIPPAGE = 10  # 10% slippage tolerance

# --- CONTRACTS ---
# PancakeSwap V2 Router
PANCAKE_ROUTER_ADDRESS = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
# WBNB Address
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

# --- NOTIFICATIONS ---
# Security: Load from .env file to prevent git leaks
import os
from dotenv import load_dotenv

# Try to load .env, but don't crash if missing (fallback to empty)
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- SYSTEM ---
WATCHLIST_FILE = "watchlist.json" # For Dashboard Visibility
