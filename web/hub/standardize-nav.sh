#!/usr/bin/env bash
# Standardize the home-lab hub nav links to the three live sections:
#   Network (/)  ·  Fitness (/personal/)  ·  Forrest (/forrest/)
#
# Run on the Pro:   bash web/hub/standardize-nav.sh
#
# Pipes standardize_nav.py to the mini over SSH; it rewrites the injected nav
# block in each live page in place, leaving a .navbak copy for rollback. Parked
# pages (grid-life, news) are left as-is; the Forrest page already carries these
# links, so it is not touched.
set -euo pipefail
MINI=mini-ts
HERE="$(cd "$(dirname "$0")" && pwd)"

ssh "$MINI" 'python3 -' < "$HERE/standardize_nav.py"

echo "-- live check --"
for u in / /personal/ /forrest/; do
  printf "  %-11s HTTP %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' "http://100.120.201.45:8787$u")"
done
echo "Rollback: ssh $MINI 'cd /Users/george/LLD-health/web && cp index.html.navbak index.html && cp personal/index.html.navbak personal/index.html'"
