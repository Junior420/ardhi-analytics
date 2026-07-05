"""Golden tests for loan math, verified against published amortization tables."""

import pytest

from finance_core import amortization_schedule, annual_debt_service, payment, remaining_balance


class TestPayment:
    def test_standard_30yr_mortgage(self):
        # 100,000 @ 6% / 30yr monthly = 599.55 (published)
        assert payment(100_000, 0.06, 30) == pytest.approx(599.55, abs=0.01)

    def test_15yr_mortgage(self):
        # 200,000 @ 5% / 15yr monthly = 1,581.59 (published)
        assert payment(200_000, 0.05, 15) == pytest.approx(1581.59, abs=0.01)

    def test_zero_rate(self):
        assert payment(120_000, 0.0, 10) == pytest.approx(1000.0)

    def test_rejects_zero_term(self):
        with pytest.raises(ValueError):
            payment(100_000, 0.05, 0)


class TestSchedule:
    def test_fully_amortizes(self):
        sched = amortization_schedule(100_000, 0.06, 30)
        assert len(sched) == 360
        assert sched[-1].balance == pytest.approx(0.0, abs=0.5)

    def test_first_period_split(self):
        # First payment on 100k @ 6%: interest = 500.00, principal = 99.55
        sched = amortization_schedule(100_000, 0.06, 30)
        assert sched[0].interest == pytest.approx(500.00, abs=0.01)
        assert sched[0].principal == pytest.approx(99.55, abs=0.01)

    def test_interest_only_phase(self):
        sched = amortization_schedule(100_000, 0.06, 30, interest_only_years=5)
        # During IO: payment == interest, balance unchanged
        assert sched[0].payment == pytest.approx(500.0, abs=0.01)
        assert sched[59].balance == pytest.approx(100_000.0)
        # After IO: amortizes over remaining 25 years, ends at zero
        assert sched[-1].balance == pytest.approx(0.0, abs=0.5)
        assert sched[60].principal > 0

    def test_io_longer_than_term_rejected(self):
        with pytest.raises(ValueError):
            amortization_schedule(100_000, 0.06, 10, interest_only_years=10)


class TestRemainingBalance:
    def test_after_5_years(self):
        # 100k @ 6% / 30yr: balance after 60 payments ≈ 93,054 (published)
        bal = remaining_balance(100_000, 0.06, 30, 60)
        assert bal == pytest.approx(93_054, abs=2)

    def test_before_start_and_after_end(self):
        assert remaining_balance(100_000, 0.06, 30, 0) == 100_000
        assert remaining_balance(100_000, 0.06, 30, 360) == pytest.approx(0.0, abs=0.5)


class TestAnnualDebtService:
    def test_first_year(self):
        ads = annual_debt_service(100_000, 0.06, 30)
        assert ads == pytest.approx(599.55 * 12, abs=0.2)

    def test_io_first_year(self):
        ads = annual_debt_service(100_000, 0.06, 30, interest_only_years=1)
        assert ads == pytest.approx(6000.0, abs=0.01)
