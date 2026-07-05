const form = document.getElementById("dealForm");
const errBox = document.getElementById("error");
const pctFields = ["vacancy_rate", "rent_growth", "expense_growth", "exit_cap_rate",
                   "selling_costs_rate", "discount_rate", "ltv", "annual_rate"];

document.getElementById("useLoan").addEventListener("change", (e) => {
  document.getElementById("loanFields").style.display = e.target.checked ? "" : "none";
});

function collectDeal() {
  const f = new FormData(form);
  const num = (k) => parseFloat(f.get(k));
  const pct = (k) => num(k) / 100;
  const deal = {
    name: f.get("name") || "Untitled deal",
    jurisdiction: "tz",
    currency: "TZS",
    use: f.get("use"),
    tenure: f.get("tenure"),
    buyer_resident: document.getElementById("buyerResident").checked,
    is_crowdfunded: document.getElementById("isCrowdfunded").checked,
    purchase_price: num("purchase_price"),
    gross_rent_annual: num("gross_rent_annual"),
    vacancy_rate: pct("vacancy_rate"),
    operating_expenses_annual: num("operating_expenses_annual"),
    rent_growth: pct("rent_growth"),
    expense_growth: pct("expense_growth"),
    hold_years: parseInt(f.get("hold_years"), 10),
    exit_cap_rate: pct("exit_cap_rate"),
    selling_costs_rate: pct("selling_costs_rate"),
    discount_rate: pct("discount_rate"),
  };
  if (document.getElementById("useLoan").checked) {
    deal.loan = {
      ltv: pct("ltv"),
      annual_rate: pct("annual_rate"),
      term_years: num("term_years"),
      interest_only_years: num("interest_only_years") || 0,
    };
  }
  return deal;
}

const fmt = (v) => "TZS " + Math.round(v).toLocaleString("en-US");
const pctFmt = (v) => v == null ? "n/a" : (v * 100).toFixed(2) + "%";

function tile(label, value) {
  return `<div class="tile"><div class="k">${label}</div><div class="v">${value}</div></div>`;
}

function render(r) {
  const m = r.metrics;
  let tiles = [
    tile("Levered IRR", pctFmt(m.levered_irr)),
    tile("Unlevered IRR", pctFmt(m.unlevered_irr)),
    tile("Entry cap rate", pctFmt(m.entry_cap_rate)),
    tile("Equity multiple", m.equity_multiple.toFixed(2) + "x"),
    tile("Cash-on-cash (yr 1)", pctFmt(m.cash_on_cash_year1)),
    tile("NPV (levered)", fmt(m.levered_npv)),
    tile("NOI (yr 1)", fmt(m.noi_year1)),
    tile("Equity invested", fmt(m.equity_invested)),
  ];
  if (m.dscr_year1 !== undefined) {
    tiles.push(tile("DSCR (yr 1)", m.dscr_year1.toFixed(2)),
               tile("LTV", pctFmt(m.ltv)),
               tile("Debt yield", pctFmt(m.debt_yield)),
               tile("Break-even occupancy", pctFmt(m.break_even_occupancy)));
  }
  document.getElementById("tiles").innerHTML = tiles.join("");

  const head = "<tr><th>Year</th><th>GPI</th><th>EGI</th><th>Opex</th><th>NOI</th><th>Debt svc</th><th>Cash flow</th></tr>";
  const rows = r.years.map((y) =>
    `<tr><td>${y.year}</td><td>${fmt(y.gross_potential_income)}</td><td>${fmt(y.effective_gross_income)}</td>` +
    `<td>${fmt(y.operating_expenses)}</td><td>${fmt(y.noi)}</td><td>${fmt(y.debt_service)}</td>` +
    `<td>${fmt(y.cash_flow_after_debt)}</td></tr>`).join("");
  document.getElementById("cfTable").innerHTML = head + rows;

  document.getElementById("exitTiles").innerHTML = [
    tile(`Gross sale price (yr ${r.sale.year})`, fmt(r.sale.gross_sale_price)),
    tile("Net proceeds to equity", fmt(r.sale.net_sale_proceeds_levered)),
    tile("Loan payoff", fmt(r.sale.loan_payoff)),
    tile(`Est. CGT (${pctFmt(r.disposal_taxes.cgt_rate)})`, fmt(r.disposal_taxes.capital_gains_tax)),
    tile("Stamp duty (acq.)", fmt(r.acquisition_costs.stamp_duty)),
    tile("Total acquisition costs", fmt(r.acquisition_costs.total)),
    tile(`Rent WHT / yr (${pctFmt(r.rental_withholding.rate)})`, fmt(r.rental_withholding.annual_withholding)),
  ].join("");

  document.getElementById("flags").innerHTML =
    r.compliance_flags.map((f) => `<li>${f.message}</li>`).join("");
  document.getElementById("steps").innerHTML =
    r.procedure_steps.map((s) => `<li>${s.step} (~${s.typical_days} days)</li>`).join("");
  document.getElementById("disclaimer").textContent =
    `Rule pack: ${r.rulepack.jurisdiction} v${r.rulepack.version} (${r.rulepack.status}, reviewed ${r.rulepack.last_reviewed}). ${r.disclaimer}`;

  document.getElementById("placeholderCard").style.display = "none";
  document.getElementById("results").classList.add("visible");
}

async function post(path) {
  errBox.textContent = "";
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectDeal()),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || res.statusText));
  }
  return res;
}

function renderScenarios(data, hasLoan) {
  const irrKey = hasLoan ? "levered_irr" : "unlevered_irr";
  const head = "<tr><th>Scenario</th><th>IRR</th><th>NPV</th><th>Equity multiple</th><th>DSCR (yr 1)</th></tr>";
  const rows = ["pessimistic", "base", "optimistic"].map((name) => {
    const s = data.scenarios[name];
    return `<tr><td>${name[0].toUpperCase() + name.slice(1)}</td><td>${pctFmt(s[irrKey])}</td>` +
      `<td>${fmt(s.levered_npv)}</td><td>${s.equity_multiple.toFixed(2)}x</td>` +
      `<td>${s.dscr_year1 != null ? s.dscr_year1.toFixed(2) : "n/a"}</td></tr>`;
  }).join("");
  document.getElementById("scenTable").innerHTML = head + rows;
}

function renderSensitivity(data) {
  const head = "<tr><th>Driver</th><th>Downside IRR</th><th>Base IRR</th><th>Upside IRR</th><th>Swing</th></tr>";
  const rows = data.tornado.map((r) =>
    `<tr><td>${r.param.replace("loan.", "").replaceAll("_", " ")}</td><td>${pctFmt(r.downside)}</td>` +
    `<td>${pctFmt(r.base)}</td><td>${pctFmt(r.upside)}</td><td>${pctFmt(r.swing)}</td></tr>`).join("");
  document.getElementById("tornTable").innerHTML = head + rows;

  const g = data.grid;
  const gHead = "<tr><th>exit cap \\ growth</th>" +
    g.col_values.map((v) => `<th>${pctFmt(v)}</th>`).join("") + "</tr>";
  const gRows = g.matrix.map((row, i) =>
    `<tr><td>${pctFmt(g.row_values[i])}</td>` +
    row.map((v) => `<td>${pctFmt(v)}</td>`).join("") + "</tr>").join("");
  document.getElementById("gridTable").innerHTML = gHead + gRows;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("analyzeBtn");
  btn.disabled = true;
  try {
    const hasLoan = document.getElementById("useLoan").checked;
    const [analysis, scen, sens] = await Promise.all([
      post("/api/analyze").then((r) => r.json()),
      post("/api/scenarios").then((r) => r.json()),
      post("/api/sensitivity").then((r) => r.json()),
    ]);
    render(analysis);
    renderScenarios(scen, hasLoan);
    renderSensitivity(sens);
  } catch (err) {
    errBox.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

async function refreshSavedDeals() {
  const res = await fetch("/api/deals");
  const deals = await res.json();
  const sel = document.getElementById("savedDeals");
  sel.innerHTML = '<option value="">— select a saved deal —</option>' +
    deals.map((d) => `<option value="${d.id}">${d.name} (${d.created_at.slice(0, 10)})</option>`).join("");
}

function fillForm(deal) {
  const set = (name, v) => { const el = form.elements[name]; if (el && v != null) el.value = v; };
  const setPct = (name, v) => { if (v != null) set(name, Math.round(v * 10000) / 100); };
  set("name", deal.name); set("use", deal.use); set("tenure", deal.tenure);
  set("purchase_price", deal.purchase_price);
  set("gross_rent_annual", deal.gross_rent_annual);
  set("operating_expenses_annual", deal.operating_expenses_annual);
  set("hold_years", deal.hold_years);
  setPct("vacancy_rate", deal.vacancy_rate); setPct("rent_growth", deal.rent_growth);
  setPct("expense_growth", deal.expense_growth); setPct("exit_cap_rate", deal.exit_cap_rate);
  setPct("selling_costs_rate", deal.selling_costs_rate); setPct("discount_rate", deal.discount_rate);
  document.getElementById("buyerResident").checked = !!deal.buyer_resident;
  document.getElementById("isCrowdfunded").checked = !!deal.is_crowdfunded;
  const hasLoan = !!deal.loan;
  document.getElementById("useLoan").checked = hasLoan;
  document.getElementById("loanFields").style.display = hasLoan ? "" : "none";
  if (hasLoan) {
    setPct("ltv", deal.loan.ltv); setPct("annual_rate", deal.loan.annual_rate);
    set("term_years", deal.loan.term_years);
    set("interest_only_years", deal.loan.interest_only_years);
  }
}

document.getElementById("saveBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  try {
    await post("/api/deals");
    await refreshSavedDeals();
  } catch (err) { errBox.textContent = err.message; }
});

document.getElementById("loadBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  const id = document.getElementById("savedDeals").value;
  if (!id) return;
  try {
    const res = await fetch(`/api/deals/${id}`);
    if (!res.ok) throw new Error("could not load deal");
    fillForm(await res.json());
  } catch (err) { errBox.textContent = err.message; }
});

refreshSavedDeals().catch(() => {});

document.getElementById("pdfBtn").addEventListener("click", async () => {
  const btn = document.getElementById("pdfBtn");
  btn.disabled = true;
  try {
    const res = await post("/api/report");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (collectDeal().name || "deal").replace(/\s+/g, "_") + "_appraisal.pdf";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    errBox.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

const MARKET_LABELS = {
  inflation_cpi_yoy: "Inflation (CPI y/y)", gdp_growth: "GDP growth",
  lending_rate: "Lending rate", policy_rate: "Policy rate (CBR)",
  mortgage_rate_typical: "Typical mortgage rate", usd_tzs: "USD/TZS",
};

async function loadMarket() {
  try {
    const res = await fetch("/api/market/tz");
    if (!res.ok) throw new Error("market data unavailable");
    const snap = await res.json();
    const tiles = Object.entries(snap.series).map(([key, p]) => {
      const label = MARKET_LABELS[key] || key.replaceAll("_", " ");
      const value = p.unit === "fraction" ? pctFmt(p.value) : p.value.toLocaleString("en-US");
      const badge = p.provenance === "live" ? "" :
        ` <span style="font-size:10px;color:var(--muted)">(${p.provenance}${p.stale ? ", stale" : ""})</span>`;
      return tile(label + badge, value);
    });
    document.getElementById("marketTiles").innerHTML = tiles.join("");
    document.getElementById("marketNote").textContent =
      "Sources: " + [...new Set(Object.values(snap.series).map((p) => p.source.split(" - ")[0].split(" — ")[0]))].join("; ") +
      ". Reference-tagged values are curated drafts — verify before reliance.";
  } catch (e) {
    document.getElementById("marketTiles").innerHTML =
      '<div class="placeholder" style="padding:10px">Market data unavailable (offline)</div>';
  }
}
loadMarket();
