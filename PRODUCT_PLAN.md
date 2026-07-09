# Product Plan — Employee Management System (EMS)

Turning the current Docker-based EMS into a **downloadable, paid, cross-platform
desktop product** for any company.

> **Status:** Planning only. **Nothing is being built yet.** No development starts
> until the owner explicitly approves a phase. This document is the agreed plan to
> review before any work begins.

---

## 1. Goal

Sell the EMS as a downloadable app that a company can pay for, install, and run on
their own machine(s) — managing staff/contractors, ID cards, and NFC door access.

## 2. Product shape — "local host + native launcher"

One architecture that scales from a single-person office to a whole company:

- One office machine is the **host**. A single installer puts the app, a bundled
  database, and the hardware bridge on it, wrapped in a small **native launcher**
  (start/stop, status, license).
- That host is fully usable **standalone** for a small office.
- Other staff on the same network connect via **browser over the LAN** → multi-user
  for larger companies. Same product, 1 user or many.

## 3. Packaging changes vs. today

| Area | Today | Product |
|---|---|---|
| Distribution | `docker compose` | Native installers (`.msi` / `.dmg` / `.AppImage`) |
| Dependencies | Requires Docker Desktop | Zero — everything bundled |
| Database | Postgres container | Bundled Postgres (same engine for every install size) |
| Redis | Container | Replaced with in-process equivalents |
| Launch | Terminal | Native launcher (**Tauri** — small downloads) |
| Hardware bridge | Manual host process | Bundled, optional, auto-detected |

**Decision (2026-07-09): Postgres everywhere — no SQLite tier.** One database
engine for every customer, from a 1-person office to a large company. Rejected a
SQLite "Lite" tier to avoid maintaining two DB code paths (the app already uses
Postgres-specific types — JSONB/UUID — that a SQLite tier would need to work
around) and to avoid a painful SQLite→Postgres migration if a small customer
grows. The bundled Postgres runs as a quiet background service managed by the
native launcher, alongside the backend and hardware bridge processes it already
manages.

## 4. Hardware — optional, plug-and-play, bring-your-own

- The app **runs fully without any hardware.** The NFC reader and card printer are
  **optional add-ons** that light up when a device is connected.
- **Hardware choice is left to each company.** We do not require or bundle specific
  devices — customers use whatever NFC reader and card printer they already own or
  prefer to buy. Driver installation is a standard OS step handled by the customer.
- Hardware is **never required to run and never blocks a release.** The riskiest
  part (the card printer) is isolated to an optional module.
- **Compatibility is a standard, not a guarantee of a specific model:**
  - NFC: any **PC/SC-compliant** reader (the near-universal standard — ACR122U,
    Omnikey, Identiv, etc. all qualify).
  - Printer: any printer reachable via the **OS print queue**, sized for CR80 cards;
    Zebra printers additionally get a dedicated ZPL path in the bridge.
- **Trade-off, stated plainly:** because hardware isn't fixed to a certified
  shortlist, we can't prove "it will work" for every possible device the way a
  locked-down shortlist would let us. The mitigation is (a) building to the open
  standard rather than one vendor's SDK, (b) failing clearly and visibly when a
  device doesn't cooperate (no reader detected / print failed — never a silent or
  confusing failure), and (c) treating unusual devices as best-effort support
  after release rather than a pre-launch guarantee.
- A **known-good shortlist is still offered as a recommendation** (not a
  requirement) for customers who don't already own hardware and want the least-risk
  option:
  - NFC reader: ACS ACR122U · alternatives: HID Omnikey 5427, Identiv uTrust 3700 F.
  - Card printer: Zebra ZC300 (dedicated ZPL path in the bridge) · alternatives:
    Evolis Primacy 2, Magicard 300 · Evolis Badgy200 as a cheap starter.
  - Consumables (ongoing): colour ribbon (~$100–200, roughly £80–160), blank CR80
    PVC cards (~$30–60 / 500, roughly £25–48 / 500).
  - *Prices are rough 2026 ballparks — verify before buying.*

## 5. Paid-product layers (separate from packaging)

1. **Licensing / activation** — signed keys, **offline** validation + **online**
   seat/revocation checks, via **Lemon Squeezy** (decided 2026-07-09 — see below).
2. **Payments / distribution** — **Lemon Squeezy**, same vendor as licensing.
   Handles checkout, tax/VAT compliance (merchant of record), and license-key
   delivery in one integration rather than stitching a separate processor
   (e.g. Stripe) to a dedicated licensing service.
3. **Code signing** — Windows Authenticode. **Decided (2026-07-09): Standard (OV)
   certificate, ~$100–200/yr (roughly £80–160/yr)**, not EV (~$300–400/yr, roughly
   £240–320/yr). OV is cheaper and faster to obtain; Windows may show a mild
   SmartScreen warning until the cert builds install-volume reputation, which is
   normal for a new product and can be revisited (upgrade to EV) once install
   volume justifies it. Apple notarization ($99/yr, roughly £78/yr) is not
   relevant yet — only needed once/if a macOS build happens (§7 step 6). Required
   to avoid "unknown developer" warnings on install.
   *(GBP figures are rough guidance at ~$1 = £0.79 — vendors bill in USD; your
   actual cost depends on the exchange rate at time of payment.)*
4. **Auto-update** — so buyers receive fixes.

## 6. De-risking spikes (run BEFORE the real build)

Small throwaway tests to validate the approach on a **representative** setup —
since hardware is bring-your-own, these prove the *standard* works, not that every
possible device will:

1. **NFC reader** — detect via PC/SC and read a card UID, on at least one real
   reader. (needs a device)
2. **Card printer** — print a correctly-sized CR80 card from a generated PDF, on at
   least one real printer (ideally test a second, different-brand printer too, to
   confirm the OS-print-queue path generalises). *Highest-risk item.* (needs a device)
3. **Licensing** — key generation, offline validation, online revocation.
   *No hardware — can be done any time.*

**Gate:** no hardware-dependent code is built until it's been exercised against at
least one real device and passes its spike. Hardware-independent software proceeds
in parallel. Once released, hardware compatibility beyond the tested devices is
handled as **best-effort support**, not a pre-launch guarantee — this is the
accepted trade-off of not requiring specific certified hardware (see §4).

## 7. Phased roadmap (effort is indicative, not a promise)

1. Collapse the stack — embed DB, drop Redis, backend as a bundled process.
2. Native launcher + installer — **Windows first**.
3. Licensing + activation (online/offline).
4. Payments + distribution channel.
5. Code signing + auto-update.
6. macOS / Linux builds once Windows is proven.

## 8. Working agreement (important)

- **No promise of a flawless first-time build** — that isn't honest for a project
  this size. What *is* committed: upfront rigor, spikes on risky parts, and testing
  before any release so bugs don't reach customers.
- Distinguish **errors while building** (normal, unavoidable) from **bugs reaching
  customers** (minimized via testing).
- **Lock the plan; hold scope steady per phase.** Mid-phase scope changes are the
  main cause of rework.
- Honest status always; failures surfaced plainly.
- **Build nothing until explicitly approved.**

## 9. Decisions before building (all settled 2026-07-09)

- [x] **Windows-only first**, or all three OSes at once? → **DECIDED (2026-07-09): Windows-only first.** macOS/Linux considered later once Windows is proven (§7 step 6).
- [x] Bundled Postgres everywhere, or SQLite "Lite" tier? → **DECIDED (2026-07-09): Postgres everywhere.** See §3.
- [x] Licensing/payment vendor → **DECIDED (2026-07-09): Lemon Squeezy.** See §5.
- [x] Budget for yearly code-signing certificates → **DECIDED (2026-07-09): Standard (OV), ~$100–200/yr (roughly £80–160/yr).** See §5.
- [x] Which NFC card type will be issued → **DECIDED (2026-07-09): MIFARE Classic**
  (cheapest, most universally supported; only the UID is read, so DESFire's
  on-card encryption isn't needed). Accepted trade-off: MIFARE Classic UIDs can in
  principle be cloned with physical access — a normal, accepted risk for basic
  office access-control. NTAG/DESFire remain available as an upgrade path for
  security-sensitive customers later; no app changes needed to support that.

## 10. Biggest risks

- **Card printer** across OSes and across arbitrary customer-chosen models
  (sizing/bleed/print-queue differences) — mitigated by isolating it to an optional
  module, building to the OS-print-queue standard, and failing clearly and visibly
  when a device doesn't cooperate.
- **Bring-your-own hardware means compatibility can't be pre-proven for every
  device** — accepted trade-off in exchange for no vendor lock-in for customers;
  mitigated by testing representative devices pre-launch and handling anything
  unusual as best-effort support after release, not a guarantee (see §4, §6).
- **Cross-platform hardware testing** needs real devices per OS — mitigated by
  Windows-first.
- **No hardware yet + testing late** — mitigated by testing against at least one
  representative reader/printer before relying on the hardware path, rather than
  shipping it untested.
