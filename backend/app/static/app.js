function authHeaders() {
  const t = localStorage.getItem("ardhi_token");
  return t ? { Authorization: "Bearer " + t } : {};
}

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
    headers: { "Content-Type": "application/json", ...authHeaders() },
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
  const res = await fetch("/api/deals", { headers: authHeaders() });
  if (res.status === 401) {
    document.getElementById("savedDeals").innerHTML = '<option value="">— sign in to save/load deals —</option>';
    return;
  }
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
    const res = await fetch(`/api/deals/${id}`, { headers: authHeaders() });
    if (!res.ok) throw new Error("could not load deal");
    fillForm(await res.json());
  } catch (err) { errBox.textContent = err.message; }
});

refreshSavedDeals().catch(() => {});

document.getElementById("pdfBtn").addEventListener("click", async () => {
  const btn = document.getElementById("pdfBtn");
  btn.disabled = true;
  try {
    const res = await post("/api/report?template=" + document.getElementById("pdfTemplate").value);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (collectDeal().name || "deal").replace(/\s+/g, "_") + "_" + document.getElementById("pdfTemplate").value + ".pdf";
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

function compFilters() {
  return {
    kind: document.getElementById("cKind").value,
    use: document.getElementById("cUse").value,
    region: document.getElementById("cRegion").value || null,
    district: document.getElementById("cDistrict").value || null,
  };
}

function renderCompStats(s) {
  const tiles = [tile("Comps", s.count), tile("With area", s.count_with_area)];
  if (s.unit_price_median != null) {
    tiles.push(tile("Median TZS/m²", Math.round(s.unit_price_median).toLocaleString("en-US")),
               tile("Range TZS/m²", `${Math.round(s.unit_price_min).toLocaleString("en-US")} – ${Math.round(s.unit_price_max).toLocaleString("en-US")}`),
               tile("Confidence", s.confidence));
  } else {
    tiles.push(tile("Confidence", s.confidence));
  }
  document.getElementById("compTiles").innerHTML = tiles.join("");
  document.getElementById("compNote").textContent = s.note ||
    (s.date_range ? `Evidence from ${s.date_range[0]} to ${s.date_range[1]}. Screening statistics, not a valuation.` : "");
}

document.getElementById("addCompBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  const body = {
    ...compFilters(),
    price: parseFloat(document.getElementById("cPrice").value),
    area_sqm: parseFloat(document.getElementById("cArea").value) || null,
    observed_date: document.getElementById("cDate").value,
    source: document.getElementById("cSource").value,
    contributor: "web-ui",
  };
  const res = await fetch("/api/comps", {
    method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify(body),
  });
  if (res.status === 401) { errBox.textContent = "Sign in (Account section) to contribute comparables."; return; }
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    errBox.textContent = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail || "invalid comp");
    return;
  }
  document.getElementById("statsBtn").click();
});

document.getElementById("statsBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  const f = compFilters();
  const qs = new URLSearchParams(Object.fromEntries(Object.entries(f).filter(([, v]) => v)));
  renderCompStats(await (await fetch(`/api/comps/stats?${qs}`)).json());
});

document.getElementById("indicateBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  const area = parseFloat(document.getElementById("subjArea").value);
  if (!area) { errBox.textContent = "Enter a subject area first."; return; }
  const res = await fetch("/api/comps/indicate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...compFilters(), area_sqm: area }),
  });
  const out = await res.json();
  if (out.indicated_value != null) {
    renderCompStats(out.stats);
    document.getElementById("compTiles").innerHTML =
      tile("Indicated value", fmt(out.indicated_value)) +
      tile("Range", `${fmt(out.indicated_range[0])} – ${fmt(out.indicated_range[1])}`) +
      document.getElementById("compTiles").innerHTML;
    document.getElementById("compNote").textContent = out.note;
  } else {
    document.getElementById("compNote").textContent = out.note;
  }
});

function renderAuthState() {
  const email = localStorage.getItem("ardhi_email");
  document.getElementById("authForms").style.display = email ? "none" : "";
  document.getElementById("authStatus").style.display = email ? "" : "none";
  if (email) document.getElementById("authWho").textContent = email;
}

async function authCall(path) {
  errBox.textContent = "";
  const res = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: document.getElementById("authEmail").value,
      password: document.getElementById("authPassword").value,
    }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    errBox.textContent = typeof body.detail === "string" ? body.detail : "authentication failed";
    return;
  }
  localStorage.setItem("ardhi_token", body.access_token);
  localStorage.setItem("ardhi_email", body.user.email);
  renderAuthState();
  refreshSavedDeals().catch(() => {});
}

document.getElementById("loginBtn").addEventListener("click", () => authCall("/api/auth/login"));
document.getElementById("registerBtn").addEventListener("click", () => authCall("/api/auth/register"));
document.getElementById("logoutBtn").addEventListener("click", () => {
  localStorage.removeItem("ardhi_token");
  localStorage.removeItem("ardhi_email");
  renderAuthState();
  refreshSavedDeals().catch(() => {});
});
renderAuthState();

document.getElementById("mcBtn").addEventListener("click", async () => {
  errBox.textContent = "";
  const btn = document.getElementById("mcBtn");
  btn.disabled = true;
  btn.textContent = "Simulating…";
  try {
    const res = await fetch("/api/montecarlo", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ deal: collectDeal(), n: 1000 }),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(typeof b.detail === "string" ? b.detail : "simulation failed");
    }
    const mc = await res.json();
    document.getElementById("mcTiles").innerHTML = [
      tile("Median IRR", pctFmt(mc.irr.median)),
      tile("90% interval", `${pctFmt(mc.irr.p5)} – ${pctFmt(mc.irr.p95)}`),
      tile("P(IRR < 0)", pctFmt(mc.irr.prob_below_zero)),
      tile("P(NPV < 0)", pctFmt(mc.npv.prob_below_zero)),
      tile("P(equity multiple < 1x)", pctFmt(mc.equity_multiple.prob_below_one)),
      tile("Median NPV", fmt(mc.npv.median)),
    ].join("");

    const total = mc.histogram.counts.reduce((a, b) => a + b, 0);
    const max = Math.max(...mc.histogram.counts);
    document.getElementById("mcBars").innerHTML = mc.histogram.counts.map((c, i) => {
      const lo = mc.histogram.bin_edges[i], hi = mc.histogram.bin_edges[i + 1];
      const share = ((c / total) * 100).toFixed(1);
      return `<div title="IRR ${pctFmt(lo)} to ${pctFmt(hi)}: ${c} draws (${share}%)"` +
        ` style="flex:1; min-width:4px; height:${max ? Math.round((c / max) * 100) : 0}%;` +
        ` background:#0d8a6a; border-radius:4px 4px 0 0"></div>`;
    }).join("");
    document.getElementById("mcLo").textContent = pctFmt(mc.histogram.bin_edges[0]);
    document.getElementById("mcMid").textContent = "median " + pctFmt(mc.irr.median);
    document.getElementById("mcHi").textContent = pctFmt(mc.histogram.bin_edges.at(-1));
    document.getElementById("mcChart").style.display = "";
    document.getElementById("mcNote").textContent =
      `${mc.n_effective} of ${mc.n} draws produced a defined IRR (base case ${pctFmt(mc.base_irr)}). ` +
      "Gaussian shocks on rent, growth, vacancy, expenses, exit cap and loan rate. Hover bars for detail.";
  } catch (err) {
    errBox.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run simulation (1,000 draws)";
  }
});

// ---- Swahili localization (first pass): UI chrome is translated; standard
// financial jargon (IRR, NPV, DSCR, cap rate) stays in English, matching
// Tanzanian professional practice.
const SW = {
  "Real estate finance & investment analysis — Tanzania rule pack v1 (draft)":
    "Uchambuzi wa fedha na uwekezaji wa mali isiyohamishika — kanuni za Tanzania v1 (rasimu)",
  "Deal inputs": "Taarifa za mradi",
  "Deal name": "Jina la mradi",
  "Use": "Matumizi", "Residential": "Makazi", "Commercial": "Biashara",
  "Tenure": "Umiliki",
  "Granted right of occupancy": "Hati ya umiliki (granted)",
  "Customary / village land": "Ardhi ya kimila / kijiji",
  "TIC derivative right": "Haki tegemezi ya TIC",
  "Other": "Nyingine",
  "Purchase price (TZS)": "Bei ya ununuzi (TZS)",
  "Gross annual rent (TZS)": "Kodi ya mwaka, jumla (TZS)",
  "Vacancy rate %": "Kiwango cha nafasi wazi %",
  "Annual opex (TZS)": "Gharama za uendeshaji kwa mwaka (TZS)",
  "Rent growth %/yr": "Ukuaji wa kodi %/mwaka",
  "Expense growth %/yr": "Ukuaji wa gharama %/mwaka",
  "Hold period (years)": "Muda wa kushikilia (miaka)",
  "Selling costs %": "Gharama za mauzo %",
  "Finance with a mortgage": "Nunua kwa mkopo wa nyumba",
  "Interest rate %/yr": "Riba %/mwaka",
  "Term (years)": "Muda wa mkopo (miaka)",
  "Interest-only (years)": "Riba pekee (miaka)",
  "Buyer is a Tanzanian resident": "Mnunuzi ni mkazi wa Tanzania",
  "Crowdfunded offering": "Uwekezaji wa umati (crowdfunding)",
  "Analyze deal": "Chambua mradi",
  "Report template": "Aina ya ripoti",
  "Investor appraisal": "Tathmini ya mwekezaji",
  "Bank collateral report": "Ripoti ya dhamana ya benki",
  "Valuer workpaper (IVS)": "Karatasi ya mthamini (IVS)",
  "Download PDF": "Pakua PDF",
  "Account": "Akaunti",
  "Email": "Barua pepe",
  "Password (8+ chars)": "Nenosiri (herufi 8+)",
  "Sign in": "Ingia", "Register": "Jisajili", "Sign out": "Toka",
  "Saved deals": "Miradi iliyohifadhiwa",
  "Save current": "Hifadhi", "Load selected": "Fungua",
  "Market data — Tanzania": "Takwimu za soko — Tanzania",
  "Comparables database": "Hifadhidata ya mauzo linganifu",
  "Kind": "Aina", "Sale": "Mauzo", "Rent (annual)": "Kodi (mwaka)",
  "Land": "Ardhi",
  "Region": "Mkoa", "District": "Wilaya",
  "Price (TZS)": "Bei (TZS)", "Area (m²)": "Eneo (m²)",
  "Observed (YYYY-MM)": "Tarehe (YYYY-MM)", "Source": "Chanzo",
  "Contribute comp": "Changia data", "Market stats": "Takwimu za soko",
  "Subject area (m²) for indication": "Eneo la mali (m²) kwa makadirio",
  "Indicate value": "Kadiria thamani",
  "Key metrics": "Vipimo muhimu",
  "Cash flow projection": "Makadirio ya mtiririko wa fedha",
  "Scenarios": "Mazingira",
  "Sensitivity — IRR drivers": "Usikivu — vichocheo vya IRR",
  "Monte Carlo — IRR distribution": "Monte Carlo — mgawanyo wa IRR",
  "Run simulation (1,000 draws)": "Endesha uigaji (mizunguko 1,000)",
  "Exit & taxes (draft Tanzania rule pack)": "Mauzo ya mwisho na kodi (kanuni za Tanzania, rasimu)",
  "Compliance checklist": "Orodha ya uzingatiaji wa sheria",
  "Transfer procedure": "Utaratibu wa uhamisho",
  "Exit cap rate %": "Exit cap rate %",
  "Discount rate %": "Discount rate %",
  "LTV %": "LTV %",
};

function applyLang(lang) {
  document.querySelectorAll("h2, label, button, option, p, span").forEach((el) => {
    if (el.children.length > 0 || el.id === "langBtn") return;
    if (el.dataset.orig === undefined) el.dataset.orig = el.textContent.trim();
    const orig = el.dataset.orig;
    if (lang === "sw" && SW[orig]) el.textContent = SW[orig];
    else if (lang === "en") el.textContent = orig;
  });
  document.getElementById("langBtn").textContent = lang === "sw" ? "English" : "Kiswahili";
  localStorage.setItem("ardhi_lang", lang);
}

document.getElementById("langBtn").addEventListener("click", () => {
  applyLang(localStorage.getItem("ardhi_lang") === "sw" ? "en" : "sw");
});
if (localStorage.getItem("ardhi_lang") === "sw") applyLang("sw");
