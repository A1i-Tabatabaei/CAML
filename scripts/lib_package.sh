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
#
# Portable to macOS (bash 3.2, BSD mktemp, bsdtar) as well as Linux: it
# stages the files in a temp directory and tars that, instead of GNU-only
# `mktemp --suffix` and `tar --transform` (which broke every run from a Mac
# until 2026-10-24). COPYFILE_DISABLE=1 stops macOS tar from adding `._*`
# AppleDouble files.

caml_package_archive() {
  local out="$1" include_worktree="${2:-0}"
  local stage dirty=0
  stage="$(mktemp -d "${TMPDIR:-/tmp}/caml-package.XXXXXX")"
  mkdir "$stage/CAML"

  if [[ "$include_worktree" == "1" ]]; then
    git ls-files -co --exclude-standard | COPYFILE_DISABLE=1 tar cf - -T - | tar xf - -C "$stage/CAML"
    [[ -n "$(git status --porcelain)" ]] && dirty=1
  else
    git archive --format=tar HEAD | tar xf - -C "$stage/CAML"
  fi

  printf 'commit=%s\nbranch=%s\ndirty=%s\n' \
    "$(git rev-parse HEAD)" "$(git rev-parse --abbrev-ref HEAD)" "$dirty" > "$stage/CAML/REVISION"

  COPYFILE_DISABLE=1 tar czf "$out" -C "$stage" CAML
  rm -rf "$stage"
}
