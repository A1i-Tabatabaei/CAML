#!/usr/bin/env bash
# The agent flow end to end, over real SSH, with the exact command shapes
# the operator profiles (skills/caml-benchmark/references/operator-*.md)
# give an agent: `ssh HOST camlctl ...` and `scp`. Nothing here needs
# quoting tricks, which is the point.
#
#   tests/e2e/agent_flow.sh HOST
#
# CI's server-e2e job runs it against the runner itself (sshd on 127.0.0.1,
# root, key login, alias caml-vps), so every push proves the server side on
# Ubuntu 24.04. On a real VPS it takes about 15 minutes and leaves CAML,
# FLAML, a dataset called e2e and jobs named e2e-* behind. Use a disposable
# server, never one with a sweep running.
#
# Source of the CAML code on the server:
#   CAML_E2E_SOURCE=archive (default)  this checkout's HEAD, pushed with scp
#   CAML_E2E_SOURCE=github             the documented clone from GitHub
set -euo pipefail

HOST="${1:?usage: tests/e2e/agent_flow.sh HOST}"
SOURCE="${CAML_E2E_SOURCE:-archive}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/caml-e2e.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
STAMP="$(date -u +%Y%m%d%H%M%S)"

step() { printf '\n==> %s (%s)\n' "$*" "$(date -u +%H:%M:%S)"; }
fail() { echo "E2E FAILED: $*" >&2; exit 1; }
expect() {  # expect LABEL PATTERN TEXT: TEXT must contain a line matching PATTERN (ERE)
  grep -qE -- "$2" <<< "$3" || { printf '%s\n' "$3" >&2; fail "$1: no line matches /$2/"; }
}
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }
wait_job() {  # wait_job NAME MAX_SECONDS: poll with camlctl wait until the job ends
  local name="$1" deadline=$((SECONDS + $2)) out rc
  while true; do
    rc=0; out="$(remote camlctl wait "$name" 240)" || rc=$?
    printf '%s\n' "$out" | tail -n 4
    case "$rc" in
      0) return 0 ;;
      124) (( SECONDS < deadline )) || fail "job $name still running after $2s" ;;
      *) printf '%s\n' "$out" >&2; remote camlctl logs "$name" 200 >&2 || true; fail "job $name failed (exit $rc)" ;;
    esac
  done
}

step "SSH works without prompts"
expect "ssh" '^ok$' "$(remote echo ok)"

step "Seed a CAML checkout on the server ($SOURCE)"
remote "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
SETUP_ARGS=()
if [[ "$SOURCE" == "github" ]]; then
  remote "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
else
  # shellcheck source=scripts/lib_package.sh
  source "$REPO_ROOT/scripts/lib_package.sh"
  (cd "$REPO_ROOT" && caml_package_archive "$WORK/caml-src.tar.gz" 0)
  scp -q "$WORK/caml-src.tar.gz" "$HOST:caml-e2e-src.tar.gz"
  remote "rm -rf /opt/caml-src && mkdir -p /opt/caml-src && tar -xzf caml-e2e-src.tar.gz -C /opt/caml-src --strip-components=1"
  REMOTE_HOME="$(remote pwd)"
  SETUP_ARGS=(--src "$REMOTE_HOME/caml-e2e-src.tar.gz")
fi

step "Server facts before setup"
remote bash /opt/caml-src/scripts/camlctl info | tee "$WORK/info0.txt"
expect "info" '^checks: ' "$(cat "$WORK/info0.txt")"

step "Setup, detached"
out="$(remote bash /opt/caml-src/scripts/camlctl setup --detach ${SETUP_ARGS[@]+"${SETUP_ARGS[@]}"})"
printf '%s\n' "$out"
expect "setup --detach" '^started job setup' "$out"
wait_job setup 1800
out="$(remote camlctl version)"; printf '%s\n' "$out"
expect "version" '^caml [0-9]+\.[0-9]+\.[0-9]+' "$out"
expect "info after setup" '^caml_user: present$' "$(remote camlctl info --offline)"

step "Check-in 2, keys: a filled-in file (Notepad style), imported unread"
echo "caml's login files: $(remote "ls -a /home/caml" | grep -E '^\.(profile|bash_profile|bash_login|bashrc)$' | tr '\n' ' ')"
out="$(remote camlctl secrets --check)"; printf '%s\n' "$out"
expect "no key yet" '^TABPFN_TOKEN: (missing|set)' "$out"
remote camlctl secrets --template \
  | awk '{ sub(/^TABPFN_TOKEN=$/, "TABPFN_TOKEN=e2e-file-token"); printf "%s\r\n", $0 }' > "$WORK/caml-secrets.env"
scp -q "$WORK/caml-secrets.env" "$HOST:caml-secrets.env"
out="$(remote camlctl secrets --import caml-secrets.env)"; printf '%s\n' "$out"
expect "imported" '^TABPFN_TOKEN: imported \(14 characters\)$' "$out"
expect "uploaded copy deleted" '^deleted: ' "$out"
expect "set" '^TABPFN_TOKEN: set' "$out"
grep -q "e2e-file-token" <<< "$out" && fail "secrets --import printed the key"
[[ -z "$(remote "ls caml-secrets.env 2>/dev/null || true")" ]] || fail "the uploaded keys file survived the import"
expect "1.1.0 check" '^token-set$' "$(remote camlctl tabpfn-token --check)"

step "Check-in 2, keys: typed at the hidden prompt (ssh -t through sudo)"
out="$(printf 'e2e-typed-token\n\n' | ssh -tt -o BatchMode=yes "$HOST" camlctl secrets 2>&1 | tr -d '\r')"
printf '%s\n' "$out" | grep -v 'e2e-typed-token' || true
expect "received" 'received \(15 characters\)' "$out"
expect "set after typing" '^TABPFN_TOKEN: set' "$out"
printf '%s\n' '[ "${TABPFN_TOKEN:-}" = e2e-typed-token ] && echo key-matches || echo key-differs' > "$WORK/check_key.sh"
scp -q "$WORK/check_key.sh" "$HOST:check_key.sh"
expect "caml's login shell sees the typed key" '^key-matches$' "$(remote camlctl script check_key.sh)"
out="$(remote camlctl secrets --remove --all)"; printf '%s\n' "$out"
expect "removed" '^TABPFN_TOKEN: missing' "$out"

step "A Windows-style Excel export: Windows-1252, semicolons, decimal commas, CRLF"
awk 'BEGIN {
  srand(42)
  printf "customer_id;email;age;monthly_spend;plan;churned\r\n"
  for (i = 1; i <= 400; i++) {
    age = 18 + int(rand() * 60); spend = 5 + rand() * 95
    plan = (rand() < 0.5) ? "basic" : "premium caf\303\251"
    p = (spend > 60 ? 0.75 : 0.2) + (age < 30 ? 0.1 : 0)
    churned = (rand() < p) ? "yes" : "no"
    s = sprintf("%.2f", spend); sub(/\./, ",", s)
    printf "%d;user%d@example.com;%d;%s;%s;%s\r\n", i, i, age, s, plan, churned
  }
}' | iconv -f UTF-8 -t WINDOWS-1252 > "$WORK/My Export.csv"
LOCAL_SHA="$( (sha256sum "$WORK/My Export.csv" 2>/dev/null || shasum -a 256 "$WORK/My Export.csv") | cut -d' ' -f1)"
scp -q "$WORK/My Export.csv" "$HOST:e2e.csv"
out="$(remote camlctl dataset e2e.csv)"; printf '%s\n' "$out"
expect "dataset sha" "^sha256: $LOCAL_SHA$" "$out"
expect "dataset encoding" '^encoding: NOT UTF-8' "$out"
expect "dataset status" '^status: needs-conversion$' "$out"
DATA_PATH="$(sed -n 's/^path: //p' <<< "$out")"
out="$(remote camlctl dataset "$DATA_PATH" --from-encoding WINDOWS-1252)"; printf '%s\n' "$out"
expect "converted" '^encoding: utf-8$' "$out"
expect "separator" '^separator: semicolon$' "$out"
expect "rows" '^rows: 400 ' "$out"

step "Check-in 3, the task: probe without values, remove identifiers, probe with the target"
out="$(remote camlctl caml describe-data "$DATA_PATH" 2>&1)"; printf '%s\n' "$out"
expect "id-like" '^ +1 +customer_id +integer .*id-like' "$out"
expect "pii" '^ +2 +email .*pii\?' "$out"
expect "candidates" '^target_candidates: churned' "$out"
grep -q "@example.com" <<< "$out" && fail "describe-data printed cell values"
out="$(remote camlctl caml anonymize-data "$DATA_PATH" --drop email --out /home/caml/data/e2e-anon.csv --delete-original 2>&1)"
printf '%s\n' "$out"
expect "anonymized" '^dropped: email$' "$out"
expect "original deleted" "^deleted: $DATA_PATH" "$out"
DATA_PATH=/home/caml/data/e2e-anon.csv
out="$(remote camlctl caml describe-data "$DATA_PATH" --target churned 2>&1)"; printf '%s\n' "$out"
expect "task guess" '^task_type_guess: binary' "$out"
expect "classes" '^classes: (no|yes) [0-9]+, (no|yes) [0-9]+$' "$out"

step "prepare-data, exactly as confirmed (a column by number, an explicit type and metric)"
out="$(remote camlctl caml prepare-data "$DATA_PATH" --target churned --type binary --drop 1 --metric auc --metric balacc --name e2e --folds 2 --force 2>&1)"
printf '%s\n' "$out"
expect "prepare-data type" '^Type +binary' "$out"
expect "dropped by number" '^Dropped +customer_id$' "$out"
expect "metric" '^Metric +auc ranks; also balacc$' "$out"
B=input/datasets/e2e/e2e.yaml

step "A helper script written on Windows (CRLF), run with camlctl script: a 60 s budget for CI"
printf '%s\r\n' 'set -eu' \
  "yaml=$B" \
  'grep -q "^  max_runtime_seconds:" "$yaml" || sed -i "s/^  folds: \([0-9]*\)$/  folds: \1\n  max_runtime_seconds: 60/" "$yaml"' \
  'grep -n "max_runtime_seconds" "$yaml"' > "$WORK/short_budget.sh"
scp -q "$WORK/short_budget.sh" "$HOST:short_budget.sh"
out="$(remote camlctl script short_budget.sh)"; printf '%s\n' "$out"
expect "budget" 'max_runtime_seconds: 60' "$out"

step "Install FLAML, detached"
remote camlctl start e2e-install install FLAML
wait_job e2e-install 1800
expect "installed" '^installed: FLAML$' "$(remote camlctl logs e2e-install 20)"

step "Preview and launch the sweep, detached"
out="$(remote camlctl caml sweep FLAML --benchmark "$B" --constraint quick --dry-run 2>/dev/null)"; printf '%s\n' "$out"
expect "dry-run" '^FRAMEWORK' "$out"
remote camlctl start e2e-sweep caml sweep FLAML --benchmark "$B" --constraint quick
sleep 20
out="$(remote camlctl status)"; printf '%s\n' "$out"
expect "status" '^== sweep job e2e-sweep' "$out"
expect "status memory" '^memory: ' "$out"
wait_job e2e-sweep 1800

step "Results"
out="$(remote camlctl caml sweep FLAML --benchmark "$B" --constraint quick --dry-run 2>/dev/null)"; printf '%s\n' "$out"
expect "fold 0 ok" '^FLAML +e2e +fold 0 +ok$' "$out"
expect "fold 1 ok" '^FLAML +e2e +fold 1 +ok$' "$out"
out="$(remote camlctl caml leaderboard --benchmark "$B" --constraint quick 2>&1)"; printf '%s\n' "$out"
expect "leaderboard" 'FLAML' "$out"

step "Hand over the winner: train it on all rows with FLAML's own Python (a CRLF script)"
printf '%s\r\n' \
  'import pickle, sys' \
  'from pathlib import Path' \
  'import flaml' \
  'import pandas as pd' \
  'data = Path("input/datasets/e2e")' \
  'df = pd.concat([pd.read_csv(data / "e2e_train_0.csv"), pd.read_csv(data / "e2e_test_0.csv")])' \
  'X, y = df.drop(columns="churned"), df["churned"]' \
  'automl = flaml.AutoML()' \
  'automl.fit(X_train=X, y_train=y, task="classification", metric="roc_auc", time_budget=15, verbose=0)' \
  'out = Path("output/final-model/FLAML")' \
  'out.mkdir(parents=True, exist_ok=True)' \
  'pickle.dump(automl, open(out / "model.pkl", "wb"))' \
  '(out / "README.md").write_text(f"FLAML {flaml.__version__}, Python {sys.version.split()[0]}, {automl.best_estimator}\n")' \
  'print("rows", len(df), "saved", out)' > "$WORK/fit_final.py"
scp -q "$WORK/fit_final.py" "$HOST:fit_final.py"
remote camlctl start e2e-final script --framework FLAML fit_final.py
wait_job e2e-final 900
expect "final model" '^rows 400 saved output/final-model/FLAML$' "$(remote camlctl logs e2e-final 20)"

step "Bundle and copy back"
out="$(remote camlctl bundle "e2e-$STAMP")"; printf '%s\n' "$out"
REMOTE_BUNDLE="$(sed -n 's/^copy: scp [^:]*:\([^ ]*\) \.$/\1/p' <<< "$out")"
[[ -n "$REMOTE_BUNDLE" ]] || fail "bundle printed no copy line"
scp -q "$HOST:$REMOTE_BUNDLE" "$WORK/"
(cd "$WORK" && tar -xzf "e2e-$STAMP.tar.gz")
grep -q FLAML "$WORK/e2e-$STAMP/output/results.csv" || fail "results.csv in the bundle has no FLAML row"
[[ -f "$WORK/e2e-$STAMP/datasets/e2e/e2e.yaml" && -f "$WORK/e2e-$STAMP/server-info.txt" ]] || fail "bundle is missing files"
[[ -s "$WORK/e2e-$STAMP/output/final-model/FLAML/model.pkl" ]] || fail "bundle is missing the final model"
grep -q "metric: \[auc, balacc\]" "$WORK/e2e-$STAMP/datasets/e2e/e2e.yaml" || fail "the YAML lost the confirmed metrics"
echo "bundle ok: $(find "$WORK/e2e-$STAMP" -type f | wc -l) files"

step "camlctl stop ends a job and its children (real root + sudo)"
printf '%s\n' 'echo sleeping' 'sleep 300' > "$WORK/sleeper.sh"
scp -q "$WORK/sleeper.sh" "$HOST:sleeper.sh"
remote camlctl start e2e-sleeper script sleeper.sh
sleep 3
out="$(remote camlctl stop e2e-sleeper)"; printf '%s\n' "$out"
expect "stopped" '^job e2e-sleeper: failed' "$out"
sleep 2
[[ -z "$(remote "pgrep -f '[s]leep 300' || true")" ]] || fail "the sleeper survived camlctl stop"

step "TabPFN token check never prints a token"
expect "token check" '^token-(set|missing)$' "$(remote camlctl tabpfn-token --check)"

step "Final job list"
remote camlctl jobs
echo
echo "E2E PASSED"
