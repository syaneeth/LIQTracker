from __future__ import annotations

import time
from typing import Iterable

import requests

from .config import BASESCAN_API, COINGECKO_SIMPLE_PRICE


def _get(url: str, params: dict) -> dict:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "0" and data.get("result") in ("Max rate limit reached", "Invalid API Key"):
        raise RuntimeError(f"API error: {data.get('result')}")
    return data


def fetch_token_transfers(wallet: str, api_key: str, start_block: int = 0, end_block: int = 99999999) -> list[dict]:
    params = {
        "module": "account",
        "action": "tokentx",
        "address": wallet,
        "startblock": start_block,
        "endblock": end_block,
        "sort": "asc",
        "apikey": api_key,
    }
    data = _get(BASESCAN_API, params)
    result = data.get("result", [])
    return result if isinstance(result, list) else []


def fetch_token_prices_usd(token_contracts: Iterable[str]) -> dict[str, float]:
    tokens = [t.lower() for t in token_contracts if t]
    if not tokens:
        return {}

    # Chunk to avoid URL length issues.
    out: dict[str, float] = {}
    for i in range(0, len(tokens), 100):
        chunk = tokens[i : i + 100]
        params = {
            "contract_addresses": ",".join(chunk),
            "vs_currencies": "usd",
        }
        r = requests.get(COINGECKO_SIMPLE_PRICE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for c in chunk:
            out[c] = float(data.get(c, {}).get("usd", 0.0) or 0.0)
        time.sleep(0.15)
    return out
