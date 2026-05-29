# DTCC Blockchain / DLT Research — Consolidated (Sessions 1–4)

> **NOTE ON PLACEMENT:** This is external-market research about DTCC's tokenization /
> DLT initiatives. It is **not** a `hedgeAdvisor2` design document. It lives in the dedicated
> `hedgeAdvisor2/research/` folder (moved here 2026-05-29 from DESIGN/DESIGN-V1, where it
> did not match the `design-v1-*` design-doc convention). Possible thematic link to
> hedgeAdvisor2: the DTCC pilot tokenizes exactly
> Russell 1000 equities + US Treasuries + index ETFs — the same asset classes a hedge
> advisor reasons about — so this may be background for a future tokenized-asset mode.
> That link is an **assumption**, not a stated requirement.

**Status conventions** (same discipline as the design docs):
- **VERIFIED** — read directly from a cited primary source (URL/PDF given inline).
- **INFERENCE** — reasoned but not directly confirmed; flagged explicitly.
- **WATCH** — not yet verified against a primary source; do not treat as fact.

**Last updated:** 2026-05-29 (Session 4). **Author:** Claude (Opus 4.8).

---

## 1. DTCC multi-chain strategy — VERIFIED baseline (Sessions 1–2)

DTCC is pursuing several chains in parallel, not one:

- **Hyperledger Besu → "AppChain"** — Chainlink CRE (Cross-Chain Runtime Environment)
  selected 2026-05-12; AppChain launch targeted **Q4 2026**.
- **Canton Network** — used for Treasuries; MVP targeted **H1 2026**.
- **Stellar** — DTCC's first *public* chain; DTC-tokenized assets targeted **H1 2027**;
  announced **2026-05-27**.
- **Ethereum** — earlier private/permissioned work.
- **Chainlink** — oracle / CCIP / CRE infrastructure layer across the above.

> Dates above are stated **targets**, not committed go-lives (see §6 WATCH).

---

## 2. SEC No-Action Letter — VERIFIED primary source (Session 4)

**Source (read in full, text-extractable PDF):**
`https://www.sec.gov/files/tm/no-action/dtc-nal-121125.pdf`
SEC Division of Trading and Markets staff letter **dated 2025-12-11**, with DTC's request
letter of the same date attached.

**What it is:** SEC staff declines to recommend enforcement against DTC for launching the
**"Preliminary Base Version"** of the DTCC Tokenization Services. Relief is granted from
four provision sets: **Reg SCI**; **Section 19(b) / Rule 19b-4** (and Title VIII §806(e)
advance-notice); the **Covered Clearing Agency Standards, Rule 17Ad-22(e)**; and
**Rule 17Ad-25(i) and (j)**. Relief **self-withdraws three years after launch**.

**Eligible assets ("Subject Securities") — the previously-open watch-list item, now CONFIRMED.**
Limited to three categories (identical in the staff response and DTC request representation #2):
1. Securities in the **Russell 1000 Index** at launch, plus later additions (a security stays
   eligible even if subsequently dropped from the index);
2. **U.S. Treasury securities** (bills, bonds, notes);
3. **ETFs that track major indices**, "such as the S&P 500 index and Nasdaq-100 index."

**Design facts:**
- **No collateral or settlement value** ascribed to Tokenized Entitlements (no Net Debit Cap
  / Collateral Monitor value) — so DTC never relies on them to manage a participant default.
- **Blockchain-neutral by design.** The letter "would not prescribe a particular blockchain
  ... or a particular tokenization protocol." It names **zero specific chains**. The only named
  protocol is **ERC 3643**, cited as an example "compliance-aware" standard (supports
  distribution control + transaction reversibility). DTC will publish an approved-chain list later.
- **Named systems:** **Factory** (DTCC's tokenization/minting framework), **LedgerScan**
  (off-chain cloud system that scans blockchains; its record is DTC's official books and
  records), **Digital Omnibus Account** (prevents double-spend), per-blockchain **"root wallet"**
  (override keys to force-convert/burn tokens for "Conditions Requiring Reversal").
- Registered ownership stays in **Cede & Co.** (DTC's nominee) throughout; Article 8 UCC
  framework unchanged.

**Timeline (primary-sourced):**
- **Fall 2025** — internal proof-of-concept, synthetic data only, no real value.
- **Early 2026** — one or more production MVPs/pilots: select participants, a live blockchain,
  real assets of limited value.
- **H2 2026** — Preliminary Base Version launch (the relief applies only to this version).

**Scale:** letter states DTC custodies **"over $100 trillion"** as of 2025, citing DTCC's own
press release "Surpasses $100 Trillion in Assets Under Custody" (2025-06-18). This makes the
**$100T+** figure primary-sourced. (The specific **$114T** figure and the
**~$3.7–4 quadrillion/yr** throughput figure are NOT in this document — see §6 WATCH.)

**People named:** Brian Steele (MD, President, Clearing & Securities Services, DTCC) and
Nadine Chakar (MD, Global Head of DTCC Digital Assets) signed the request; SEC side:
Jeffrey Mooney (Associate Director), cc Jamie Selway (Director, Division of Trading and Markets).

---

## 3. The DTCC patents — VERIFIED primary source (Sessions 2–3)

One patent family, same inventor **George Daniel Doney**, assignee **DTCC Digital US Inc**:

- **Granted: US12190385B2** — granted 2025-01-07 (read in full, Session 2).
- **Pending application: US20250078162A1** — pub. 2025-03-06, legal status **Pending**
  (read in full via Google Patents HTML render, Session 3). Same title, inventor, assignee,
  and specification text as the grant. Priority chain:
  18/953,875 → 17/869,884 → 16/861,769 → 16/851,184 → provisional 62/839,969 (filed 2019-04-29).

**Contents relevant to the chain question:**
- Example DLT networks (FIG 13A): **Bitcoin, Ethereum, Stellar** — explicitly illustrative
  ("any number of or any type"). Identical across both patents.
- FIG 17 example transfer: a generic **"ABC token"** moved from a user node on **Stellar** to a
  user node on **Ripple DLT System**. Generic placeholder; the **"Steller" typo** appears in both.
- Token standards named: **ERC-20, ERC-721, ERC-1400, ERC-1616, ERC-1643**.
- Currencies/crypto named: Ether (ETH), Bitcoin (BTC), USD (OCR-garbled "USO"), EUR.

**KEY CORRECTION (triple-confirmed across the family):** there is **NO "XRP" and NO "XRPL"**
anywhere in the spec. **"Ripple DLT System"** is a generic example destination *ledger*, peer to
BTC/ETH/Stellar, with zero special treatment and no token-level role. Secondary sources
(genfinity.io 2025-05-22; a YouTube video) that frame the patent as "integrating XRP and XLM"
**overstate it** — the spec names *ledgers* as routing examples, not *tokens* as bridge assets.

- The granted patent's **cited prior-art** references include two **Ripple Labs** patents
  (US20210192501A1, US11551191B2 "on-demand liquidity"). These are cited **against** Doney
  (a citation relationship) — the **opposite** of a design dependency.

**INFERENCE (not verified this session):** US20250078162A1 also names **PayPal + SWIFT**
(as example traditional value-transfer networks) and **"Cascade"** (as an example external
provider) in the bridge/ontology section — payment-rail examples, NOT blockchains, NOT claimed
elements. Assumed to appear identically in granted US12190385B2 (same disclosure) but **not
re-verified verbatim** in the grant. Verify if it matters.

---

## 4. The Ripple / XRP connection — VERIFIED as corporate-only

- **XRPL is absent** from DTCC's chosen chains (§1) and from the tokenization pilot (§2,
  which names no chains at all).
- Ripple's link to DTCC is **corporate, not technical**:
  - Ripple acquired **Hidden Road** ($1.25B, closed late 2025) → rebranded **Ripple Prime**.
  - Hidden Road appears in the **NSCC MPID directory** ~2026-03-02 (clearing code 0443,
    alpha **HRFI**, OTC-only) — a routine broker listing.
  - Hidden Road is a named participant in DTCC's tokenization **Industry Working Group**
    (release 2026-05-04).
- The **"patent + Hidden Road acquisition + NSCC listing = XRP becomes the Wall Street bridge
  asset"** narrative is an **XRP-community thesis, NOT a DTCC statement**. Nothing in the
  primary sources (patents §3, no-action letter §2, chain strategy §1) supports a token-level
  role for XRP.

---

## 5. Primary sources read (verbatim) across sessions

- `https://www.sec.gov/files/tm/no-action/dtc-nal-121125.pdf` — SEC no-action letter (Session 4, full).
- `https://patents.google.com/patent/US12190385B2/` — granted patent (Session 2, full).
- `https://patents.google.com/patent/US20250078162A1/` — pending application (Session 3, full).

---

## 6. WATCH — not yet verified against primary sources

1. **$114T custody** and **~$3.7–4 quadrillion/yr** throughput — secondary sources only.
   ($100T+ is now primary-sourced via the no-action letter; the larger/specific figures are not.)
   DTCC.com blocks bot fetch.
2. **2026–2027 dates** (§1) are stated **targets**, not committed go-lives.
3. **PayPal / SWIFT / Cascade** verbatim presence in *granted* US12190385B2 (see §3 INFERENCE).

**Resolved this session (removed from watch):** the SEC no-action letter's eligible-asset list
was the last unread authoritative source — now read in full (§2).

---

## 7. Open question carried forward

- The user has not yet decided whether this research belongs in this design folder long-term.
  See the placement note at the top.
