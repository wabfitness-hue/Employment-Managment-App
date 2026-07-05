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
| Database | Postgres container | Bundled Postgres (or SQLite for a "Lite" tier) |
| Redis | Container | Replaced with in-process equivalents |
| Launch | Terminal | Native launcher (**Tauri** — small downloads) |
| Hardware bridge | Manual host process | Bundled, optional, auto-detected |

*Note: the ORM already runs on SQLite (the test suite proves it), so the database
layer is most of the way there. Migrations currently use Postgres-specific types
(JSONB/UUID) and would need attention for a SQLite tier.*

## 4. Hardware — optional and plug-and-play

- The app **runs fully without any hardware.** The NFC reader and card printer are
  **optional add-ons** that light up when a device is connected.
- The app **uses whatever device Windows already has installed** (plug it in → app
  detects it). Driver installation is a standard OS step handled by the customer.
- Hardware is **never required to run and never blocks a release.** The riskiest
  part (the card printer) is isolated to an optional module.
- The bridge already speaks the standard protocols: **PC/SC** (pyscard) for NFC and
  **OS print queue / ZPL** for printers.

### Recommended known-compatible hardware
- **NFC reader:** ACS ACR122U (top pick) · alternatives: HID Omnikey 5427, Identiv uTrust 3700 F. All PC/SC, 13.56 MHz.
- **Card printer:** Zebra ZC300 (top pick — code has a Zebra/ZPL path) · alternatives: Evolis Primacy 2, Magicard 300 · Evolis Badgy200 as a cheap starter.
- **Consumables (ongoing):** color ribbon (~$100–200), blank CR80 PVC cards (~$30–60 / 500).
- *Prices are rough 2026 ballparks — verify before buying.*

## 5. Paid-product layers (separate from packaging)

1. **Licensing / activation** — signed keys, **offline** validation + **online**
   seat/revocation checks (e.g. Lemon Squeezy or Keygen).
2. **Payments / distribution** — Lemon Squeezy / Paddle (handle checkout, tax,
   license delivery) or own site + Stripe.
3. **Code signing** — Windows Authenticode (~$100–400/yr) + Apple notarization
   ($99/yr). Required to avoid "unknown developer" warnings.
4. **Auto-update** — so buyers receive fixes.

## 6. De-risking spikes (run BEFORE the real build)

Small throwaway tests that prove the risky parts work on the real setup:

1. **NFC reader** — detect via PC/SC and read a card UID. (needs the device)
2. **Card printer** — print a correctly-sized CR80 card from a generated PDF.
   *Highest-risk item.* (needs the device)
3. **Licensing** — key generation, offline validation, online revocation.
   *No hardware — can be done any time.*

**Gate:** no hardware-dependent code is built until a real device is in hand and
passes its spike. Hardware-independent software proceeds in parallel.

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

## 9. Open decisions before building

- [ ] Windows-only first, or all three OSes at once? (recommend Windows-first)
- [ ] Bundled Postgres everywhere, or SQLite "Lite" tier + Postgres for bigger installs?
- [ ] Licensing/payment vendor (recommend starting with Lemon Squeezy)
- [ ] Budget for yearly code-signing certificates
- [ ] Which NFC card type will be issued (MIFARE / DESFire / NTAG) — UID read works with all

## 10. Biggest risks

- **Card printer** across OSes (sizing/bleed/print-queue differences) — mitigated by
  isolating it to an optional module and buying known-good hardware.
- **Cross-platform hardware testing** needs real devices per OS — mitigated by
  Windows-first.
- **No hardware yet + testing late** — mitigated by choosing hardware from the
  known-compatible shortlist rather than testing arbitrary devices.
