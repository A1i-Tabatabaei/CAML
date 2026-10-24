# VPS runbook: bringing up a framework

This is the loop used for every framework in Phases 3–5 (see `STATUS.md`).
It's designed so a multi-day, multi-session effort never loses state.

## Per-framework loop

1. **Open a tracking issue**:
   ```bash
   gh issue create --repo A1i-Tabatabaei/CAML --title "[framework] <Name>" --label framework \
     --body $'- [ ] manifest written\n- [ ] installs cleanly\n- [ ] smoke test passes\n- [ ] doc page written\n- [ ] STATUS.md updated'
   ```
2. **Install**:
   ```bash
   uv run caml install <name>
   ```
   Capture the full log. If it fails, that's expected on a first attempt
   for the harder frameworks (TabPFN, SapientML, GAMA especially) — see
   step 4.
3. **Smoke test** against a tiny task:
   ```bash
   uv run caml run <name> --benchmark test --constraint test
   ```
   `resources/benchmarks/test.yaml` has 3 tiny OpenML tasks (kc2 binary,
   iris multiclass, cholesterol regression) under the `test` constraint (2
   folds, 60s budget). Confirm a plausible non-NaN score, not just "it
   didn't crash."
4. **On failure**: log the full traceback + environment
   (`uv --version`, resolved Python, framework version from
   `.setup/installed`) as an issue comment. Fix, re-run step 2–3.
5. **Once green**: distill the *lasting* lesson into
   `docs/frameworks/<name>.md`'s gotchas section. Issue comments are the
   raw debugging trail; the docs page is the durable knowledge next time
   someone (human or agent) touches this framework.
6. **Update `STATUS.md`**: flip the framework's row to `verified`, fill in
   pinned version / Python / date / issue number. Close the issue. Commit
   `STATUS.md` before moving to the next framework — state must never live
   only in shell history.

## Time-boxing judgment calls

GAMA (and any framework that turns out unexpectedly troublesome) should be
time-boxed rather than absorbing unbounded debugging time. If a framework
doesn't install/run cleanly within the box, mark it `blocked` in
`STATUS.md` with a clear note of what's blocking it, rather than silently
downgrading scope — that's a call the user should see, not one made
unilaterally mid-session.

## Every session should

- **Start** by reading `CLAUDE.md` and `STATUS.md`.
- **End** by committing an updated `STATUS.md` (and any docs pages
  finished), even if the framework being worked isn't fully green yet —
  leave a clear "currently working on" note for whoever picks this up next.
