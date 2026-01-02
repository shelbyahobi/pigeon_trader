# Deployment Guide: Google Cloud (Free Tier)

## 1. Connect to VPS
Open your terminal or SSH client:
```bash
ssh username@your-gcp-ip
```

## 2. Update Code   folder and pull the latest strategies:
```bash
cd pigeon_trader
git pull origin main
```

## 3. Install Requirements (If needed)
Just to be safe:
```bash
pip install -r requirements.txt
```

## 4. Launch the Bot (Choose Mode)

### Option A: The "Mixed Fleet" (Recommended)
Runs **95% Echo** (Alpha Hunter) and **5% CAHV** (Vortex Harvest).
```bash
nohup python3 strategic_bot.py mixed > bot.log 2>&1 &
```

### Option B: Solo Echo
```bash
nohup python3 strategic_bot.py echo > bot.log 2>&1 &
```

## 5. View Logs
To check if it's working:
```bash
tail -f bot.log
```

## 6. Stop the Bot
If you want to kill it:
```bash
pkill -f strategic_bot.py
```
