from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Iterable

import requests

from .config import COINGECKO_SIMPLE_PRICE

BLOCKSCOUT_BASE = "https://base.blockscout.com/api/v2"


def _get_json(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _to_unix(ts: str | None) -> int:
    if not ts:
        return 0
    # Example: 2026-02-18T13:02:13.000000Z
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def fetch_token_transfers(wallet: str, api_key: str = "", start_block: int = 0, end_block: int = 99999999) -> list[dict]:
    _ = api_key  # kept for interface compatibility; Blockscout path doesn't require it.
    wallet = wallet.strip()
    url = f"{BLOCKSCOUT_BASE}/addresses/{wallet}/token-transfers"

    items: list[dict] = []
    params: dict = {}
    seen_pages: set[str] = set()

    # Pull recent pages for responsiveness in UI.
    for _page in range(8):
        page_key = repr(sorted(params.items()))
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        data = _get_json(url, params=params)
        page_items = data.get("items", [])
        if not isinstance(page_items, list) or not page_items:
            break

        for it in page_items:
            block_number = int(it.get("block_number") or 0)
            if block_number < start_block:
                continue
            if block_number > end_block:
                continue

            token_type = str(it.get("token_type") or "")
            if token_type and token_type.upper() not in {"ERC-20", "ERC20"}:
                continue

            total = it.get("total") or {}
            token = it.get("token") or {}
            from_obj = it.get("from") or {}
            to_obj = it.get("to") or {}
            items.append(
                {
                    "from": (from_obj.get("hash") or "").lower(),
                    "to": (to_obj.get("hash") or "").lower(),
                    "from_name": str(from_obj.get("name") or ""),
                    "to_name": str(to_obj.get("name") or ""),
                    "method": str(it.get("method") or ""),
                    "hash": str(it.get("transaction_hash") or "").lower(),
                    "timeStamp": str(_to_unix(it.get("timestamp"))),
                    "tokenSymbol": str(token.get("symbol") or "?"),
                    "contractAddress": str(token.get("address_hash") or "").lower(),
                    "tokenDecimal": str((total.get("decimals") or token.get("decimals") or 18)),
                    "value": str(total.get("value") or "0"),
                }
            )

        next_page = data.get("next_page_params")
        if not next_page:
            break
        params = next_page
        time.sleep(0.05)

    return items


def fetch_normal_transactions(wallet: str, api_key: str = "", start_block: int = 0, end_block: int = 99999999) -> list[dict]:
    _ = api_key
    wallet = wallet.strip()
    url = f"{BLOCKSCOUT_BASE}/addresses/{wallet}/transactions"

    items: list[dict] = []
    params: dict = {}
    seen_pages: set[str] = set()

    for _page in range(8):
        page_key = repr(sorted(params.items()))
        if page_key in seen_pages:
            break
        seen_pages.add(page_key)

        data = _get_json(url, params=params)
        page_items = data.get("items", [])
        if not isinstance(page_items, list) or not page_items:
            break

        for it in page_items:
            block_number = int(it.get("block_number") or 0)
            if block_number < start_block:
                continue
            if block_number > end_block:
                continue

            to_obj = it.get("to") or {}
            from_obj = it.get("from") or {}
            items.append(
                {
                    "hash": str(it.get("hash") or "").lower(),
                    "from": (from_obj.get("hash") or "").lower(),
                    "to": (to_obj.get("hash") or "").lower(),
                    "from_name": str(from_obj.get("name") or ""),
                    "to_name": str(to_obj.get("name") or ""),
                    "method": str(it.get("method") or ""),
                    "timeStamp": str(_to_unix(it.get("timestamp"))),
                    "blockNumber": str(block_number),
                }
            )

        next_page = data.get("next_page_params")
        if not next_page:
            break
        params = next_page
        time.sleep(0.05)

    return items


def _fetch_prices_chunk(chunk: list[str]) -> dict[str, float]:
    params = {
        "contract_addresses": ",".join(chunk),
        "vs_currencies": "usd",
    }
    r = requests.get(COINGECKO_SIMPLE_PRICE, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    out: dict[str, float] = {}
    for c in chunk:
        out[c] = float(data.get(c, {}).get("usd", 0.0) or 0.0)
    return out


def fetch_token_prices_usd(token_contracts: Iterable[str]) -> dict[str, float]:
    tokens = [t.lower() for t in token_contracts if t]
    if not tokens:
        return {}

    out: dict[str, float] = {}
    for i in range(0, len(tokens), 100):
        chunk = tokens[i : i + 100]
        try:
            out.update(_fetch_prices_chunk(chunk))
        except requests.HTTPError:
            # Some addresses (e.g., non-ERC20 contracts/NFT contracts) can cause 400.
            # Retry individually and ignore non-priceable addresses.
            for c in chunk:
                try:
                    out.update(_fetch_prices_chunk([c]))
                except requests.HTTPError:
                    out[c] = 0.0
                time.sleep(0.08)
        time.sleep(0.15)
    return out
