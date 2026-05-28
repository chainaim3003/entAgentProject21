# hedgeAdvisor2 — design-v1-risk-factor-catalog

This document catalogues the risk factors that can drive the SOFR-path components in V2, organised by the three audiences the user identified:

- **(a)** Export-import businesses (the V1 case + extensions)
- **(b)** Ecommerce / supply-demand and global-supply-chain businesses
- **(c)** Domestic small businesses generally

For each factor: **what it is**, **where it comes from (primary source)**, **how it lands in a profile component**, and **which businesses it applies to**.

> **Discipline note:** every factor below maps to either an existing free-data source (see `design-v1-free-apis.md`) or an explicit "OPEN — needs source" tag. Nothing is asserted as a usable factor without a citable source.

---

## (a) Export-import risk factors

### a.1 Tariff escalation — the V1 anchor factor

**What:** the applied tariff rate on the imported commodity, current and projected peak, multiplied by Armington elasticity (substitutability between domestic and foreign-origin varieties of the same good) and pass-through (the fraction of the tariff that flows into the importer's purchase price rather than being absorbed by the foreign producer).

**Primary sources:**
- **USTR HTSUS** (Harmonised Tariff Schedule of the US): https://hts.usitc.gov — the legal applied tariffs by HS code, including Section 301 add-ons.
- **WITS / UNCTAD-TRAINS** (free): https://wits.worldbank.org — applied and bound tariffs by country pair × HS code, going back years.
- **GTAP database** for Armington elasticities: https://www.gtap.agecon.purdue.edu/databases/v11/. A 2019 meta-analysis of 3,524 estimates puts the Armington elasticity range at 2.5-5.1 with a median of 3.8.

**Maps to component:** `tariff_gtap_quadratic` (V1 formula preserved verbatim).

**Applies to:** any business with cross-border goods exposure on either the input or the output side.

### a.2 Shipping line closures / corridor disruption

**What:** transit-time and cost shocks from a specific shipping lane closing (Red Sea/Suez 2024-2025, Panama Canal drought 2024). Affects working-capital cycle (longer DSO, more inventory in transit) and direct logistics cost (rerouted via Cape of Good Hope adds ~2 weeks and ~$1M per voyage at typical FEU rates).

**Primary sources (free or freemium):**
- **NY Fed GSCPI** (free, monthly): https://www.newyorkfed.org/research/policy/gscpi. The GSCPI integrates variables from the Baltic Dry Index, Harpex container ship rate index, BLS in/outbound price indices, and PMI components on delivery times, backlogs, and purchased stocks across the US, China, Japan, Euro-area, South Korea, Taiwan, and the UK. Single composite index, standard-score scale.
- **World Bank GSCSI** (free, monthly): the Global Supply Chain Stress Index, alternative to GSCPI. The two indexes can diverge — in late 2025 the GSCSI showed stress at 2021-22 levels while the GSCPI showed normal levels, so combining them gives signal robustness.
- **World Bank CPPI** (Container Port Performance Index) — annual rankings, public. 2024 saw resurgence of stress from the Red Sea crisis and Panama Canal climate disruptions, with rerouting via Cape of Good Hope causing schedule unreliability and increased port congestion.
- **Commercial port-congestion feeds** (paid): Portcast, GoComet, Vizion — granular per-port. Mentioned because the user asked, but **NOT free**.

**Maps to component:** `port_congestion_indexed` (proposed, scaffolded in V2; activated when a profile binds it).

**Formula sketch:** `congestion_bps(t) = max(0, GSCPI(t) - GSCPI_threshold) × sensitivity_by_business_type`. Profile supplies the threshold and sensitivity; component file pulls the latest GSCPI from NY Fed at run-time (cached daily).

**Applies to:** export-import businesses where logistics cost is a meaningful share of COGS (i.e. anything bulky, perishable, time-sensitive).

### a.3 What moves through containers — commodity-level disruption

The user's specific ask: "what moves through these containers, beyond just oil prices going up." A container ship sailing US ↔ Asia carries thousands of HS codes. A blockade or rerouting affects different commodities differently:

- **Perishables (food, pharma)** — extra transit time has a direct shelf-life cost; pharma cold-chain breaks → discarded inventory.
- **Just-in-time inputs (auto parts, electronics)** — 1-week delay can shut a US plant. Toyota's experience after the 2011 Tohoku quake; Apple's 2025 supplier visibility briefings post-Suez.
- **Commodity inputs (metals, plastics, chemicals)** — buffers smooth short shocks; longer disruptions widen working-capital needs by 10-30%.
- **Finished consumer goods** — substitute origins; pricing power depends on Armington elasticity (the same parameter V1 already uses).

**Maps to component:** the **commodity-specific override in a profile**. The pattern is already in V1's Postman JS (`India-United States-pha` vs `India-United States-tex` overrides for pass-through and WC stress). V2 makes this a first-class file: `india-us-pharmaceuticals.json` has `pass_through: 0.15` (inelastic essentials) while `india-us-oil.json` has `pass_through: 0.30` (direct commodity pricing). The corridor file holds the base, the commodity file the override.

**Primary sources for commodity-specific disruption sensitivity:**
- **UN Comtrade** (free, register required): https://comtradeplus.un.org — actual trade flow shifts during disruption events. Register for free to access data previews, download up to 100K records per call, and enjoy up to 500 API calls per day.
- **WITS SMART** (free): partial-equilibrium tariff impact simulation by HS code.
- **USDA AMS** (free) for agricultural commodities: market shipping data, lane-level.
- **EIA** (free, US): https://www.eia.gov/opendata/ — oil, gas, fuel price daily.
- **LME / CME public quotes** (delayed, free) for industrial metals.

### a.4 FX translation risk for cross-border revenues

**What:** when costs are paid in one currency and revenues are in another, FX moves change the effective floating-rate exposure. A weaker INR raises the USD cost of Indian inputs for a US importer.

**Maps to component:** `fx_translation_pct_linear` (scaffolded). Inputs: home currency, revenue currency, spot, vol, share of revenue.

**Primary sources:** central-bank reference rates (free): Fed H.10, ECB SDW, BoJ, RBI WSS. **CurrencyAPI / exchangerate.host** (free, no key) for daily spot.

### a.5 Trade-finance gap / payment risk

**What:** counterparty payment risk in cross-border trade. The trade-finance gap is large — the user's V1 design cited ~$2.5T globally — and small exporters in EMs face documentary-credit availability shocks that affect their working-capital cost.

**Primary sources:**
- **ADB Trade Finance Gaps Report** (annual, free): https://www.adb.org/publications/2024-trade-finance-gaps
- **WTO Trade Statistics** (free): https://www.wto.org/english/res_e/statis_e/statis_e.htm
- **Atradius Payment Practices Barometer** (annual, free PDF) — DSO + payment-default rates by country/sector. Annual global survey across 31 countries, ~6,500 companies.

---

## (b) Ecommerce / supply-demand and global supply chain risk factors

The user's specific framing: "supply demand mismatch and how it can affect these hedges, particularly involved in global supply chain dimensions based on the US based business, and then expand same in to Japan and India."

### b.1 Demand volatility — the headline factor for consumer-facing businesses

**What:** swing in unit demand over the loan horizon, driven by macro consumer confidence, sector seasonality, channel shifts (the user's "ecommerce activities"). Demand volatility doesn't move SOFR directly — it moves the **bank's perceived credit risk on the loan**, which moves the **applied spread** the bank charges and the optionality value of the swap.

**Primary sources (free):**
- **U.S. Census Retail Trade** (E-commerce Quarterly Retail Sales Report): free, quarterly. https://www.census.gov/retail/ecommerce.html
- **FRED** — Retail Sales (RSAFS), E-Commerce as % of Retail (ECOMPCTSA), Personal Consumption Expenditures by category. FRED's free API covers SOFR, unemployment, CPI, and ~800,000 time series.
- **Conference Board Consumer Confidence Index** (free, lagged).
- **PMI surveys** (S&P Global / Markit) — release-day free.

**Maps to component:** `demand_volatility_vix_proxy` (proposed). Formula: convert a sector-PMI delta from neutral to a credit-spread bp adjustment with a profile-configurable sensitivity.

**Applies to:** all consumer-facing ecommerce, retail, hospitality. Less relevant for B2B SaaS where demand is contract-bound.

### b.2 Supply-demand mismatch — the inventory-cycle factor

**What:** in ecommerce, mismatches show up as either (i) stockouts (lost revenue, lower DSO from accelerated sales, but lasting brand cost) or (ii) gluts (excess inventory, longer DIO, higher carrying cost, eventual markdowns). Both affect working capital.

**Primary sources (free):**
- **Census M3 Survey** (Manufacturers' Shipments, Inventories, and Orders) — free, monthly. https://www.census.gov/manufacturing/m3/
- **Census MRTS** (Monthly Retail Trade Survey) — inventory-to-sales ratio.
- **FRED ISRATIO** — Retailers' Inventory-to-Sales Ratio (key signal — historic ~1.45; >1.6 = gluts, <1.3 = stockouts).
- **ISM Manufacturing PMI — Inventories sub-index** (free, monthly).

**Maps to component:** `inventory_carrying_dso_dpo` (proposed). Formula combines current ISR vs historic mean with sector-DIO sensitivity to produce a working-capital stress bp.

### b.3 Port congestion (the ecommerce-import angle)

Same source as (a.2) above — **NY Fed GSCPI** is the workhorse free source. An ecommerce business importing finished goods feels port congestion directly in DIO (longer transit → more in-transit inventory → more financed working capital).

### b.4 Last-mile and freight cost spikes

**What:** parcel and LTL freight rates. The 2024-2025 surface freight market has been volatile; that volatility flows into ecommerce COGS.

**Primary sources (free):**
- **BLS PPI for Truck Transportation** (PCU484121484121) — free, monthly.
- **DAT or Cass Freight Index** — partial free access; the Cass Index is widely cited.
- **USDA AMS Truck Rate Reports** — free, weekly.

**Maps to component:** rolled into `wc_trapezoidal` or its own `freight_cost_linear` if the business has high freight share.

### b.5 Payment-cycle stress (B2B ecommerce / marketplaces)

**What:** how long customers pay. Intuit QuickBooks' 2025 Small Business Late Payments Report surveyed 2,487 US small businesses; Atradius runs a similar global survey. Late payments compound directly into needed working capital.

**Primary sources (free reports, not all APIs):**
- **Federal Reserve Small Business Credit Survey** (annual, free): https://www.fedsmallbusiness.org/
- **Atradius Payment Practices Barometer** (annual, free PDF).
- **JPMorgan Chase Institute small business datasets** (free reports).
- **Intuit QuickBooks Small Business Late Payments Report** (annual, free).

**Maps to component:** `payment_cycle_stress_dso`. Formula: DSO above sector median → bp add to working-capital stress curve.

### b.6 Global supply chain dimensions for a US-based business expanding to Japan and India

The user's specific ask. The pattern is the same — pluggable components in a profile — but the **source data** changes country to country. See `design-v1-free-apis.md` §5 for the Japan/India source list. Summary:

| Risk factor | US source | Japan source | India source |
|---|---|---|---|
| Base policy rate | Fed (FRED) | BoJ (TONA / JGB curve via BoJ Time-Series, free) | RBI (MIBOR, repo rate, free) |
| Supply chain pressure | NY Fed GSCPI (Japan is a tracked region) | NY Fed GSCPI (Japan-specific component) + BoJ Tankan | RBI Industrial Outlook Survey (free) |
| Sector demand | Census, FRED | METI (Ministry of Economy, free statistics) | MOSPI / Statistics Ministry of India (free) |
| Trade data | Census FT900, BEA | Japan Customs Trade Statistics (free) | India DGFT / DGCI&S (free) |
| Port performance | World Bank CPPI | World Bank CPPI + Japan MLIT | World Bank CPPI + Indian Ports Association |

The profile file for `jp-ecommerce.json` looks structurally identical to `us-ecommerce.json` — only the `source.ref` URLs change.

---

## (c) Pain points and opportunities for small businesses generally

The user's broad ask. These are the risk factors that affect **any** small business, exporter or not, and are therefore candidates for the `derived_domestic` mode's component sets.

### c.1 Cash-flow volatility — the universal pain point

**Verified facts from 2025-2026 surveys:**

- 29% of SMB leaders ranked cash flow as their top concern in Q4 2025.
- Uneven cash flows affect 51% of small businesses, making it the third most common financial challenge. 75% of firms cite rising costs of goods, services, and/or wages as their primary financial challenge.
- A survey of 468 small business owners by OnDeck and Ocrolus showed Q4 2025 top concerns were inflation (31%) and cash flow (29%).

**Implication:** any small business with a floating-rate working-capital loan benefits from a hedge-vs-no-hedge analysis. The market is much wider than the V1 import-tariff slice.

**Maps to:** the existing `wc_trapezoidal` component with a profile that uses BLS/FRED-sourced working-capital metrics rather than V1's hardcoded textile DSO.

### c.2 Rising input costs (the inflation-pass-through factor)

- 34% said the rising cost of supplies and 31% said the rising cost of inflation have impacted their businesses in the past year.
- Two-thirds of retailers raised prices in 2025, but 56.1% met or exceeded their 2025 revenue projections — pricing power exists but is not unlimited.

**Maps to:** a new component `input_cost_passthrough_linear` (scaffolded). Inputs: sector PPI delta vs revenue CPI delta. Sources: BLS PPI series + FRED CPI series, both free.

### c.3 Borrowing cost itself

- Average small business bank loan rates ranged from about 6.3% to 11.5% in Q3 2025, depending on loan type and borrower risk. Online and alternative lenders can charge between 14% and 99% APR. The average rate paid on short-maturity small business loans was 9.1% in January 2026.

**Implication:** the spread V1 hard-codes at 250bps is reasonable for an IG corporate but **wildly wrong for an actual small business**. The profile must allow much higher spreads, and the breakpoint where hedging is worth the cost shifts significantly. V2's `loan_spread_default` in the profile is per-segment, not global.

### c.4 Debt overhang / credit access

- 39% of firms hold more than $100,000 in business debt, up from 31% in 2019. Among firms denied financing, 41% cited having too much existing debt, up from 22% in 2021.
- By late 2024, SBA had charged off more than $47 billion in COVID EIDL loans.

**Implication:** an additional **deal-killer** signal — if a small business is in debt-overhang territory, the right answer to "should I hedge?" may be "you cannot refinance even if you wanted to." V2 can scaffold a `creditworthiness_screen` component that fails the run honestly when the business profile indicates non-eligibility.

### c.5 Regulatory / compliance overhead

- 57% of small businesses said cumbersome regulation holds their business back. 73% feel the federal tax code is unfavorable to them.

**Implication:** not directly a SOFR-path driver, but it shows up in **margins available to absorb rate moves**. A profile field `regulatory_overhead_share_of_revenue` could feed a credit-spread sensitivity multiplier.

### c.6 Opportunities — where the small-business hedge advisor is differentiated

The user asked about opportunities, not just pain points. These are the angles where V2 creates value not available to small businesses today:

1. **Banks don't proactively offer hedge analysis to <$50M revenue businesses.** A swap-desk minimum is typically $5-10M notional. V2's deterministic core can run a defensible analysis on a $250K loan in seconds — banks won't do that economics.
2. **Treasurers at small businesses don't have CFA-level rate-modelling expertise.** V2 packages it as a prompt.
3. **The IFRS/US-GAAP disclosure side (V1's Disclosure Agent) is otherwise expensive consulting work.** V2 produces it deterministically as part of the run.
4. **The predicted-vs-realised drift loop (V1's Memory Agent) is the trust-builder.** Over 4 quarters of running V2, a small business owner sees whether the model's recommendations actually paid off — that's a feedback loop banks structurally cannot offer.

---

## Component-to-audience matrix

| Component | Export-import | Ecommerce | Domestic services | Domestic mfg |
|---|---|---|---|---|
| `base_sofr_fed_path_linear` | always | always | always | always |
| `tariff_gtap_quadratic` | yes | only if import-heavy | rare | only if input-import-heavy |
| `sovereign_trapezoidal` | yes (counterparty country) | no | no | no |
| `wc_trapezoidal` | yes | yes | yes | yes |
| `demand_volatility_vix_proxy` | optional | **yes (core)** | yes | yes |
| `inventory_carrying_dso_dpo` | optional | **yes (core)** | no | yes |
| `payment_cycle_stress_dso` | yes | yes | **yes (core)** | yes |
| `port_congestion_indexed` | yes | yes (if imports) | no | yes (if imports) |
| `fx_translation_pct_linear` | yes (multi-ccy) | yes (cross-border ecom) | yes (if cross-border) | yes (if cross-border) |
| `input_cost_passthrough_linear` | yes | yes | yes | yes |

Each cell is configurable — a profile decides whether to enable the component. **No component is a code-level on/off.** Adding a new audience is adding a new profile that selects a different column subset.

---

## What's deliberately NOT in the catalog (for V2 scope)

- **Credit default models** (Merton, KMV) — that's a bank-internal concern; V2 is a customer-facing advisor.
- **VaR / CVaR portfolio aggregation** — Phase 2 (a Portfolio-Rollup right-wing agent).
- **Climate risk / physical risk** — important but not yet wired to the rate-curve channels here; reserved for V3 with a `climate_event_stress` component.
- **Cyber disruption risk** — same; explicit V3 component scaffold.

---

**End of design-v1-risk-factor-catalog.md**
