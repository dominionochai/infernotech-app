# InfernoTech — Unified Wildfire Response Platform
### Submission: Fund My Crazy by Google — **Community & Living** theme · Built with Gemini

A working merge of three independently-real systems into one wildfire
response platform, spanning detection, confirmation, and financing:

1. **Satellite detection** (this repo) — live NASA FIRMS hotspots anywhere
   on Earth, wind-based spread projection, address-level pre-disaster risk
   scoring, and Gemini-powered plain-language briefs. Falls back to the
   original Attica, Greece (July 2023) case study when no place is searched.
2. **Ground confirmation** — [Ridgeline](https://github.com/ayaan-gupta/ridgeline)
   watches public wildfire lookout cameras (HPWREN/ALERTWildfire) and only
   confirms a detection after 3 consecutive frames score above threshold.
   InfernoTech polls its documented REST API and overlays confirmed
   detections on the map as a distinct, higher-trust marker layer.
3. **Carbon-credit financing** — [Hedera Guardian](https://github.com/hashgraph/guardian)
   tokenizes verified environmental outcomes. When a protected forest area
   has documented avoided deforestation, InfernoTech can submit a real MRV
   (Monitoring, Reporting, Verification) document to a running Guardian
   instance under the **VM0015 "Avoided Unplanned Deforestation"**
   methodology, tying wildfire prevention to actual, ledger-verifiable
   carbon-market financing.

## Why this merge, not just three separate demos

Satellite detection tells you a fire *might* be happening somewhere broad.
Ground cameras *confirm* it's real, fast, for what's in view. Neither of
those, alone, creates an incentive for anyone to prevent the fire in the
first place — that's what tying verified forest protection to actual
carbon-credit issuance does. Three different time horizons of the same
problem (detect → confirm → prevent-and-finance), in one dashboard.

## Architecture

```
                    ┌─────────────────────┐
   NASA FIRMS  ───▶ │                     │
   Open-Meteo  ───▶ │     InfernoTech     │ ───▶ Gemini (briefs, risk notes)
   (this repo) ───▶ │   (Flask, port 5000)│
                    └──────────┬──────────┘
                               │ polls GET /api/detections
                               ▼
                    ┌─────────────────────┐
                    │      Ridgeline       │  (separate repo — clone yourself)
                    │  Next.js + FastAPI   │
                    │  + Postgres          │
                    └─────────────────────┘

   InfernoTech ──POST /external (owner, policyTag, document)──▶ Hedera Guardian
                                                                  (separate platform —
                                                                   run independently)
```

Both Ridgeline and Guardian are real, substantial systems in their own
right — this repo doesn't re-implement or vendor either one. It talks to
each through its own documented public API (`webapp/ridgeline_client.py`,
`webapp/guardian_client.py`), and every integration **degrades gracefully**:
unset the relevant env vars and InfernoTech runs exactly as before with
that layer simply absent. Nothing breaks if Ridgeline or Guardian aren't
running.

## Honesty about scope

This was built and tested in an environment with no live network access for
`pip`/`npm`/Docker — every InfernoTech module (`app.py`, `fire_data.py`,
`weather.py`, `spread.py`, `risk.py`, `guardian_client.py`,
`ridgeline_client.py`) was written and logic-tested against **mocked**
Ridgeline/Guardian/NASA-FIRMS/Gemini responses (see the test patterns used
throughout development — every failure path, every success path, checked).
What's **not** verified from that environment: actually running Ridgeline's
Next.js/Postgres stack, or a live Hedera Guardian instance with VM0015
imported. Those need a real `git clone` of Ridgeline and a real Guardian
deployment on your end — `docker-compose.yml` and the env vars below are
where those get wired in once you have them.

## Quickstart (InfernoTech alone — works standalone)

```bash
cd webapp
pip install -r requirements.txt
python generate_sample_data.py
cp .env.example .env   # add your Gemini + FIRMS keys
python app.py
```

## Adding Ridgeline (ground-camera confirmation)

```bash
git clone https://github.com/ayaan-gupta/ridgeline.git
# follow Ridgeline's own README to configure and run it (it needs its own
# .env — camera stream URLs, optional model weights, Postgres, etc.)
```
Then set in `webapp/.env`:
```
RIDGELINE_API_URL=http://localhost:3100
```
Confirmed detections will start appearing as camera-icon markers on the map,
and the status line will show a live camera-confirmed count.

## Adding Guardian (carbon-credit MRV)

Stand up a Guardian instance with VM0015 imported (see
[PR #3516](https://github.com/hashgraph/guardian/pull/3516) and Guardian's
own setup docs — it's a full platform: guardian-service, worker-service,
MongoDB, IPFS, a Hedera testnet/mainnet account). Register an owner DID
against the policy, then set in `webapp/.env`:
```
GUARDIAN_API_URL=http://localhost:3000/api/v1
GUARDIAN_OWNER_DID=did:hedera:testnet:your-registered-did
GUARDIAN_POLICY_TAG=MRV_VM0015
GUARDIAN_ACCESS_TOKEN=your-token
```
The "Submit Avoided-Deforestation MRV" panel in the UI will then submit real
documents to your policy. **Reconcile the field names in
`build_vm0015_mrv_document()`** (`webapp/guardian_client.py`) against your
actual imported policy schema before relying on this for real credit
issuance — they're a reasonable placeholder shape, not copied from the
schema file directly (that file wasn't reachable to read directly while
building this).

## Running all three together

```bash
docker compose up
```
(after cloning Ridgeline as a sibling `../ridgeline` directory and
uncommenting its service block in `docker-compose.yml` — see the comments
in that file.)

---

## Everything below: the original InfernoTech feature set

- **Works anywhere** — search any place worldwide; live NASA FIRMS hotspots
  via Open-Meteo geocoding (chosen over Nominatim/OSM, which some
  networks/firewalls block).
- **Fire-spread projection** — for the strongest hotspot, pulls live wind
  from Open-Meteo and projects a directional cone showing roughly where a
  fire may head over the next few hours. A transparent heuristic (a
  fraction of wind speed), not a validated fire-behavior model — labeled as
  such everywhere it appears.
- **Address risk check** — 0–100 heuristic wildfire-weather risk score
  (temperature + humidity + wind + nearby active detections) for any
  address, for pre-disaster preparation rather than only post-disaster
  response. Always labeled as a simplified estimate, never an official
  rating.
- **Built with Gemini** — plain-language community recovery briefs and
  risk-check notes, both with offline fallbacks if no `GEMINI_API_KEY` is set.
- **Original Attica, Greece case study** — the source hackathon project
  (STEMist Hacks II, July 2023 wildfires) preserved as the default/fallback
  view, with bundled sample GeoJSON standing in for shapefiles that were
  never committed to the original repo.

Full original technical write-up (FireCLR/SAMGeo methodology, disaster-phase
framing, references) is preserved in `models/` and the project's git history.
