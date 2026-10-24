"""GPU/CPU device resolution shared by the torch-backed frameworks.

Runs *inside* a framework's isolated venv (same context as
``frameworks/shared/utils.py`` — resolved off the subprocess ``PYTHONPATH``,
using that venv's own ``torch``). Only the three frameworks in the roster
with a real GPU code path import this: ``AutoGluon``, ``LightAutoML`` and the
local ``TabPFN``. The CPU-bound frameworks (FLAML, MLJAR, TPOT, H2O,
NaiveAutoML, FEDOT, GAMA) never touch it, and the hosted ``TabPFNClient`` is
exempt entirely (its compute is server-side).

**Policy: GPU by default.** When a CUDA device is actually usable, use it;
otherwise fall back to CPU cleanly and silently. This is the runtime half of
CAML's Phase-8 GPU support; the install-time half (which torch wheel gets
installed) lives in ``src/caml/frameworks/installer.py``. Both honour the
same ``CAML_COMPUTE`` override so a single knob controls the whole box.

``CAML_COMPUTE`` (env var, forwarded across the subprocess boundary via each
torch framework's ``__init__.py`` ``retained_env_vars``):

- unset / ``auto`` — detect a usable CUDA GPU and use it if present (default).
- ``cpu``          — force CPU even on a GPU box (e.g. to honour TabPFN-3's
                     non-commercial weight license on a shared box, or to A/B
                     a timing run).
- ``gpu``          — insist on GPU; still falls back to CPU with a loud
                     warning if no CUDA device is actually usable, rather than
                     crashing a benchmark run.
"""

import logging
import os

log = logging.getLogger(__name__)

_VALID_PREFERENCES = {"auto", "cpu", "gpu"}


def compute_preference() -> str:
    """Return the normalized ``CAML_COMPUTE`` preference (``auto`` by default)."""
    pref = (os.environ.get("CAML_COMPUTE") or "auto").strip().lower()
    if pref not in _VALID_PREFERENCES:
        log.warning(
            "Unrecognized CAML_COMPUTE=%r; expected one of %s. Falling back to 'auto'.",
            pref,
            sorted(_VALID_PREFERENCES),
        )
        return "auto"
    return pref


def cuda_available() -> bool:
    """True iff this venv's torch can actually see a usable CUDA device.

    Defensive on every axis: torch may not be importable at all (this module
    is only ever imported by torch frameworks, but a broken install shouldn't
    take a run down), and ``torch.cuda.is_available()`` itself can raise on a
    driver/runtime mismatch rather than returning False. Any failure means
    "no usable GPU" — CPU is always a safe answer.
    """
    try:
        import torch
    except Exception:  # noqa: BLE001 - torch missing/broken => no GPU
        return False
    try:
        return bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
    except Exception:  # noqa: BLE001 - driver/runtime mismatch => no GPU
        log.warning("torch.cuda.is_available() raised; treating as CPU-only.", exc_info=True)
        return False


def use_gpu() -> bool:
    """Whether this run should use the GPU, honouring ``CAML_COMPUTE``."""
    pref = compute_preference()
    if pref == "cpu":
        return False
    if pref == "gpu":
        if cuda_available():
            return True
        log.warning(
            "CAML_COMPUTE=gpu was requested but no usable CUDA device was found; "
            "falling back to CPU for this run."
        )
        return False
    # auto
    return cuda_available()


def torch_device() -> str:
    """``"cuda"`` or ``"cpu"`` — for frameworks that take a device string (TabPFN)."""
    return "cuda" if use_gpu() else "cpu"


def describe() -> str:
    """One-line human-readable summary for logs (e.g. the model banner)."""
    pref = compute_preference()
    if use_gpu():
        detail = ""
        try:
            import torch

            detail = f" ({torch.cuda.get_device_name(0)})"
        except Exception:  # noqa: BLE001 - name lookup is best-effort
            pass
        return f"GPU/cuda{detail} [CAML_COMPUTE={pref}]"
    return f"CPU [CAML_COMPUTE={pref}]"
