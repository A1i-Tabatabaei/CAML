#!/usr/bin/env bash
# Shared packaging helper, sourced by scripts/provision_vps.sh and
# scripts/sync_vps.sh. Not meant to be run directly.
#
# caml_package_archive <out.tar.gz> <include_worktree: 0|1>
#   Builds a gzip'd tarball of the CAML source with every path prefixed
#   `CAML/`, from either HEAD (`git archive`) or the live working tree
#   (tracked + untracked, gitignore-excluded), and appends a `CAML/REVISION`
#   file:
#       commit=<full sha of HEAD>
#       branch=<branch>
#       dirty=<1 if the working tree was packaged AND has uncommitted changes>
#   A VPS checkout has no .git, so caml.resources.git_info reads this file
#   to keep results.csv's `app_version` column traceable to an exact commit.
#   Must be called from the repo root.

caml_package_archive() {
  local out="$1" include_worktree="${2:-0}"
  local tar_tmp rev_dir dirty=0
  tar_tmp="$(mktemp --suffix=.tar)"
  rev_dir="$(mktemp -d)"

  if [[ "$include_worktree" == "1" ]]; then
    git ls-files -co --exclude-standard | tar cf "$tar_tmp" --transform 's,^,CAML/,' -T -
    [[ -n "$(git status --porcelain)" ]] && dirty=1
  else
    git archive --format=tar --prefix=CAML/ HEAD > "$tar_tmp"
  fi

  printf 'commit=%s\nbranch=%s\ndirty=%s\n' \
    "$(git rev-parse HEAD)" "$(git rev-parse --abbrev-ref HEAD)" "$dirty" > "$rev_dir/REVISION"
  tar rf "$tar_tmp" -C "$rev_dir" --transform 's,^,CAML/,' REVISION

  gzip -c "$tar_tmp" > "$out"
  rm -rf "$tar_tmp" "$rev_dir"
}
