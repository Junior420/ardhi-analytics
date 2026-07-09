"""Data ingestion: bring external observations into the comparables database.

Pipeline (source-agnostic): raw records -> field mapping -> normalize &
validate -> deduplicate against existing rows -> insert with provenance.
Adapters turn a specific format (CSV, partner JSON) into raw dicts; everything
downstream is shared.

Design choices:
- Every ingested row is provenance-stamped: contributor = "ingest:<source>",
  and the original source string is preserved.
- Deduplication uses comps.dedup_hash so re-running a feed, or overlapping
  feeds, never double-count a transaction.
- dry_run previews exactly what a commit would do (insert / skip / reject)
  without writing — the safe default for the admin UI.

Live HTML portal scraping is intentionally NOT done here: it needs per-site
selectors, robots.txt/ToS compliance, and rate limiting, and it is fragile to
run from CI. A future `HtmlListingAdapter` can produce the same raw-record
shape these functions consume; the pipeline below is unchanged by its arrival.
"""

from __future__ import annotations

import csv
import io
from typing import Iterable, Optional

from . import comps

# Canonical comp fields an adapter must map onto.
_STR_FIELDS = ("kind", "use", "region", "district", "observed_date", "source", "notes")
_VALID_KIND = {"sale", "rent"}
_VALID_USE = {"residential", "commercial", "land"}
_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}(-\d{2})?$")


def _to_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(str(v).replace(",", "").replace(" ", ""))


def normalize(raw: dict, source: str) -> tuple[Optional[dict], Optional[str]]:
    """Return (record, None) if valid, else (None, reason)."""
    try:
        rec = {k: str(raw.get(k, "")).strip() for k in _STR_FIELDS}
        rec["kind"] = rec["kind"].lower() or "sale"
        rec["use"] = rec["use"].lower() or "residential"
        rec["currency"] = str(raw.get("currency", "TZS")).strip() or "TZS"
        price = _to_float(raw.get("price"))
        area = _to_float(raw.get("area_sqm"))
    except (ValueError, TypeError) as e:
        return None, f"unparseable number: {e}"

    if rec["kind"] not in _VALID_KIND:
        return None, f"invalid kind {rec['kind']!r}"
    if rec["use"] not in _VALID_USE:
        return None, f"invalid use {rec['use']!r}"
    if not rec["region"] or not rec["district"]:
        return None, "missing region/district"
    if price is None or price <= 0:
        return None, "missing or non-positive price"
    if area is not None and area <= 0:
        return None, "non-positive area"
    if not _DATE_RE.match(rec["observed_date"]):
        return None, f"bad observed_date {rec['observed_date']!r} (want YYYY-MM[-DD])"

    rec["price"] = price
    rec["area_sqm"] = area
    rec["source"] = rec["source"] or source
    rec["contributor"] = f"ingest:{source}"
    return rec, None


def ingest(raws: Iterable[dict], source: str, dry_run: bool = False) -> dict:
    """Validate, dedup, and (unless dry_run) insert. Returns a summary with
    per-row rejection reasons and dedup counts."""
    inserted = skipped_duplicate = 0
    rejected: list[dict] = []
    seen_hashes: set[str] = set()
    preview: list[dict] = []

    for i, raw in enumerate(raws):
        rec, reason = normalize(raw, source)
        if rec is None:
            rejected.append({"row": i, "reason": reason})
            continue
        h = comps.dedup_hash(rec)
        # dedup against both the DB and earlier rows in this same batch
        if h in seen_hashes or comps.hash_exists(h):
            skipped_duplicate += 1
            continue
        seen_hashes.add(h)
        if dry_run:
            preview.append({k: rec[k] for k in ("kind", "use", "district",
                                                "price", "area_sqm", "observed_date")})
        else:
            comps.add_comp({**rec, "dedup_hash": h})
        inserted += 1

    return {
        "source": source,
        "dry_run": dry_run,
        "inserted": inserted,
        "skipped_duplicate": skipped_duplicate,
        "rejected": rejected,
        "rejected_count": len(rejected),
        "preview": preview if dry_run else None,
    }


# ---- adapters -----------------------------------------------------------

def from_csv(text_data: str, source: str, dry_run: bool = False,
             mapping: Optional[dict] = None) -> dict:
    """Ingest a CSV. Header names should match the canonical fields, or supply
    `mapping` = {canonical_field: csv_column} to translate a partner's schema."""
    reader = csv.DictReader(io.StringIO(text_data))
    if reader.fieldnames is None:
        raise ValueError("empty CSV or missing header row")

    def rows():
        for row in reader:
            if mapping:
                yield {canon: row.get(col) for canon, col in mapping.items()}
            else:
                yield row

    return ingest(rows(), source, dry_run)


def from_json(records: list[dict], source: str, dry_run: bool = False,
              mapping: Optional[dict] = None) -> dict:
    """Ingest a list of JSON objects (e.g. a partner/portal API payload)."""
    def rows():
        for obj in records:
            if mapping:
                yield {canon: obj.get(col) for canon, col in mapping.items()}
            else:
                yield obj

    return ingest(rows(), source, dry_run)
