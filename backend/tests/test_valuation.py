import pytest

from finance_core import (
    Comparable, dcf_value, direct_capitalization, npv, reconcile_approaches,
    sales_comparison,
)
from tests.test_projections import simple_deal


class TestDirectCap:
    def test_basic(self):
        assert direct_capitalization(80_000, 0.08) == pytest.approx(1_000_000)

    def test_rejects_zero_cap(self):
        with pytest.raises(ValueError):
            direct_capitalization(80_000, 0)


class TestDCF:
    def test_flat_perpetual_style_deal(self):
        # NOI 80k for 5 yrs + sale 1,000,000 (80k / 8% cap, no selling costs),
        # discounted at 10%: hand-check against npv().
        a = simple_deal()
        expected = npv(0.10, [0, 80_000, 80_000, 80_000, 80_000, 1_080_000])
        assert dcf_value(a) == pytest.approx(expected, abs=1e-6)

    def test_independent_of_asking_price(self):
        assert dcf_value(simple_deal()) == pytest.approx(
            dcf_value(simple_deal(purchase_price=2_000_000)), rel=1e-9)


class TestSalesComparison:
    def comps(self):
        return [
            Comparable("Comp A", 100_000_000, {"location": 0.05, "size": -0.02}),
            Comparable("Comp B", 110_000_000, {"condition": -0.05}),
            Comparable("Comp C", 95_000_000, {}, weight=2.0),
        ]

    def test_adjusted_values(self):
        out = sales_comparison(self.comps())
        by_name = {x["name"]: x for x in out.adjusted}
        assert by_name["Comp A"]["adjusted_value"] == pytest.approx(103_000_000)
        assert by_name["Comp B"]["adjusted_value"] == pytest.approx(104_500_000)
        assert by_name["Comp C"]["adjusted_value"] == pytest.approx(95_000_000)

    def test_weighted_reconciliation(self):
        out = sales_comparison(self.comps())
        expected = (103_000_000 + 104_500_000 + 95_000_000 * 2) / 4
        assert out.reconciled_value == pytest.approx(expected)

    def test_gross_adjustment_warning(self):
        out = sales_comparison([Comparable("Weak", 100_000_000,
                                           {"location": 0.20, "size": -0.15})])
        assert out.gross_adjustment_warning

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            sales_comparison([])


class TestReconciliation:
    def test_weighted(self):
        out = reconcile_approaches(
            {"income_direct_cap": 1_000_000, "sales_comparison": 1_100_000},
            {"income_direct_cap": 2.0, "sales_comparison": 1.0})
        assert out["reconciled_value"] == pytest.approx((2_000_000 + 1_100_000) / 3)

    def test_skips_missing(self):
        out = reconcile_approaches({"income_dcf": None, "sales_comparison": 900_000})
        assert out["reconciled_value"] == pytest.approx(900_000)

    def test_all_missing_rejected(self):
        with pytest.raises(ValueError):
            reconcile_approaches({"income_dcf": None})
