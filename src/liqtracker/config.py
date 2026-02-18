from __future__ import annotations

from dataclasses import dataclass

BASESCAN_API = "https://api.basescan.org/v2/api"
BASE_CHAIN_ID = "8453"
COINGECKO_SIMPLE_PRICE = "https://api.coingecko.com/api/v3/simple/token_price/base"

# Known Aerodrome protocol contracts on Base. Keep expanding as needed.
DEFAULT_AERODROME_CONTRACTS = {
    "0xcF77a3Ba9A5CA399B7c97c74d54e5b9d4a6fE7C2",  # Router
    "0x16613524e02ad97edfeF371bC883F2F5d6C480A5",  # Voter
    "0x827922686190790b37229fd06084350E74485b72",  # Slipstream Position Manager
}


@dataclass(frozen=True)
class TrackedFlow:
    timestamp: int
    tx_hash: str
    token_symbol: str
    token_contract: str
    direction: str  # deposit | inflow
    amount: float
    counterparty: str
