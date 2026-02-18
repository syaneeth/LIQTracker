# LIQTracker

Track your Aerodrome (Base) liquidity deposit flows and estimate profitability including fee inflows.

## What this MVP does

- Pulls wallet ERC-20 transfers from Basescan
- Filters transfers to/from known Aerodrome contracts
- Classifies:
  - **deposit**: token moved from your wallet into Aerodrome contracts
  - **inflow**: token moved from Aerodrome contracts into your wallet (includes withdrawals + fees)
- Prices tokens using CoinGecko current USD prices
- Shows estimated PnL based on current prices

> This is an estimate. It does **not** yet compute exact LP position-level PnL decomposition (principal, IL, fees realized/unrealized).

## Quick start

```bash
git clone https://github.com/syaneeth/LIQTracker.git
cd LIQTracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with BASESCAN_API_KEY + WALLET_ADDRESS
streamlit run app.py
```

Open: http://localhost:8503

## Run as a background service (systemd user service)

A user service file was installed at:

- `~/.config/systemd/user/liqtracker.service`

Useful commands:

```bash
systemctl --user daemon-reload
systemctl --user enable --now liqtracker.service
systemctl --user status liqtracker.service
journalctl --user -u liqtracker.service -f
```

Stop/restart:

```bash
systemctl --user stop liqtracker.service
systemctl --user restart liqtracker.service
```

The app listens on `0.0.0.0:8503`.

## Improve accuracy

In the sidebar you can add additional Aerodrome-related contract addresses (one per line), such as gauges/pools you interact with. This improves classification coverage.

## Next milestone ideas

1. Per-pool/per-position tracking
2. Historical USD at transfer time (instead of current-only valuation)
3. Explicit fee-claim detection using event signatures
4. Weekly/monthly PnL reports and Telegram alerts
