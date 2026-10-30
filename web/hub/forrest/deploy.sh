#!/usr/bin/env bash
# Deploy the Forrest page to the home-lab hub (mini). Run on the Pro from the repo:
#   bash web/hub/forrest/deploy.sh
# Additive: creates /forrest/ on the hub. Re-running just replaces the two files.
# To update the page later without a full deploy, edit forrest.json on the mini
# (the page fetches it live) or re-run this.
set -euo pipefail
MINI=mini-ts                                   # SSH host alias (same as grid-life deploys)
WEBROOT=/Users/george/LLD-health/web
HERE="$(cd "$(dirname "$0")" && pwd)"

scp -q "$HERE/index.html" "$HERE/forrest.json" "$MINI:$WEBROOT/forrest/" 2>/dev/null \
  || { ssh "$MINI" "mkdir -p $WEBROOT/forrest"; scp -q "$HERE/index.html" "$HERE/forrest.json" "$MINI:$WEBROOT/forrest/"; }

code=$(curl -s -o /dev/null -w '%{http_code}' http://100.120.201.45:8787/forrest/)
echo "Live check: http://100.120.201.45:8787/forrest/  ->  HTTP $code"
