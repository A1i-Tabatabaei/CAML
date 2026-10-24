# TabPFN — local OSS package (`tabpfn`)

| | |
|---|---|
| Framework name | `TabPFN` (primary/default; the hosted sibling is `TabPFNClient`) |
| PyPI package | [`tabpfn`](https://pypi.org/project/tabpfn/) |
| GitHub | [PriorLabs/TabPFN](https://github.com/PriorLabs/TabPFN) |
| License | Apache-2.0-based code; **model weights are non-commercial** — see gotchas |
| Current pin | `8.1.0` |
| Python range | `>=3.10,<3.13` (capped for torch-wheel safety; upstream claims 3.14) |
| System deps | none (pulls the CPU torch wheel) |
| Status | **Verified 2026-07-31** — see the bring-up log below and `STATUS.md` |

**Status: VERIFIED on the real VPS, 2026-07-31.** Runs TabPFN's *actual model
on-box* via the open-source `tabpfn` package — data never leaves the machine —
as opposed to the hosted `tabpfn-client` API (`docs/frameworks/tabpfn-client.md`).
The one-time, license-gated weight download needs a Prior Labs license
acceptance (a user action, now done — see the bring-up log). A living document —
edit it as bugs are found and decisions are made, same discipline as
`docs/frameworks/sapientml.md`.

## Why this exists — correcting a stale "blocked" conclusion

The project's history (`CLAUDE.md`, `STATUS.md`) records the local `tabpfn`
package as **blocked** on a licensing gate (2026-07-29), which is why the
roster pivoted to the hosted `tabpfn-client` on 2026-07-30. That conclusion
was *correct at the time* but is **now stale**:

- The block was: `tabpfn` needs a one-time Prior Labs account + license
  acceptance before it will serve model weights, even non-interactively —
  and at that point no account existed, and creating one on the user's
  behalf wasn't ours to do.
- **That precondition is now satisfied.** For the `tabpfn-client` pivot the
  user registered at Prior Labs, accepted the license, and created an API
  key (`TABPFN_TOKEN`). The *same* token + license acceptance is exactly
  what the local package needs for its headless weight download (both are
  Prior Labs' one auth system, keyed off `ux.priorlabs.ai` and the
  `TABPFN_TOKEN` env var). So the original blocker is gone.

**Verdict: running TabPFN fully locally is feasible.** One caveat to
confirm empirically on the VPS (below): that the user's existing
`TABPFN_TOKEN` authenticates the local package's weight download, not just
the API client. High confidence from the docs; the token either works or it
doesn't, and it's a one-line test.

## The material difference vs. `tabpfn-client`

This is the whole point of the exercise:

| | local `tabpfn` | hosted `tabpfn-client` |
|---|---|---|
| Where inference runs | **on the box** (CPU or GPU) | Prior Labs' servers |
| Does data leave the machine? | **No** — after a one-time weight download, `fit()`/`predict()` are 100% local | **Yes** — every `fit()`/`predict()` ships X/y to Prior Labs over HTTPS |
| Network needed at run time | No (once weights cached) | Yes, every call |
| Rate limits / usage quotas | None | Server-side, daily reset |
| Auth | `TABPFN_TOKEN` for the one-time weight download only | `TABPFN_TOKEN` on every call |
| Best for | anyone wanting local/private inference; GPU users | users with no local GPU/compute who accept the data-egress tradeoff |

So the two are kept as **complementary** roster entries, per the user's
direction ("keep the API version running on outside servers as well for
those who don't have access to GPU").

## Official docs — distilled (verified live 2026-07-31)

Sources: `github.com/PriorLabs/TabPFN` README, `docs.priorlabs.ai/quickstart`,
`libraries.io/pypi/tabpfn`.

### Install & Python

- `pip install tabpfn` — **installs a compatible PyTorch build automatically.**
- Supported Python: **3.10–3.14** (README states "Python 3.10+").
- Latest version: **`tabpfn==8.1.0`** (per libraries.io; confirm as latest
  at install time on the VPS, per the exact-pin-and-bump policy). Note the
  package version (8.x) is unrelated to the *model generation* name
  ("TabPFN-3", the current default checkpoint).

### GPU vs CPU — **CPU works**

- "⚡ GPU Recommended: For optimal performance, use a GPU (even older ones
  with ~8GB VRAM work well; 16GB needed for some large datasets)."
- **"On CPU, only moderate datasets are feasible (the default TabPFN-3
  allows up to 5000 samples; older versions up to 1000)."**
- Device is chosen via the constructor `device=` kwarg (`"cuda"` /
  `"cpu"`). This is a **real difference from `tabpfn-client`**, whose
  estimators have no `device` kwarg at all (all compute is server-side) — so
  the local `exec.py` sets it. **Phase 8 (2026-08-02): `exec.py` now
  auto-detects** via `frameworks/shared/compute.py` — `"cuda"` when a usable
  GPU is present, `"cpu"` otherwise, overridable with `CAML_COMPUTE`. On a GPU
  box this both speeds up inference and lifts the CPU sample cap below.

### Model weights, license acceptance & headless auth

- Weights auto-download from HuggingFace on first use
  (checkpoint `Prior-Labs/tabpfn_3`).
- **On first use it normally opens a browser to log in via Prior Labs and
  accept the license.** On a headless VPS that can't happen — but the docs
  give the exact escape hatch:
  > "For headless / CI environments where a browser is not available, visit
  > https://ux.priorlabs.ai, go to the License tab to accept the license,
  > and then set the `TABPFN_TOKEN` environment variable with a token
  > obtained from your account."
  > "Your authentication token is cached locally so you only need to do
  > this once."
- **Offline / pre-download options** (useful for reproducible VPS installs):
  - `python scripts/download_all_models.py` (ships in the repo) pre-caches
    all model checkpoints.
  - `TabPFNClassifier(model_path="/path/to/model.ckpt")` loads a local
    checkpoint directly.
  - Cache dir on Linux: `~/.cache/tabpfn/`; overridable via
    `TABPFN_MODEL_CACHE_DIR`.

### License flags — **must get a legal read before non-internal use**

- **Code**: "Prior Labs License (Apache 2.0 with additional attribution
  requirement)."
- **Weights (TabPFN-3)**: **non-commercial license.** This is a stronger
  constraint than the Apache-2.0 client library and applies to the actual
  model artifact we'd run locally. For CAML's current internal-benchmarking
  use against public OpenML datasets this is very likely fine. CAML itself
  is Apache-2.0 since 2026-10-24, and installs the weights at run time
  rather than redistributing them, but **anyone using local TabPFN results
  commercially must check Prior Labs' license**. Surface this to the user;
  don't assume it's fine (the agent skill asks). (This is a different consideration than `tabpfn-client`, where
  you're using Prior Labs' hosted service under their ToS rather than
  redistributing/running the weight artifact yourself.)

### Dataset limits (local, TabPFN-3 default)

- Up to **1,000,000 × 200**, **100,000 × 2,000**, or **1,000 × 20,000**
  (rows × features) on adequate hardware.
- **On CPU: ~5,000 samples max.** Trivially fine for the `test` benchmark
  (kc2/iris/cholesterol are all tiny), but a real constraint for a large
  benchmark suite on a CPU box — document loudly.

### Minimal API (sklearn-compatible)

```python
from tabpfn import TabPFNClassifier, TabPFNRegressor

clf = TabPFNClassifier(device="cpu")   # device kwarg exists (unlike the client)
clf.fit(X_train, y_train)
proba = clf.predict_proba(X_test)
preds = clf.predict(X_test)

reg = TabPFNRegressor(device="cpu")
reg.fit(X_train, y_train)
preds = reg.predict(X_test)
```

## CAML integration design

The local `exec.py` is close to the hosted-client one
(`frameworks/TabPFNClient/exec.py`) — same sklearn-shaped fit/predict/predict_proba,
same `result()` contract, same array-based data flow — with these deltas:

1. **Package**: `tabpfn==8.1.0`, not `tabpfn-client`. Real torch dependency.
2. **Torch wheel index (GPU-aware since Phase 8)**: the manifest declares both
   `extra_index_urls = [".../whl/cpu"]` and
   `gpu_extra_index_urls = [".../whl/cu124"]`; the installer picks CUDA wheels
   on a GPU box and CPU wheels otherwise (same GPU-by-default mechanism as
   AutoGluon and LightAutoML — see `docs/operations/gpu.md`). (This is the
   reason `tabpfn-client` needed *no* torch handling — it has no torch. The
   local package brings it back.)
3. **`device` kwarg (auto-detected since Phase 8)**: `exec.py` resolves
   `device` to `"cuda"`/`"cpu"` via `frameworks/shared/compute.py`
   (`CAML_COMPUTE` overrides). Not present on the client's estimators.
4. **`TABPFN_TOKEN` passthrough**: still needed, but now only for the
   *weight download*, not every call. Same `retained_env_vars` addition in
   `__init__.py` as the client integration. Also pass through
   `TABPFN_MODEL_CACHE_DIR` if we standardize a cache location.
5. **`max_runtime_seconds`**: unused by default (in-context inference, one
   forward pass, not a hyperparameter search) — same as the client.
6. **GPU exemption reversed (wired up in Phase 8)**: unlike the client (exempt
   from GPU detection because compute is server-side), the *local* package is
   the prime GPU beneficiary in the roster and now uses a GPU automatically
   when one is present — see `docs/operations/gpu.md`.

## VPS bring-up log (2026-07-31)

Installed and diagnosed on the real VPS (Ubuntu 24.04, 4 vCPU/7.8GB/CPU-only).
What was confirmed, and the one thing that wasn't:

- **[x] Install is clean.** `caml install TabPFN` resolved to Python 3.12 and
  pulled **`torch==2.13.0+cpu`** (the `extra_index_urls` CPU-wheel fix works —
  no CUDA download) plus `tabpfn==8.1.0` and 35 deps, all wheels, in seconds.
  No tantivy-style wheel gap at 3.12.
- **[x] The token is valid.** The local package reads `TABPFN_TOKEN` from the
  environment (`tabpfn/browser_auth.py::get_cached_token`, priority: env var →
  `~/.cache/tabpfn/auth_token` → `~/.tabpfn/token`), and it crosses the
  subprocess boundary fine (the `retained_env_vars` addition works).
  `verify_token()` against `https://api.priorlabs.ai/protected/` returns
  **True** — same token the `TabPFNClient` framework uses, confirmed to
  authenticate the local package too. (Token format: a `tabpfn_s…` API key,
  53 chars.)
- **[x] The weight repo is NOT HuggingFace-gated.** `Prior-Labs/tabpfn_3`
  (the default TabPFN-3 checkpoint) reports `gated: False` via the HF API, and
  all classifier/regressor `.ckpt` files are present — so **no `HF_TOKEN` /
  huggingface `accept terms` step is required** for this checkpoint (unlike the
  older `Prior-Labs/tabpfn-v2-classifier`, which *is* HF-gated). Good.
- **[x] RESOLVED — was blocked on a one-time user action: the TabPFN-3 license
  acceptance.** Initially `check_license_accepted(token, api_url,
  "tabpfn-3-license-v1.0")` returned **False**: the license the user had
  accepted for `tabpfn-client` did **not** cover the `tabpfn-3-license-v1.0`
  model checkpoint the local package downloads.
  `tabpfn/browser_auth.py::ensure_license_accepted` therefore found the license
  unaccepted (the token itself was valid) and fell through to an interactive
  browser/paste login — which can't run on a headless box, so `caml run TabPFN`
  failed with `TabPFNLicenseError: … no interactive terminal is available`.
  **Fix (done):** the user accepted the TabPFN-3 (and 2.6, 2.5) licenses at
  <https://ux.priorlabs.ai> (Licenses tab). No code change, no new token —
  acceptance is checked live server-side, so the very next run worked. This is
  the one genuinely user-only step in the whole integration; a coding agent
  can't and shouldn't accept a license. (`TABPFN_NO_BROWSER=1` can force the
  token-only path for a cleaner error if the license is ever un-accepted again,
  but it is not a substitute for acceptance.)

## Last verified

**2026-07-31, real VPS (Ubuntu 24.04, 4 vCPU/7.8GB RAM, CPU-only)** — after
the license acceptance, `caml run TabPFN --benchmark test --constraint test`
completed cleanly: all 6 jobs (kc2/iris/cholesterol × 2 folds) produced real,
plausible scores, in line with the `TabPFNClient` numbers (same model) and
every other verified framework:

- kc2: AUC **0.855 / 0.910** (acc 0.774/0.868, logloss 0.370/0.282)
- iris: acc **1.000 / 1.000** (logloss 0.025/0.008)
- cholesterol: RMSE **43.69 / 54.08** (r2 0.015/−0.014)

Total wall-clock **1m52s including the one-time weight download** (the
regressor + classifier checkpoints, cached to `~/.cache/tabpfn/`); per-job fit
1–8s, predict 2–5s on CPU. `device="cpu"` worked, `predict_proba` returned the
right shape, labels round-tripped — no `exec.py`-level surprises (contrast
SapientML/TPOT, which needed post-run fixes).

**Benign note:** the HF download logs `Warning: You are sending
unauthenticated requests to the HF Hub. Please set a HF_TOKEN…`. This is just
a rate-limit notice, not an error — the download succeeded. For large-scale or
repeated cold installs, setting `HF_TOKEN` avoids throttling, but it is not
required for correctness. Once weights are cached, no network is used at all.

## `validation` benchmark findings (2026-08-01)

Ran the local `TabPFN` through the messy-data `validation` suite (9 tasks,
`--constraint test`, one fold) — the robustness follow-up the E2E audit
(`docs/operations/e2e-verification.md`) had only done for the hosted client.
Run per-task (via `--task`, so one failure doesn't abort the rest):

| task | rows (approx) | outcome |
|---|---|---|
| dresses-sales | ~500 | **PASS** (binary) |
| eucalyptus | ~736 | **PASS** (multiclass) |
| micro-mass | ~571 | **PASS** (multiclass) |
| bioresponse | ~3.7k | FAIL — CPU >1000-sample guard |
| internet-advertisements | ~3.3k | FAIL — CPU >1000-sample guard |
| kc1 | ~2.1k | FAIL — CPU >1000-sample guard |
| APSFailure | ~76k | FAIL — CPU >1000-sample guard |
| diabetes130US | ~102k | FAIL — CPU >1000-sample guard |
| census-income | ~299k | FAIL — CPU >1000-sample guard |

**Headline: 3/9 pass — and all 6 failures are the identical guard, not a
messy-data problem.** TabPFN-3 refuses to run on CPU with more than 1000
samples by default:

> `Running on CPU with more than 1000 samples is not allowed by default due to
> slow performance. To override this behavior, set the environment variable
> TABPFN_ALLOW_CPU_LARGE_DATASET=1 or set ignore_pretraining_limits=True.
> Alternatively, consider using a GPU or the tabpfn-client API.`

So the failures are a **hardware/performance guard, not a robustness gap**: on
the three datasets small enough to run, the local model handled the messy data
cleanly (real, non-NaN scores), matching the hosted client's messy-data
robustness (the client cleared all 9 in the audit, since its compute is
server-side and has no such limit). **This is the crucial operational
difference between the two TabPFN variants** — on a CPU box the local `TabPFN`
is effectively capped at ~1000 samples unless the guard is lifted.

**Overriding the guard (a deliberate choice, deliberately NOT on by default):**
the guard exists because CPU inference slows sharply as rows grow. To run
larger datasets on CPU anyway, either

- pass `ignore_pretraining_limits=True` via the benchmark's `framework_params`
  (it flows straight through `exec.py`'s `**training_params`), or
- set `TABPFN_ALLOW_CPU_LARGE_DATASET=1` in the environment,

accepting materially slower runs (and real memory pressure on very large
datasets — census-income is ~300k rows). The clean answer for large data is a
**GPU** or the hosted **`TabPFNClient`** variant. Left at the safe default on
CPU — this is a user/benchmark-config decision, not one to force on
unilaterally.

**Phase 8 (2026-08-02): on a GPU box this resolves itself automatically.**
`exec.py` now auto-detects the GPU (`frameworks/shared/compute.py`) and runs
`device="cuda"`, which lifts this 1000-sample guard outright — so the 6 tasks
that fail here on CPU are expected to pass on the RTX A4000 box with no config
change. Re-running this suite on GPU (and recording the now-passing 6) is part
of the pending on-box Phase 8 verification — see `docs/operations/gpu.md`.

## Naming / roster structure — DECIDED (2026-07-31)

The user chose **Option A**: `TabPFN` = the local OSS package (primary), and
the existing hosted entry renamed to `TabPFNClient`. Implemented:

- `frameworks/TabPFN/` = the local OSS package (`tabpfn==8.1.0`), this doc.
- `frameworks/TabPFNClient/` = the hosted API (`tabpfn-client==0.3.3`),
  documented in `docs/frameworks/tabpfn-client.md` (was `tabpfn.md`).

Remaining doc/config finalization (README, STATUS, mkdocs nav, NOTICE,
CLAUDE, CLI refs, tests) is deferred until the smoke test passes, so nothing
gets stamped "verified" before the model has actually run.

## Sources

- <https://github.com/PriorLabs/TabPFN> (README)
- <https://docs.priorlabs.ai/quickstart>
- <https://github.com/PriorLabs/TabPFN/issues/174> (offline mode)
- <https://libraries.io/pypi/tabpfn> (version 8.1.0)
