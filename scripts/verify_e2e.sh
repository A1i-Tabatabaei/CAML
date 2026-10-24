#!/usr/bin/env bash
# VPS-side: installs every framework discovered under frameworks/, then
# runs each one against both the `test` benchmark (the existing 3-task
# smoke test: binary/multiclass/regression) and the `validation`
# benchmark (9 real data-quality/type edge cases -- missing values, stray
# whitespace in category labels, boolean-like target classes, a target
# column not in the last position, duplicate differently-cased labels;
# see resources/benchmarks/validation.yaml) under the `test` runtime
# constraint.
#
# Built entirely from already-documented single-framework commands
# (`caml install --all`, `caml run <name> --benchmark X --constraint Y`
# -- see docs/reference/cli.md) -- this script only adds the loop and
# result-capture around them, no new CAML behavior.
#
# Tolerates individual failures deliberately (no `set -e`) -- the whole
# point of this script is finding out which framework/dataset
# combinations are NOT reliable, so one crash must not stop the rest of
# the audit. Every attempt's outcome and full log are recorded regardless
# of whether it passed.
#
# Resumable: a full run of every framework against the (uncapped-budget)
# validation benchmark takes many hours -- long enough to outlast a
# single SSH session. Pass an existing results directory as $1 to resume
# it: already-recorded framework/benchmark combos (read from that dir's
# summary.tsv) are skipped rather than re-run. Re-running caml install
# --all on resume is safe/cheap -- installer.py already no-ops a
# framework whose pin matches what's installed.
#
# Run as the `caml` user from the CAML repo root, DETACHED from the
# invoking shell so it survives the SSH connection dropping (this bit us
# once already -- a bare `ssh ... "bash scripts/verify_e2e.sh"` dies with
# the connection):
#   setsid nohup bash scripts/verify_e2e.sh [resume_dir] \
#     > /tmp/verify_e2e_launcher.log 2>&1 < /dev/null &
#   disown
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$(pwd)"

RESUME_DIR="${1:-}"
if [[ -n "$RESUME_DIR" && -f "$RESUME_DIR/summary.tsv" ]]; then
  RESULTS_DIR="$RESUME_DIR"
  echo "==> Resuming existing results dir: $RESULTS_DIR"
else
  RESULTS_DIR="$REPO_ROOT/output/e2e_verify_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$RESULTS_DIR/logs"
  printf 'framework\tbenchmark\tstatus\tduration_seconds\tlog_file\n' > "$RESULTS_DIR/summary.tsv"
  echo "==> Fresh results dir: $RESULTS_DIR"
fi
SUMMARY="$RESULTS_DIR/summary.tsv"

# Build the skip-set of already-completed framework/benchmark combos from
# any prior rows (works for both a genuine resume and a fresh dir with an
# empty/header-only summary.tsv -- the loop below is just a no-op
# skip-set in the fresh case). Keyed with "::" rather than a literal tab
# -- an *unquoted* array subscript containing \t silently loses the
# backslash during bash's normal quote removal (only quoted subscripts
# preserve it), so a write of DONE["$fw\t$bench"] and a read of
# ${DONE[$fw\t$bench]} build two DIFFERENT keys and never match. "::"
# can't appear in a framework or benchmark name, so it sidesteps the
# whole class of bug rather than relying on getting the quoting exactly
# right on both sides.
declare -A DONE
while IFS=$'\t' read -r fw bench status _rest; do
  [[ "$fw" == "framework" ]] && continue  # header row
  DONE["${fw}::${bench}"]=1
done < "$SUMMARY"

echo "==> [1/4] caml doctor (pre-install baseline)"
uv run caml doctor 2>&1 | tee "$RESULTS_DIR/logs/doctor_pre.log"

echo "==> [2/4] caml install --all"
uv run caml install --all 2>&1 | tee "$RESULTS_DIR/logs/install_all.log"

echo "==> [3/4] caml status (post-install)"
uv run caml status 2>&1 | tee "$RESULTS_DIR/logs/status_post_install.log"

echo "==> [4/4] caml run <framework> --benchmark {test,validation} --constraint test, for every discovered framework"

FRAMEWORKS=()
for dir in frameworks/*/; do
  name="$(basename "$dir")"
  [[ "$name" == "shared" ]] && continue
  [[ -f "${dir}framework.toml" ]] && FRAMEWORKS+=("$name")
done
echo "    Discovered ${#FRAMEWORKS[@]} frameworks: ${FRAMEWORKS[*]}"

for fw in "${FRAMEWORKS[@]}"; do
  for bench in test validation; do
    if [[ -n "${DONE["${fw}::${bench}"]:-}" ]]; then
      echo "----> $fw / $bench: already recorded, skipping"
      continue
    fi
    log_file="$RESULTS_DIR/logs/${fw}_${bench}.log"
    start_ts=$(date +%s)
    echo "----> $fw / $bench ..."
    if uv run caml run "$fw" --benchmark "$bench" --constraint test > "$log_file" 2>&1; then
      status="PASS"
    else
      status="FAIL"
    fi
    end_ts=$(date +%s)
    duration=$((end_ts - start_ts))
    printf '%s\t%s\t%s\t%s\t%s\n' "$fw" "$bench" "$status" "$duration" "$log_file" >> "$SUMMARY"
    echo "      $fw / $bench: $status (${duration}s) -- log: $log_file"
  done
done

echo "==> caml doctor (post-run)"
uv run caml doctor 2>&1 | tee "$RESULTS_DIR/logs/doctor_post.log"

echo
echo "==> DONE. Summary: $SUMMARY"
column -t -s "$(printf '\t')" "$SUMMARY" || cat "$SUMMARY"

# Pure suggestion, read-only over data this script already collected --
# doesn't run anything or affect this script's exit code. `caml compare`
# reads the SAME output/results.csv this loop just wrote to, paired per
# task (see docs/reference/cli.md) -- a natural follow-up once ≥2
# frameworks passed the same benchmark, not something this reliability
# audit needs to run itself (a different concern: tolerating individual
# framework failures vs. statistically comparing the ones that succeeded).
echo
echo "==> Suggested significance comparisons (>=2 PASS frameworks per benchmark):"
awk -F'\t' '
  NR == 1 { next }
  $3 == "PASS" { fws[$2] = fws[$2] " " $1 }
  END {
    for (bench in fws) {
      n = split(fws[bench], arr, " ")
      if (n >= 2) {
        cmd = "caml compare"
        for (i = 1; i <= n; i++) cmd = cmd " " arr[i]
        print "  " cmd " --benchmark " bench " --constraint test"
      }
    }
  }
' "$SUMMARY"
