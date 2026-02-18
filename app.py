from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.liqtracker.analysis import classify_flows, summarize
from src.liqtracker.api import fetch_normal_transactions, fetch_token_prices_usd, fetch_token_transfers
from src.liqtracker.config import DEFAULT_AERODROME_CONTRACTS

load_dotenv()

st.set_page_config(page_title="LIQTracker", page_icon="💧", layout="wide")
st.title("💧 LIQTracker — Aerodrome deposit profitability tracker")
st.caption("MVP: scans Base token transfers to/from known Aerodrome contracts and estimates PnL using current USD prices.")

with st.sidebar:
    st.header("Settings")
    wallet = st.text_input("Wallet address", value=os.getenv("WALLET_ADDRESS", "")).strip()
    api_key = st.text_input("Basescan API key", value=os.getenv("BASESCAN_API_KEY", ""), type="password").strip()
    custom_contracts = st.text_area(
        "Extra Aerodrome contract addresses (one per line)",
        value="",
        help="Add gauge/pool/position-manager contracts specific to your activity for better accuracy.",
    )

    start_block = st.number_input("Start block", value=0, min_value=0, step=1)
    end_block = st.number_input("End block", value=99_999_999, min_value=0, step=1)

    run = st.button("Run scan", type="primary")

if run:
    if not wallet or not api_key:
        st.error("Please enter both wallet address and Basescan API key.")
        st.stop()

    protocol_contracts = set(DEFAULT_AERODROME_CONTRACTS)
    if custom_contracts.strip():
        protocol_contracts |= {x.strip() for x in custom_contracts.splitlines() if x.strip()}

    with st.spinner("Fetching transfers + tx history from Basescan..."):
        transfers = fetch_token_transfers(wallet=wallet, api_key=api_key, start_block=int(start_block), end_block=int(end_block))
        normal_txs = fetch_normal_transactions(wallet=wallet, api_key=api_key, start_block=int(start_block), end_block=int(end_block))

    # Any transaction where wallet called/was-called by core Aerodrome contracts
    # is treated as Aerodrome-related; then we include token transfers from those tx hashes.
    core_contracts = {c.lower() for c in DEFAULT_AERODROME_CONTRACTS}
    aero_hashes = {
        str(tx.get("hash", "")).lower()
        for tx in normal_txs
        if str(tx.get("to", "")).lower() in core_contracts
        or str(tx.get("from", "")).lower() in core_contracts
    }

    flows = classify_flows(
        transfers=transfers,
        wallet=wallet,
        protocol_contracts=protocol_contracts,
        aerodrome_tx_hashes=aero_hashes,
    )

    if not flows:
        st.warning(
            "No Aerodrome-related token flows found in this block range. "
            "Try widening block range and/or add known pool/gauge/position-manager contracts in sidebar."
        )
        with st.expander("Debug info"):
            st.write({
                "token_transfer_count": len(transfers),
                "normal_tx_count": len(normal_txs),
                "aerodrome_tagged_tx_hashes": len(aero_hashes),
            })
        st.stop()

    token_prices = fetch_token_prices_usd({f.token_contract for f in flows})
    detail_df, summary_df, kpis = summarize(flows, token_prices)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Deposited (USD now)", f"${kpis['total_deposit_usd_now']:,.2f}")
    c2.metric("Inflows incl. fees (USD now)", f"${kpis['total_inflow_usd_now']:,.2f}")
    c3.metric("Estimated PnL (USD now)", f"${kpis['estimated_pnl_usd_now']:,.2f}")
    c4.metric("Tracked transfers", f"{kpis['tx_count']:,}")

    st.subheader("Token summary")
    st.dataframe(summary_df, width="stretch", hide_index=True)

    st.subheader("Detailed flows")
    pretty = detail_df.copy()
    pretty["timestamp"] = pd.to_datetime(pretty["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    st.dataframe(pretty, width="stretch", hide_index=True)

    csv = pretty.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name="liqtracker_flows.csv", mime="text/csv")

st.markdown("---")
st.info(
    "Accuracy note: this MVP uses transfer-direction heuristics + current prices, so it is an estimate. "
    "For exact LP PnL (principal vs impermanent loss vs realized fees), we can add per-position math via Aerodrome pool/gauge/NFT events next."
)
