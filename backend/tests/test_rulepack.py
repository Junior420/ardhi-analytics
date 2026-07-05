import pytest

from app import rulepack


@pytest.fixture
def pack():
    return rulepack.load("tz")


def test_loads_tanzania_pack(pack):
    assert pack["jurisdiction"] == "TZ"
    assert pack["status"] == "draft"


def test_unknown_jurisdiction():
    with pytest.raises(FileNotFoundError):
        rulepack.load("xx")


def test_acquisition_costs(pack):
    costs = rulepack.acquisition_costs(pack, 100_000_000)
    assert costs["stamp_duty"] == pytest.approx(1_000_000)      # 1%
    assert costs["registration_fee"] == pytest.approx(50_000)
    assert costs["total"] == pytest.approx(sum(v for k, v in costs.items() if k != "total"))


def test_disposal_taxes_resident_vs_not(pack):
    res = rulepack.disposal_taxes(pack, 150_000_000, 100_000_000, resident=True)
    non = rulepack.disposal_taxes(pack, 150_000_000, 100_000_000, resident=False)
    assert res["capital_gains_tax"] == pytest.approx(5_000_000)   # 10% of 50m
    assert non["capital_gains_tax"] == pytest.approx(10_000_000)  # 20% of 50m


def test_no_tax_on_loss(pack):
    out = rulepack.disposal_taxes(pack, 90_000_000, 100_000_000)
    assert out["capital_gains_tax"] == 0


def test_rental_withholding(pack):
    out = rulepack.rental_withholding(pack, 54_000_000, "residential")
    assert out["annual_withholding"] == pytest.approx(5_400_000)


def test_conditional_flags(pack):
    base = {f["id"] for f in rulepack.compliance_checklist(pack)}
    assert "land_rent_arrears" in base
    assert "non_resident_buyer" not in base

    flagged = {f["id"] for f in rulepack.compliance_checklist(
        pack, buyer_non_resident=True, is_crowdfunded=True)}
    assert {"non_resident_buyer", "crowdfunding_offer"} <= flagged


def test_procedure_steps(pack):
    steps = rulepack.procedure_steps(pack)
    assert len(steps) >= 5
    assert all("step" in s for s in steps)
