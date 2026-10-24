# GPU support (Phase 8)

CAML uses a GPU automatically when it's running on a box that has one, and
falls back to CPU cleanly when it isn't — no per-run flags, no separate
"GPU mode". This page is the operational reference for that behaviour: what's
wired up, how detection works, how to override it, and how to point it at a
different CUDA version.

## TL;DR

- On a **GPU box**, `caml install <fw>` pulls CUDA wheels and `caml run <fw>`
  uses the GPU, for the three frameworks that can benefit.
- On a **CPU box**, everything behaves exactly as before (CPU wheels, CPU run).
- One override knob, honoured at both install and run time:
  `CAML_COMPUTE=auto|cpu|gpu` (default `auto`).
- `caml doctor` prints the detected GPU and the compute mode it would use.

## What's GPU-accelerated (and what deliberately isn't)

Only frameworks whose underlying library has a real GPU code path are wired
up. Forcing the rest onto a GPU would add risk for zero benefit — they're
CPU-bound by design.

| Framework | GPU? | How |
|---|---|---|
| **TabPFN** (local) | ✅ prime beneficiary | `device="cuda"` auto-set; **GPU also lifts the CPU >1000-sample guard** (see below) |
| **AutoGluon** | ✅ | `num_gpus=1` passed to fit → torch-backed NN models (and GPU-capable GBMs) use the GPU; CPU-only models still run on CPU |
| **LightAutoML** | ✅ (see caveat) | `gpu_ids="0"` passed to `TabularUtilizedAutoML` |
| FLAML, MLJAR, TPOT, H2O, NaiveAutoML, FEDOT, GAMA | ❌ by design | CPU-bound libraries — no GPU wheel path declared, untouched on any box |
| **TabPFNClient** (hosted) | ❌ exempt | all compute is server-side (Prior Labs); nothing local to accelerate |

**TabPFN is the headline win.** On CPU, TabPFN-3 refuses datasets larger than
1000 samples by default — a hardware guard, not a robustness limit (the
2026-08-01 `validation` run passed only the 3 ≤1000-row tasks and failed the
other 6 on exactly this guard). On a GPU that guard doesn't apply, so those
tasks run for real with no other change. See `docs/frameworks/tabpfn.md`.

## How it works

Two halves, one knob.

1. **Install-time — which wheel.** `caml install` asks
   `installer.py::gpu_present()` (probes `nvidia-smi -L`, or obeys
   `CAML_COMPUTE`). A framework that declares a `gpu_extra_index_urls` in its
   `framework.toml` gets those CUDA wheels when a GPU is present, and its
   `extra_index_urls` (CPU wheels) otherwise. The CPU-bound roster declares no
   GPU index, so this is a no-op for them regardless of box. The chosen mode is
   recorded in the install marker and shown in `caml status`' COMPUTE column.

2. **Run-time — which device.** Each torch framework's `exec.py` asks
   `frameworks/shared/compute.py::use_gpu()` (this time via
   `torch.cuda.is_available()`, since torch is installed by then) and sets the
   framework's own device kwarg accordingly. Defensive throughout: no torch,
   a broken driver, or a `torch.cuda` that raises all resolve to CPU rather
   than crashing a run.

Both halves read the same `CAML_COMPUTE`, so one setting controls the whole
box consistently.

## Overrides

| Variable | Values | Effect |
|---|---|---|
| `CAML_COMPUTE` | `auto` (default) | detect a usable GPU; use it if present |
| | `cpu` | force CPU wheels + CPU runs even on a GPU box |
| | `gpu` | force CUDA wheels; runs still fall back to CPU (with a warning) if no usable device is found, rather than crashing |
| `CAML_GPU_IDS` | e.g. `0`, `0,1`, `all` | LightAutoML only — which CUDA device(s) to use (default `0`) |

Per-run, per-framework overrides still work through the normal
`framework_params` passthrough (e.g. TabPFN `device`, AutoGluon `num_gpus`),
and win over the auto-detected default.

`CAML_COMPUTE=cpu` is the intended way to honour TabPFN-3's **non-commercial
weight license** on a shared/commercial box, or to run a clean CPU-vs-GPU A/B.

## Matching the CUDA wheel to the driver

The torch frameworks pin a CUDA wheel index in their manifests
(`gpu_extra_index_urls = ["https://download.pytorch.org/whl/cu124"]`). The
`cuXXX` suffix must be **≤ the CUDA version the box's NVIDIA driver supports**
(the "CUDA Version" shown top-right in `nvidia-smi`). If a box has an older or
newer driver, change the suffix in the three manifests (AutoGluon,
LightAutoML, TabPFN) to a matching index PyTorch publishes (`cu121`, `cu124`,
`cu126`, …). It's a one-line change per manifest; nothing else depends on the
value.

Verify after install:

```bash
sudo -iu caml bash -lc 'cd ~/caml-workspace/CAML &&
  frameworks/TabPFN/venv/bin/python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"'
# expect: e.g. "2.x.y+cu124 12.4 True"
```

## Provisioning a GPU box

Same flow as any CAML box (`docs/getting-started/vps-bootstrap.md`), with two
GPU-specific notes:

- **Driver must be present.** A "GPU VPS" image usually ships with the NVIDIA
  driver pre-installed — confirm with `nvidia-smi`. If it's missing, install
  the driver before any GPU work (image/provider-specific; not automated in
  `bootstrap_vps.sh`, which stays driver-agnostic).
- **Non-root login.** The current GPU box logs in as `administrator` and
  escalates with `sudo -i` (connection details in the untracked
  `docs/operations/.gpu-vps-access.local.md`). `bootstrap_vps.sh` still needs
  root — run it as `sudo bash bootstrap_vps.sh`; everything downstream runs as
  the dedicated `caml` user exactly as before.

## Verified on the RTX A4000 box

**Partially verified, 2026-08-02** (recorded retroactively on 2026-10-21 from
that session's transcript; it hadn't been written into the repo at the time):

- Provisioning, `caml doctor` GPU detection, and the install-time wheel choice
  all worked on real hardware: TabPFN resolved **`torch 2.6.0+cu124`**,
  `torch.cuda.is_available() == True`, and the run log showed `Using
  device=cuda` on the NVIDIA RTX A4000.
- The first cold-cache `caml run TabPFN` **crashed with exit 132 (SIGILL)**. It
  was root-caused to the subprocess environment missing `HOME`, and the fix was
  committed later in `0be1a35`. See troubleshooting, "SIGILL (exit 132) on the
  first GPU run". With a warm driver cache, all 6 `test` jobs then completed on
  GPU with real scores.
- **Never re-verified**: the box was deleted mid-verification, so the `HOME` fix
  has not been tested on a cold cache. AutoGluon and LightAutoML were never run
  on GPU, and the GPU re-run of TabPFN's CPU-capped `validation` tasks never
  happened. All of this is tracked in `operations/known-issues.md`.
