#!/usr/bin/env bash
# Regenerate the README banner and diagrams from their TikZ sources.
#
# These images (embedded by README.md as docs/assets/*.svg) are authored in
# TikZ and rendered to self-contained SVG with every glyph converted to a
# path, so they look identical everywhere GitHub renders them. Each diagram
# sits on its own white rounded card (styles.tex) so it stays readable on
# GitHub's dark theme; the banner is its own dark card.
#
# Pipeline: latex (DVI) + dvisvgm, with TikZ's native dvisvgm driver
# (styles.tex sets \pgfsysdriver). Don't switch back to pdflatex +
# `dvisvgm --pdf`: that route renders every transparency as a solid
# black/white block (found 2026-10-24).
#
# Requires (Debian/Ubuntu):
#   sudo apt-get install texlive-latex-extra texlive-pictures texlive-fonts-extra dvisvgm
#   (latex + tikz + standalone + pgf, Fira Sans/Mono, plus dvisvgm)
#
# Usage:  bash docs/assets/diagrams/build.sh
# Output: docs/assets/{banner,workflow,pipeline,isolation,families,provisioning}.svg
set -euo pipefail
cd "$(dirname "$0")"

DIAGRAMS=(banner workflow pipeline isolation families provisioning)
for d in "${DIAGRAMS[@]}"; do
  echo "==> $d"
  latex -interaction=nonstopmode -halt-on-error "$d.tex" >/dev/null
  dvisvgm --no-fonts --exact-bbox "$d.dvi" -o "../$d.svg" >/dev/null 2>&1
done

rm -f ./*.aux ./*.log ./*.dvi
echo "wrote docs/assets/{$(IFS=,; echo "${DIAGRAMS[*]}")}.svg"
