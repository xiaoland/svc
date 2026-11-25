#!/bin/sh
# check-default-patterns.sh — flag model default patterns in markup and styles.
#
# Usage: check-default-patterns.sh <file> [<file>...]
# Reads HTML/JSX/CSS/TSX sources and prints one finding per line:
#   <file>:<line>: <rule-id>: <what was found>
#
# A finding is evidence that a free axis may have been spent on a default,
# not a defect. Each pattern is legitimate for some brief; decide, don't ban.
# Exit 0 with no output means no pattern matched, not that the design is good.
#
# Rules are PCRE-lite extended regex over single lines; keep each rule cheap
# to evaluate and cheap to justify. Add a rule only with a counterexample in
# mind: if no legitimate use exists, the rule belongs in a linter instead.

set -u

status=0

report() {
  # $1 file, $2 rule id, $3 regex, $4 description
  grep -nEi "$3" "$1" 2>/dev/null | while IFS=: read -r line text; do
    printf '%s:%s: %s: %s\n' "$1" "$line" "$2" "$4"
  done
  grep -qEi "$3" "$1" 2>/dev/null && status=1
  return 0
}

for f do
  case "$f" in
    *.html|*.htm|*.jsx|*.tsx|*.css|*.scss|*.vue|*.svelte|*.md|*.mdx) ;;
    *) continue ;;
  esac

  # Cards as universal container; nested cards.
  report "$f" "cards-as-scaffold" 'class="[^"]*card[^"]*"[^>]*>[^<]*<[^>]*class="[^"]*card' \
    "card nested inside card"
  # Eyebrow/kicker label above headings.
  report "$f" "eyebrow-label" 'class="[^"]*(eyebrow|kicker|overline)[^"]*"' \
    "tracked-out label above a heading"
  # Hero metric template: big number with small label cluster.
  report "$f" "hero-metric" 'text-(5xl|6xl|7xl|8xl|9xl)[^"]*"[^>]*>[^<]*[0-9]' \
    "oversized display numeral — the hero-metric template"
  # All-caps labels via CSS.
  report "$f" "all-caps-label" 'text-transform:\s*uppercase' \
    "uppercase transform — check the content is a label that earns it"
  # Gradient text.
  report "$f" "gradient-text" '(-webkit-)?background-clip:\s*text' \
    "gradient text — emphasis usually belongs to weight or size"
  # Purple/indigo default palette.
  report "$f" "default-purple" '#(6366f1|8b5cf6|a855f7|7c3aed|4f46e5)' \
    "Tailwind indigo/violet/purple default hex"
  # Section numbering as decoration.
  report "$f" "section-numbering" '>\s*0[1-9]\s*(</|—|-)' \
    "numbered marker — encode a real sequence or drop it"
  # Shadow costume: hard offset block shadow.
  report "$f" "hard-block-shadow" 'box-shadow:\s*[0-9]+px\s+[0-9]+px\s+0([^.0-9]|$)' \
    "zero-blur offset shadow — neobrutalist costume outside that world"
  # Lorem ipsum or placeholder copy.
  report "$f" "placeholder-copy" 'lorem ipsum' \
    "placeholder copy hides real layout behavior"
  # Skipped heading levels (h1 followed later by h3 with no h2 in file).
  levels=$(grep -oEi '<h[1-6]' "$f" 2>/dev/null | grep -oE '[1-6]' | sort -n | uniq | tr '\n' ' ')
  prev=0
  for l in $levels; do
    if [ "$l" -gt $((prev + 1)) ] && [ "$prev" -ne 0 ]; then
      printf '%s:1: heading-skip: heading levels jump from h%s to h%s\n' "$f" "$prev" "$l"
      status=1
      break
    fi
    prev=$l
  done
done

exit $status
