from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .config import TrackedFlow


def classify_flows(
    transfers: list[dict],
    wallet: str,
    protocol_contracts: set[str],
    aerodrome_tx_hashes: set[str] | None = None,
) -> list[TrackedFlow]:
    wallet = wallet.lower()
    contracts = {c.lower() for c in protocol_contracts}
    aero_hashes = {h.lower() for h in (aerodrome_tx_hashes or set())}
    flows: list[TrackedFlow] = []

    for t in transfers:
        from_addr = str(t.get("from", "")).lower()
        to_addr = str(t.get("to", "")).lower()
        tx_hash = str(t.get("hash", "")).lower()

        explicit_contract_match = (from_addr in contracts) or (to_addr in contracts)
        tx_level_match = tx_hash in aero_hashes

        if not (explicit_contract_match or tx_level_match):
            continue

        if from_addr == wallet:
            direction = "deposit"
            counterparty = to_addr
        elif to_addr == wallet:
            direction = "inflow"
            counterparty = from_addr
        else:
            # Wallet not sender/receiver on this transfer event
            # (can happen for unrelated transfers within same tx)
            continue

        decimals = int(t.get("tokenDecimal") or 18)
        raw = float(t.get("value") or 0.0)
        amount = raw / (10 ** decimals)

        flows.append(
            TrackedFlow(
                timestamp=int(t.get("timeStamp") or 0),
                tx_hash=str(t.get("hash", "")),
                token_symbol=str(t.get("tokenSymbol", "?")),
                token_contract=str(t.get("contractAddress", "")).lower(),
                direction=direction,
                amount=amount,
                counterparty=counterparty,
            )
        )

    return flows


def summarize(flows: list[TrackedFlow], token_prices: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = []
    agg = defaultdict(lambda: {"deposited": 0.0, "inflow": 0.0})

    for f in flows:
        px = token_prices.get(f.token_contract, 0.0)
        usd = f.amount * px
        rows.append(
            {
                "timestamp": pd.to_datetime(f.timestamp, unit="s", utc=True),
                "tx_hash": f.tx_hash,
                "token": f.token_symbol,
                "token_contract": f.token_contract,
                "direction": f.direction,
                "amount": f.amount,
                "price_usd_now": px,
                "usd_value_now": usd,
                "counterparty": f.counterparty,
            }
        )

        agg[f.token_symbol][f.direction] += f.amount

    detail_df = pd.DataFrame(rows).sort_values("timestamp") if rows else pd.DataFrame(columns=["timestamp", "tx_hash", "token", "token_contract", "direction", "amount", "price_usd_now", "usd_value_now", "counterparty"])

    summary_rows = []
    for token, data in agg.items():
        dep = data["deposited"]
        inflow = data["inflow"]
        net = inflow - dep
        summary_rows.append({"token": token, "deposited": dep, "inflow": inflow, "net": net})

    summary_df = pd.DataFrame(summary_rows).sort_values("token") if summary_rows else pd.DataFrame(columns=["token", "deposited", "inflow", "net"])

    total_deposit_usd = float(detail_df.loc[detail_df["direction"] == "deposit", "usd_value_now"].sum()) if not detail_df.empty else 0.0
    total_inflow_usd = float(detail_df.loc[detail_df["direction"] == "inflow", "usd_value_now"].sum()) if not detail_df.empty else 0.0

    kpis = {
        "total_deposit_usd_now": total_deposit_usd,
        "total_inflow_usd_now": total_inflow_usd,
        "estimated_pnl_usd_now": total_inflow_usd - total_deposit_usd,
        "tx_count": len(detail_df),
    }

    return detail_df, summary_df, kpis
