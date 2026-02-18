from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.liqtracker.analysis import classify_flows, summarize
from src.liqtracker.api import fetch_token_prices_usd, fetch_token_transfers
from src.liqtracker.config import DEFAULT_AERODROME_CONTRACTS

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)


def persist_settings(api_key: str, wallet: str) -> None:
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()

    kv = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            kv[k.strip()] = v.strip()

    kv["BASESCAN_API_KEY"] = api_key.strip()
    kv["WALLET_ADDRESS"] = wallet.strip()

    content = "\n".join([f"{k}={v}" for k, v in kv.items()]) + "\n"
    ENV_PATH.write_text(content)


st.set_page_config(page_title="LIQTracker", page_icon="💧", layout="wide")
st.title("💧 LIQTracker — Aerodrome deposit profitability tracker")
st.caption("MVP: scans Base token transfers and Aerodrome-linked transactions, then estimates PnL using current USD prices.")

with st.sidebar:
    st.header("Settings")
    wallet = st.text_input("Wallet address", value=os.getenv("WALLET_ADDRESS", "")).strip()
    api_key = st.text_input("API key (optional)", value=os.getenv("BASESCAN_API_KEY", ""), type="password").strip()
    custom_contracts = st.text_area(
        "Extra Aerodrome contract addresses (one per line)",
        value="",
        help="Add gauge/pool/position-manager contracts specific to your activity for better accuracy.",
    )

    start_block = st.number_input("Start block", value=0, min_value=0, step=1)
    end_block = st.number_input("End block", value=99_999_999, min_value=0, step=1)

    csave, crun = st.columns(2)
    save_clicked = csave.button("Save settings")
    run = crun.button("Run scan", type="primary")

if save_clicked:
    persist_settings(api_key=api_key, wallet=wallet)
    st.success("Saved wallet + API key to .env")

if run:
    if not wallet:
        st.error("Please enter wallet address.")
        st.stop()

    # Auto-save latest credentials/settings on successful run click.
    persist_settings(api_key=api_key, wallet=wallet)

    protocol_contracts = set(DEFAULT_AERODROME_CONTRACTS)
    if custom_contracts.strip():
        protocol_contracts |= {x.strip() for x in custom_contracts.splitlines() if x.strip()}

    try:
        with st.spinner("Fetching token transfers..."):
            transfers = fetch_token_transfers(wallet=wallet, api_key=api_key, start_block=int(start_block), end_block=int(end_block))
    except Exception as e:
        st.error(f"Data fetch failed: {e}")
        st.stop()

    flows = classify_flows(
        transfers=transfers,
        wallet=wallet,
        protocol_contracts=protocol_contracts,
    )

    if not flows:
        st.warning(
            "No Aerodrome-related token flows found in this block range. "
            "Try widening block range and/or add known pool/gauge/position-manager contracts in sidebar."
        )
        with st.expander("Debug info"):
            st.write({
                "token_transfer_count": len(transfers),
                "aerodrome_flow_count": 0,
            })
        st.stop()

    try:
        token_prices = fetch_token_prices_usd({f.token_contract for f in flows})
        detail_df, summary_df, kpis = summarize(flows, token_prices)
    except Exception as e:
        st.error(f"Analysis failed: {e}")
        st.stop()

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
