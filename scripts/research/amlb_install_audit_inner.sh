#!/usr/bin/env bash
# Paper-track experiment "claim A" (docs/research/paper-plan.md): does the
# ORIGINAL AMLB still install and run each framework when you follow its own
# documented instructions on a clean machine?
#
# Runs INSIDE a fresh `ubuntu:<version>` container as root, launched by
# scripts/research/run_amlb_install_audit.sh -- never on a real host, and
# never against the local read-only automlbenchmark-reference/ clone (this
# clones AMLB fresh, exactly as a new user would).
#
# Follows docs/getting_started.md of AMLB (as of its 2025-04-19 commit)
# step by step:
#   - prerequisites the docs assume: "Python 3.9 (or higher) and git ...
#     available under the alias `python`" -> python3, python3-venv,
#     python-is-python3, git (+ ca-certificates so git/pip can use HTTPS).
#     Nothing else is pre-installed: if a framework needs more, that is a
#     finding, not something to paper over.
#   - git clone --branch stable --depth 1
#   - python -m venv venv; pip install --upgrade pip; pip install -r requirements.txt
#     (and, if that fails, the docs' own fallback: one requirement at a time)
#   - per framework: `runbenchmark.py <fw> test test -s only` (setup), then
#     `runbenchmark.py <fw> test test -s skip` (run the 3-task test benchmark)
#
# Writes /audit/audit.csv (env,framework,step,status,seconds,detail) plus
# one log per step under /audit/logs/. Never exits early on a failure: every
# step's outcome is data.
set -uo pipefail

AUDIT_DIR="${AUDIT_DIR:-/audit}"
AMLB_REF="${AMLB_REF:-stable}"
STEP_TIMEOUT="${STEP_TIMEOUT:-3600}"
# AMLB's own names (resources/frameworks.yaml). RandomForest is AMLB's
# baseline, included as a control: if it fails too, the problem is AMLB's
# core, not the framework. TabPFN is absent: AMLB has no TabPFN integration.
FRAMEWORKS="${FRAMEWORKS:-RandomForest flaml mljarsupervised AutoGluon H2OAutoML TPOT lightautoml FEDOT GAMA NaiveAutoML SapientML}"

. /etc/os-release
ENV_NAME="ubuntu-${VERSION_ID}"
mkdir -p "$AUDIT_DIR/logs"
CSV="$AUDIT_DIR/audit.csv"
[[ -f "$CSV" ]] || echo "env,framework,step,status,seconds,detail" > "$CSV"

record() {  # framework step status seconds detail
  local detail="${5//\"/\'}"
  detail="${detail//$'\n'/ }"
  printf '%s,%s,%s,%s,%s,"%s"\n' "$ENV_NAME" "$1" "$2" "$3" "$4" "${detail:0:300}" >> "$CSV"
  echo "[$ENV_NAME] $1 $2 -> $3 (${4}s) ${detail:0:120}"
}

# run_step <framework> <step> <command...>: runs with a timeout, logs, records.
run_step() {
  local fw="$1" step="$2"; shift 2
  local log="$AUDIT_DIR/logs/${fw}.${step}.log" start end rc status detail
  start=$(date +%s)
  timeout "$STEP_TIMEOUT" "$@" > "$log" 2>&1
  rc=$?
  end=$(date +%s)
  if [[ $rc -eq 0 ]]; then status=pass; detail=""
  elif [[ $rc -eq 124 ]]; then status=timeout; detail="exceeded ${STEP_TIMEOUT}s"
  else status=fail; detail="exit $rc: $(grep -v '^\s*$' "$log" | tail -1)"
  fi
  LAST_STATUS=$status
  record "$fw" "$step" "$status" "$((end - start))" "$detail"
}

# The launcher points HOME (and TMPDIR) at a bind-mounted work dir so the
# heavy writes stay off the container layer; default to /root when run bare.
WORK_HOME="${HOME:-/root}"
mkdir -p "$WORK_HOME" "${TMPDIR:-/tmp}"
record _env limits info 0 "${AUDIT_LIMITS:-none set} home=$WORK_HOME"

export DEBIAN_FRONTEND=noninteractive
run_step _env apt_prereqs bash -c "apt-get update -q && apt-get install -y -q python3 python3-venv python-is-python3 git ca-certificates"
record _env python_version info 0 "$(python --version 2>&1)"

cd "$WORK_HOME" || exit 1
run_step _env clone git clone https://github.com/openml/automlbenchmark.git --branch "$AMLB_REF" --depth 1
cd automlbenchmark || { record _env clone fail 0 "no checkout"; exit 0; }
record _env amlb_commit info 0 "$(git rev-parse HEAD) ($(git log -1 --format=%cs))"

run_step _env venv python -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate
run_step _env pip_upgrade python -m pip install --upgrade pip
run_step _env core_install python -m pip install -r requirements.txt
CORE_OK=$LAST_STATUS
if [[ "$CORE_OK" != pass ]]; then
  # The docs' own documented fallback.
  run_step _env core_install_sequential bash -c "xargs -L 1 python -m pip install < requirements.txt"
  CORE_OK=$LAST_STATUS
fi

if [[ "$CORE_OK" != pass ]]; then
  for fw in $FRAMEWORKS; do record "$fw" setup blocked 0 "AMLB core install failed"; done
  exit 0
fi

count_scored_rows() {  # framework -> number of scored rows in results/results.csv
  python - "$1" <<'PY'
import csv, math, sys, os
path = "results/results.csv"
fw = sys.argv[1].lower()
n = 0
if os.path.exists(path):
    with open(path) as f:
        for row in csv.DictReader(f):
            try:
                ok = row.get("framework", "").lower() == fw and not math.isnan(float(row.get("result") or "nan"))
            except ValueError:
                ok = False
            n += ok
print(n)
PY
}

for fw in $FRAMEWORKS; do
  run_step "$fw" setup python runbenchmark.py "$fw" test test -s only
  if [[ "$LAST_STATUS" != pass ]]; then
    record "$fw" run blocked 0 "setup failed"
    continue
  fi
  installed="$(head -1 "frameworks/$fw/.setup/installed" 2>/dev/null)"
  [[ -n "$installed" ]] && record "$fw" installed_version info 0 "$installed"
  before=$(count_scored_rows "$fw")
  run_step "$fw" run python runbenchmark.py "$fw" test test -s skip
  after=$(count_scored_rows "$fw")
  # The test benchmark is 3 tasks x 2 folds = 6 jobs.
  record "$fw" scored_jobs info 0 "$((after - before))/6"
done
record _env finished info 0 "audit complete"
