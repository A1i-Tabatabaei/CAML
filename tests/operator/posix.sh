#!/usr/bin/env bash
# The macOS and Linux operator profiles' commands, checked on a real machine.
#
# CI runs it on macOS (stock /bin/bash 3.2, zsh, BSD tools) and on Ubuntu.
# It needs no server: it checks what operator-macos.md and operator-linux.md
# (skills/caml-benchmark/references/) claim about this machine.
# Run from the repo root: bash tests/operator/posix.sh
set -u
failures=0
check() {  # check NAME CONDITION_EXIT_CODE [DETAIL]
  if [ "$2" -eq 0 ]; then echo "ok    $1"; else echo "FAIL  $1 ${3:-}"; failures=$((failures + 1)); fi
}
note() { echo "note  $*"; }

os="$(uname -s)"
echo "$os $(uname -r) $(uname -m); bash $BASH_VERSION"
[ "$os" = "Darwin" ] && note "macOS $(sw_vers -productVersion)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/caml-operator.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

# 1. Tools the profiles rely on.
for t in ssh scp ssh-keygen tar; do
  command -v "$t" > /dev/null; check "$t on PATH" $?
done
note "ssh -V: $(ssh -V 2>&1)"
command -v ssh-copy-id > /dev/null && note "ssh-copy-id: present" || note "ssh-copy-id: missing (use the profile's fallback)"

# 2. The SSH host alias block from this OS's profile.
if [ "$os" = "Darwin" ]; then
  printf '%s\n' 'Host caml-vps' '  HostName 203.0.113.10' '  User root' '  IdentityFile ~/.ssh/id_ed25519' \
    '  AddKeysToAgent yes' '  UseKeychain yes' '  ServerAliveInterval 30' '  ServerAliveCountMax 6' > "$tmp/config"
else
  printf '%s\n' 'Host caml-vps' '  HostName 203.0.113.10' '  User root' '  IdentityFile ~/.ssh/id_ed25519' \
    '  ServerAliveInterval 30' '  ServerAliveCountMax 6' > "$tmp/config"
fi
resolved="$(ssh -G -F "$tmp/config" caml-vps 2>&1)"
echo "$resolved" | grep -qx 'hostname 203.0.113.10'; check "ssh reads the alias: hostname" $? "$(echo "$resolved" | head -3)"
echo "$resolved" | grep -qx 'user root'; check "ssh reads the alias: user" $?
# A config written on a Mac breaks elsewhere: UseKeychain is Apple-only.
printf '%s\n' 'Host caml-vps' '  HostName 203.0.113.10' '  UseKeychain yes' > "$tmp/config-keychain"
if ssh -G -F "$tmp/config-keychain" caml-vps > /dev/null 2>&1; then
  note "UseKeychain: accepted here"
else
  note "UseKeychain: rejected here ($(ssh -G -F "$tmp/config-keychain" caml-vps 2>&1 | head -1))"
  printf '%s\n' 'IgnoreUnknown UseKeychain' 'Host caml-vps' '  HostName 203.0.113.10' '  UseKeychain yes' > "$tmp/config-ignore"
  ssh -G -F "$tmp/config-ignore" caml-vps > /dev/null 2>&1; check "IgnoreUnknown UseKeychain fixes it" $?
fi

# 3. The documented remote command strings reach ssh unchanged, in bash and
#    in zsh (the default macOS shell). `sh -c` stands in for ssh.
cat > "$tmp/argv.sh" <<'EOF'
sh -c 'printf "%s\n" "$1"' _ "command -v git || (apt-get update -qq && apt-get install -y -qq git)"
sh -c 'printf "%s\n" "$1"' _ "test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src"
sh -c 'printf "%s\n" "$1"' _ "mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
sh -c 'printf "%s|" "$@"; echo' _ camlctl start sweep caml sweep FLAML --benchmark input/datasets/churn/churn.yaml --constraint quick
EOF
cat > "$tmp/expected" <<'EOF'
command -v git || (apt-get update -qq && apt-get install -y -qq git)
test -d /opt/caml-src || git clone -q https://github.com/A1i-Tabatabaei/CAML.git /opt/caml-src
mkdir -p ~/.ssh && chmod 700 ~/.ssh && tr -d '\r' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
camlctl|start|sweep|caml|sweep|FLAML|--benchmark|input/datasets/churn/churn.yaml|--constraint|quick|
EOF
for sh_ in bash zsh; do
  if command -v "$sh_" > /dev/null; then
    "$sh_" "$tmp/argv.sh" > "$tmp/got-$sh_" 2>&1
    cmp -s "$tmp/expected" "$tmp/got-$sh_"; check "remote command strings survive $sh_" $? "$(diff "$tmp/expected" "$tmp/got-$sh_")"
  else
    note "$sh_ not installed; skipped"
  fi
done

# 4. SHA-256 the profile's way.
printf 'abc' > "$tmp/abc.txt"
want=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
if [ "$os" = "Darwin" ]; then
  got="$(shasum -a 256 "$tmp/abc.txt" | cut -d' ' -f1)"
  rc=0; [ "$got" = "$want" ] || rc=1; check "shasum -a 256" "$rc" "$got"
  command -v sha256sum > /dev/null && note "sha256sum: present on this macOS" || note "sha256sum: missing on this macOS (use shasum -a 256)"
else
  got="$(sha256sum "$tmp/abc.txt" | cut -d' ' -f1)"
  rc=0; [ "$got" = "$want" ] || rc=1; check "sha256sum" "$rc" "$got"
fi

# 5. A result bundle (gzip tar, like camlctl bundle) unpacks.
mkdir -p "$tmp/src/run1/output"
printf 'framework,result\nFLAML,0.9\n' > "$tmp/src/run1/output/results.csv"
(cd "$tmp/src" && COPYFILE_DISABLE=1 tar -czf "$tmp/run1.tar.gz" run1)
mkdir "$tmp/out"
(cd "$tmp/out" && tar -xzf "$tmp/run1.tar.gz")
[ -f "$tmp/out/run1/output/results.csv" ]; check "tar -xzf unpacks a bundle" $?

# 6. BSD versus GNU differences the macOS profile warns about.
for t in timeout watch; do
  command -v "$t" > /dev/null && note "$t: present" || note "$t: missing"
done
if date -d '2026-01-01' > /dev/null 2>&1; then note "date -d: works"; else note "date -d: not supported (BSD date)"; fi

if [ "$failures" -gt 0 ]; then echo "$failures check(s) failed"; exit 1; fi
echo "all checks passed"
