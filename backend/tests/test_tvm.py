"""Golden tests for TVM functions, verified against Excel."""

from datetime import date

import pytest

from finance_core import irr, mirr, npv, xirr, xnpv


class TestNPV:
    def test_excel_verified(self):
        # Excel: =NPV(10%, 500,500,500) - 1000 = 243.4260
        assert npv(0.10, [-1000, 500, 500, 500]) == pytest.approx(243.4260, abs=1e-3)

    def test_zero_rate_sums(self):
        assert npv(0.0, [-1000, 400, 700]) == pytest.approx(100.0)

    def test_rejects_rate_below_negative_one(self):
        with pytest.raises(ValueError):
            npv(-1.0, [-100, 50])


class TestIRR:
    def test_excel_verified(self):
        # Excel: =IRR({-1000,400,400,400,400}) = 21.8623%
        assert irr([-1000, 400, 400, 400, 400]) == pytest.approx(0.218623, abs=1e-5)

    def test_npv_at_irr_is_zero(self):
        flows = [-5000, 1200, 1500, 1800, 2100]
        rate = irr(flows)
        assert npv(rate, flows) == pytest.approx(0.0, abs=1e-4)

    def test_no_sign_change_returns_none(self):
        assert irr([100, 200, 300]) is None

    def test_negative_irr(self):
        # Total repayment below investment → IRR below zero
        rate = irr([-1000, 300, 300, 300])
        assert rate is not None and rate < 0
        assert npv(rate, [-1000, 300, 300, 300]) == pytest.approx(0.0, abs=1e-4)


class TestXIRR:
    def test_excel_verified(self):
        # Excel XIRR example: -10000 on 2008-01-01; 2750 (3/1), 4250 (10/30),
        # 3250 (2009-02-15), 2750 (2009-04-01) = 37.3363%
        flows = [
            (date(2008, 1, 1), -10000.0),
            (date(2008, 3, 1), 2750.0),
            (date(2008, 10, 30), 4250.0),
            (date(2009, 2, 15), 3250.0),
            (date(2009, 4, 1), 2750.0),
        ]
        assert xirr(flows) == pytest.approx(0.373363, abs=1e-4)

    def test_xnpv_at_xirr_is_zero(self):
        flows = [(date(2025, 1, 1), -1_000_000.0), (date(2026, 6, 1), 600_000.0),
                 (date(2027, 12, 31), 700_000.0)]
        rate = xirr(flows)
        assert xnpv(rate, flows) == pytest.approx(0.0, abs=1e-2)


class TestMIRR:
    def test_excel_verified(self):
        # Excel: =MIRR({-120000,39000,30000,21000,37000,46000}, 10%, 12%) = 12.6094%
        flows = [-120000, 39000, 30000, 21000, 37000, 46000]
        assert mirr(flows, 0.10, 0.12) == pytest.approx(0.126094, abs=1e-5)

    def test_no_positives_returns_none(self):
        assert mirr([-100, -50], 0.1, 0.1) is None
