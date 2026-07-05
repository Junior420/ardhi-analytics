"""Live market data connectors with provenance, caching, and fallback.

Resolution order for every series: live API -> cached value (marked stale)
-> curated reference data (marked draft). Every DataPoint carries its source,
retrieval time, and provenance so reports can cite where numbers came from.
"""

from .base import DataPoint, FetchError, fetch_json
from .service import market_snapshot

__all__ = ["DataPoint", "FetchError", "fetch_json", "market_snapshot"]
