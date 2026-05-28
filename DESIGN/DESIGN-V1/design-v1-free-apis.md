# hedgeAdvisor2 — design-v1-free-apis

This is the source-of-truth list of **free or open-data APIs** that can populate risk-factor components in V2. Each entry includes: what it provides, how to access, registration / cost, rate limits, license, and which audience(s) it serves.

> **Discipline:** every API below was confirmed during the design pass via web search on 2026-05-23 (citations on those searches are in `design-v1-risk-factor-catalog.md`). If at code-time any of these APIs has moved or changed shape, the component file's `source.ref` field surfaces that immediately and V2 fails honestly rather than substituting.

---

## 1. Monetary policy and rate curves (universal — anchors `base_sofr`)

### FRED — Federal Reserve Economic Data
- **What:** ~800,000 US economic time series including SOFR (`SOFR`), Effective Federal Funds Rate (`FEDFUNDS`), 10-Year Treasury (`DGS10`), VIX, CPI, Industrial Production, ISRATIO, ECOMPCTSA, and many more.
- **Access:** REST + JSON, https://api.stlouisfed.org/fred/...
- **Auth:** **free API key** (32-char alphanumeric), register at https://fred.stlouisfed.org with a user account.
- **Rate limit:** generous (in practice not the bottleneck for V2 workloads).
- **License:** US government, public-domain-equivalent.
- **Audiences:** all (US base rate is in every V2 profile).

### ECB Statistical Data Warehouse (SDW)
- **What:** Euro-area policy rates, sovereign yield curves, banking lending rates.
- **Access:** REST + JSON/XML, https://sdw-wsrest.ecb.europa.eu/service/
- **Auth:** none.
- **License:** ECB open-data terms (attribution required).
- **Audience:** EU-based businesses (future scope).

### Bank of Japan time-series
- **What:** TONA (Tokyo Overnight Average), JGB curve, BoJ policy rate, Tankan business sentiment.
- **Access:** BoJ Time-Series Data Search: https://www.stat-search.boj.or.jp/index_en.html — CSV download; no REST API as such, but a documented download URL pattern.
- **Auth:** none.
- **License:** BoJ open-data; attribution required.
- **Audience:** Japan profiles (`jp-*.json`).

### Reserve Bank of India — Database on Indian Economy (DBIE)
- **What:** repo rate, MIBOR, INR/USD reference rate, sectoral lending rates, Industrial Outlook Survey.
- **Access:** https://dbie.rbi.org.in — interactive + CSV download. RBI does **not** publish a REST API; the V2 component file points at the CSV URL and a parsing rule.
- **Auth:** none.
- **License:** RBI public data; attribution.
- **Audience:** India profiles (`in-*.json`).

---

## 2. Trade flow and tariff data (anchors `tariff_gtap_quadratic`)

### UN Comtrade
- **What:** annual + monthly trade flows by HS code × reporter × partner. The authoritative source for what actually moves.
- **Access:** https://comtradeplus.un.org/ — REST + JSON.
- **Auth:** free registration. Free tier allows data previews, download up to 100,000 records per call, and up to 500 API calls per day.
- **License:** UN open-data, attribution to UNSD.
- **Audience:** export-import profiles.

### World Bank WITS (World Integrated Trade Solution)
- **What:** integrated tariff (UNCTAD-TRAINS, WTO IDB/CTS) and trade-flow (UN Comtrade) data with built-in trade-policy simulation (SMART).
- **Access:** REST API documented at https://wits.worldbank.org/witsapiintro.aspx
- **Auth:** none (UN Comtrade portion has the same limits as direct UN Comtrade access).
- **License:** World Bank open-data terms.
- **Audience:** export-import profiles. SMART partial-equilibrium simulator is the closest free analog to a GTAP-lite for tariff scenarios.

### USITC HTSUS (US tariff schedule)
- **What:** the legal US import tariff at the 10-digit HS level, with Section 301 add-ons.
- **Access:** https://hts.usitc.gov — search UI, also bulk JSON/XML downloads of the full schedule.
- **Auth:** none.
- **License:** US government, public domain.
- **Audience:** any US-import profile.

### USTR press releases / Federal Register
- **What:** active tariff changes (the legal source for "tariff went from 25% to 50% as of date X").
- **Access:** https://ustr.gov/ + Federal Register API at https://www.federalregister.gov/developers/documentation/api/v1
- **Auth:** none for Federal Register; rate-limited but generous.
- **License:** US government, public domain.
- **Audience:** export-import profiles for time-bounded tariff schedules.

---

## 3. Supply-chain pressure indices (anchors `port_congestion_indexed` and similar)

### NY Fed Global Supply Chain Pressure Index (GSCPI)
- **What:** composite of Baltic Dry, Harpex container ship rates, BLS in/outbound price indices, and PMI sub-indices for delivery times, backlogs, and purchased stocks across the US, China, Japan, Euro-area, South Korea, Taiwan, and the UK.
- **Access:** monthly CSV publication at https://www.newyorkfed.org/research/policy/gscpi.
- **Auth:** none.
- **License:** Fed, public.
- **Audience:** all (any business affected by global logistics).

### World Bank Global Supply Chain Stress Index (GSCSI)
- **What:** alternative composite. Useful because the two indexes diverged in 2024-2025 — combining them gives robustness.
- **Access:** World Bank Data API. https://data.worldbank.org/
- **Auth:** none.
- **License:** CC-BY.
- **Audience:** all.

### World Bank Container Port Performance Index (CPPI)
- **What:** annual ranking of container ports by efficiency. The 2024 edition reported resurgence of stress in global maritime supply chains stemming from the Red Sea crisis and ongoing climate-related disruptions at the Panama Canal.
- **Access:** PDF + spreadsheet download from World Bank Open Knowledge.
- **Auth:** none.
- **License:** CC-BY.
- **Audience:** port-sensitive profiles.

### Drewry World Container Index (WCI) — *freemium*
- **What:** weekly composite container freight rate ($/40ft) on the 8 major lanes.
- **Access:** https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry — landing page free, historical CSV requires registration or subscription.
- **Note:** **freemium**, not fully free. Mentioned because it is the canonical container-rate reference; V2's first cut uses GSCPI instead.

### Commercial port-congestion APIs (Portcast, GoComet, Vizion, SeaVantage)
- **What:** real-time vessel-level wait times, terminal dwell, predictive ETAs across 400-600 ports.
- **Access:** REST APIs, **paid only** (typical $10K-50K/year tier).
- **License:** commercial.
- **Note:** mentioned per user's ask. **Not used in V2's free-API tier.** Available as an optional paid component upgrade in a profile.

---

## 4. Commodity prices and energy

### EIA Open Data (US Energy Information Administration)
- **What:** daily crude oil (WTI, Brent), natural gas, gasoline, electricity, propane prices and inventories.
- **Access:** https://www.eia.gov/opendata/ — REST + JSON.
- **Auth:** free API key.
- **License:** US government, public.
- **Audience:** oil/gas/fuel-import profiles.

### USDA Economic Research Service / Market News
- **What:** agricultural commodity prices, livestock, dairy, fruit & vegetable shipments.
- **Access:** https://www.ers.usda.gov/data-products/ + https://www.marketnews.usda.gov/mnp/
- **Auth:** none, some free API access via MarketNews public endpoints.
- **License:** US government, public.
- **Audience:** food/agri profiles.

### LME / CME public delayed quotes
- **What:** copper, aluminum, zinc, nickel, lead, tin spot + LME 3-month at ~30-min delay; CME crude/gold/silver similar.
- **Access:** LME website + CME website public pages; **no first-party free REST API**. Yahoo Finance / Alpha Vantage have free tiers that scrape these.
- **Audience:** metal-input profiles.

### Alpha Vantage / Yahoo Finance — *limited free*
- **What:** broad market data including commodities and FX.
- **Access:** REST. Alpha Vantage free tier 5 calls/min, 500/day. Yahoo unofficial.
- **License:** free-tier terms; Yahoo's status is grey.
- **Note:** convenient for prototyping; the V2 production profile should bind to primary sources (EIA, LME) not aggregators.

---

## 5. Country-specific sources for the Japan and India expansion

### Japan
| What | Source | URL | Free? |
|---|---|---|---|
| Base rate (TONA), JGB curve, policy | Bank of Japan time series | https://www.stat-search.boj.or.jp/ | yes |
| Business sentiment (PMI-equivalent) | BoJ Tankan + au Jibun PMI | BoJ + S&P Global free pages | yes (release-day) |
| Trade data | Japan Customs Trade Statistics | https://www.customs.go.jp/toukei/info/index_e.htm | yes |
| Industrial production | METI (Ministry of Economy, Trade and Industry) | https://www.meti.go.jp/english/statistics/ | yes |
| FX (JPY/USD) | BoJ reference rate; Fed H.10 | https://www.federalreserve.gov/releases/h10/ | yes |
| Ports / logistics | MLIT port statistics | https://www.mlit.go.jp/en/statistics/index.html | yes |

### India
| What | Source | URL | Free? |
|---|---|---|---|
| Policy rates (repo, MIBOR), INR/USD reference | RBI DBIE | https://dbie.rbi.org.in | yes |
| Industrial sentiment | RBI Industrial Outlook Survey | RBI quarterly publications | yes |
| Trade data | DGFT / DGCI&S | https://commerce-app.gov.in/eidb/ | yes |
| GDP and macro | MOSPI | https://www.mospi.gov.in/ | yes |
| Port handling | Indian Ports Association | https://www.ipa.nic.in/ | yes |
| Currency intervention / reserves | RBI Weekly Statistical Supplement | RBI website | yes |

Note for both: most Indian and Japanese sources publish CSV / XLS rather than REST APIs. V2's component file points at the download URL + parsing rule. This is normal for government open data outside the US.

---

## 6. Small-business and sectoral data (anchors domestic-mode components)

### US Census Bureau APIs
- **What:** Retail Trade (incl. ECOMPCTSA — e-commerce % of retail), Monthly Retail Trade (MRTS), Manufacturers' Shipments / Inventories / Orders (M3), Annual Business Survey, Statistics of US Businesses (SUSB), International Trade (FT900).
- **Access:** https://api.census.gov/data
- **Auth:** free API key at https://api.census.gov/data/key_signup.html
- **License:** US government, public.
- **Audience:** all US-domestic profiles. **The most important free source for V2's domestic mode.**

### Bureau of Labor Statistics (BLS) Public Data API
- **What:** CPI, PPI (incl. sectoral PPI), unemployment, employment, hourly earnings, productivity.
- **Access:** https://www.bls.gov/developers/
- **Auth:** free registration for v2 API (key gives higher rate limits).
- **License:** US government, public.
- **Audience:** all US-domestic profiles.

### Bureau of Economic Analysis (BEA) API
- **What:** GDP by industry, personal consumption by category, international transactions.
- **Access:** https://apps.bea.gov/api/
- **Auth:** free API key.
- **License:** US government, public.
- **Audience:** US-domestic profiles.

### Federal Reserve Small Business Credit Survey (SBCS)
- **What:** annual survey of US small business credit access, financial health, cash flow challenges.
- **Access:** https://www.fedsmallbusiness.org/ — publications, downloadable datasets.
- **Auth:** none.
- **License:** Fed, public.
- **Audience:** all domestic profiles, especially `*_default loan_spread` calibration.

### Atradius Payment Practices Barometer
- **What:** annual global survey of B2B payment behavior across 31 countries; ~6,500 companies.
- **Access:** https://group.atradius.com/publications/ — free PDF download.
- **Auth:** registration recommended.
- **License:** © Atradius, free for research use with attribution.
- **Audience:** `payment_cycle_stress_dso` component calibration globally.

### JPMorgan Chase Institute small business datasets
- **What:** transaction-level analyses of millions of US small business bank accounts; the definitive dataset on cash buffers and volatility.
- **Access:** https://www.jpmorganchase.com/institute — free reports and underlying data summaries.
- **Auth:** none.
- **License:** free for research, attribution required.

### Intuit QuickBooks Small Business Cash Flow / Late Payments Reports
- **What:** annual cash-flow sentiment and late-payment behavior surveys (~2,500 US small businesses + UK).
- **Access:** Intuit's research site, free PDF.
- **License:** free with attribution.

### US Chamber / MetLife Small Business Index
- **What:** quarterly sentiment + concerns survey; Q4 2025 showed 74% comfortable with cash flow, but very-comfortable fell from 31% (Q3) to 24% (Q4).
- **Access:** https://www.uschamber.com/sbindex — free quarterly publications.

---

## 7. License and compliance considerations

| API class | License pattern | What V2 must do |
|---|---|---|
| US federal (FRED, Census, BLS, BEA, EIA) | public domain / open | attribute in audit_log + provenance report |
| World Bank, IMF, UN | CC-BY-style | attribute |
| Central banks (Fed, ECB, BoJ, RBI) | open with attribution | attribute |
| Industry reports (Atradius, JPM Chase Institute, Intuit) | free with attribution; not for resale | attribute; never embed full report text in V2 outputs |
| Commercial APIs (Portcast etc.) | paid only | flagged in profile; component disabled unless API key present |

The Provenance Agent (N6a) emits every binding so the audit trail satisfies these terms automatically.

---

## 8. What to do BEFORE binding a profile to any API

Per the V1 discipline ("no hallucinations, no hardcoding, no fallbacks"):

1. **Smoke test the endpoint.** A one-shot curl with documented credentials, captured to disk, dated.
2. **Verify the response schema.** Lock the field paths V2's component-file parser will rely on.
3. **Pin a snapshot** for the regression test fixture so re-binding the component does not silently break.
4. **Document failure modes.** What happens if FRED is down? V2 fails honestly (Give-Up agent), never falls back to a stale cached value as if live — UNLESS the profile explicitly authorises a "use last cached within N days" rule, in which case the staleness is in the audit log.

The first cut of V2 binds **only FRED + Census + BLS** for live data — they're the most stable and they cover the most-needed components. Other APIs are scaffolded but not bound until their smoke tests pass.

---

## 9. The "no live API" V2 path

V2 must also work **fully offline** for the regression test and for users who don't want live calls. In that mode:
- Every component file declares its source as `{"type": "config_file", "ref": "..."}` pointing to a static snapshot.
- The Provenance agent stamps `source_freshness: "snapshot"` and the snapshot date.
- The recommendation report includes "this analysis used cached data as of [date]" prominently.

This is also the **CI mode**: regression tests never hit live APIs. The `india-us-textiles.json` byte-equality test runs entirely against static snapshots, which is why it can be deterministic.

---

**End of design-v1-free-apis.md**
