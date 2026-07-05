"""Seed the comparables DB with ILLUSTRATIVE SAMPLE records for demos/dev.

These are NOT real transactions. Every record is labeled as sample data.
Run from backend/:  python -m scripts.seed_comps
"""

from app import comps

SOURCE = "Illustrative sample data — NOT real transactions"

SAMPLES = [
    # Dar es Salaam residential sales (price TZS, area m² of building)
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=420_000_000, area_sqm=310, observed_date="2026-03"),
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=505_000_000, area_sqm=350, observed_date="2026-01"),
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=380_000_000, area_sqm=290, observed_date="2025-11"),
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=460_000_000, area_sqm=335, observed_date="2026-04"),
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=350_000_000, area_sqm=250, observed_date="2026-05"),
    dict(kind="sale", use="residential", region="Dar es Salaam", district="Ilala",
         price=290_000_000, area_sqm=240, observed_date="2026-02"),
    # Residential annual rents
    dict(kind="rent", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=42_000_000, area_sqm=300, observed_date="2026-04"),
    dict(kind="rent", use="residential", region="Dar es Salaam", district="Kinondoni",
         price=36_000_000, area_sqm=260, observed_date="2026-02"),
    # Commercial sale
    dict(kind="sale", use="commercial", region="Dar es Salaam", district="Ilala",
         price=1_200_000_000, area_sqm=620, observed_date="2025-12"),
]


def main() -> None:
    for rec in SAMPLES:
        comps.add_comp({**rec, "currency": "TZS", "source": SOURCE,
                        "contributor": "sample-data", "notes": "seeded for demo"})
    print(f"Seeded {len(SAMPLES)} illustrative comparables.")


if __name__ == "__main__":
    main()
