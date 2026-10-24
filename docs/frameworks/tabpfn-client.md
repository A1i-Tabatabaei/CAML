# TabPFNClient — hosted API (the GPU-less sibling of `TabPFN`)

| | |
|---|---|
| Framework name | `TabPFNClient` |
| PyPI package | [`tabpfn-client`](https://pypi.org/project/tabpfn-client/) |
| GitHub | [PriorLabs/tabpfn-client](https://github.com/PriorLabs/tabpfn-client) |
| License | Apache-2.0 (client library — see "Data leaves the machine" below) |
| Current pin | `0.3.3` |
| Python range | `>=3.10,<3.14` |
| System deps | none (all compute is server-side) |
| Status | see `STATUS.md` |

## What this is, and when to use it

`TabPFNClient` runs the TabPFN foundation model via Prior Labs' **hosted
API**: `fit()`/`predict()`/`predict_proba()` are thin REST/SSE calls, and all
computation happens on Prior Labs' servers. It exists as the **fallback for
boxes with no local compute** — its sibling framework **`TabPFN`**
(`docs/frameworks/tabpfn.md`) runs the *same* model 100% on-box via the OSS
`tabpfn` package and is the default choice. The tradeoff is right in the name:
convenience and zero local dependencies here, at the cost of sending data off
the machine. Prefer `TabPFN` (local) unless the box genuinely can't run it.

> History: this was the *original* `TabPFN` framework. When the local `tabpfn`
> package was first attempted (2026-07-26) it looked blocked on a Prior Labs
> license/weight-download gate, so the roster pivoted to this hosted client
> (2026-07-30). That gate turned out to be a one-time license acceptance the
> user has since completed, so the local package now works too — and this
> entry was renamed `TabPFN` → `TabPFNClient` (2026-07-31) to make room for the
> local `TabPFN` as the primary. See `docs/frameworks/tabpfn.md` for the local
> integration and the full story.

## Integration notes

- `fit()`/`predict()`/`predict_proba()` are thin REST/SSE calls to Prior
  Labs' API; there's no local model. No `device`/`n_preprocessing_jobs`
  constructor kwargs (those are specific to the local package's in-process
  inference and don't exist on `tabpfn-client`'s estimators — the local
  `TabPFN` framework does use `device`).
- No torch dependency, no CPU-wheel `extra_index_urls`, no
  `post_install_script` — none of that applies to the client (all of it *does*
  apply to the local `TabPFN`).
- Auth is a `TABPFN_TOKEN` environment variable, read by `tabpfn-client`
  itself, on **every** call (the local package needs it only once, for the
  weight download). See `docs/operations/tabpfn-access.md` for where the real
  value lives (never committed) — `exec.py` fails fast with a clear
  `FrameworkError` if it's unset or still the placeholder. The *same* token
  authenticates both frameworks.
- Data flow follows CAML's array-based convention (`dataset.train.X`/`.y`,
  same as FLAML/MLJAR) — `tabpfn-client`'s estimators are sklearn-compatible.

## Gotchas

- **Data leaves the machine.** Every other framework in this roster (including
  the local `TabPFN`) runs 100% locally; `tabpfn-client` sends
  `X_train`/`y_train`/`X_test` to Prior Labs' servers and gets predictions back
  over HTTPS ("your data will be sent to our servers for processing" — their
  own docs). Fine for a benchmark harness comparing frameworks against public
  OpenML datasets, but a materially different trust boundary than the rest of
  the roster — worth remembering before ever pointing this framework at
  anything sensitive. **This is the single reason to prefer the local
  `TabPFN`.**
- **Rate limits / usage quotas apply server-side** (tracked via
  `X-RateLimit-*` response headers, daily reset at 00:00 UTC; usage cost
  scales with dataset rows × columns). Irrelevant at the tiny `test`
  benchmark's scale but worth knowing before ever pointing this framework
  at a large/real benchmark suite. Per-model row/column/cell/class limits
  are also enforced server-side; the client validates and raises
  `ValueError` before sending if exceeded. (The local `TabPFN` has no such
  quotas — only local hardware limits.)
- **No GPU/CPU relevance for the client machine at all.** When the planned
  Phase 8 GPU auto-detection work happens, **`TabPFNClient`** should be
  explicitly skipped rather than wired up — there's no local inference to
  accelerate (see `CLAUDE.md`'s "Compute target" section). The local `TabPFN`
  is the opposite: a prime GPU-acceleration candidate.
- Still architecturally different from every other framework here: no
  hyperparameter search, so `config.max_runtime_seconds` isn't spent by
  default. `tabpfn-client` does expose an opt-in "thinking mode"
  (`thinking_mode=True` + `thinking_timeout_s`, capped at 2400s server-side)
  for spending extra fit-time compute on higher precision — not enabled here,
  but flows through automatically via the standard `framework_params`
  passthrough if a future benchmark config wants it.

## Last verified

**2026-07-30, real VPS** — `caml run TabPFN --benchmark test --constraint test`
(under its old name) completed cleanly on the first attempt: kc2 AUC
0.859/0.910, iris acc 1.000/1.000 (logloss 0.021/0.010), cholesterol RMSE
43.42/54.07, ~90s for all 6 jobs (mostly network round-trips).

**2026-07-31** — after the `TabPFN` → `TabPFNClient` rename,
`caml install TabPFNClient` reinstalled cleanly in 4.7s (`tabpfn-client==0.3.3`),
confirming the rename didn't disturb the integration. Behavior is unchanged
from 2026-07-30 (same package, same code, only the framework name differs).
