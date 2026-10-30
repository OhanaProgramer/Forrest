#!/usr/bin/env bash
# Standardize the home-lab hub nav links to the three live sections:
#   Network (/)  ·  Fitness (/personal/)  ·  Forrest (/forrest/)
#
# Run on the Pro:   bash web/hub/standardize-nav.sh
#
# Edits the injected nav block in each live page on the mini, in place, keeping
# each page's own styling (private-nav.css). A .navbak copy is left next to each
# edited file for rollback. Parked pages (grid-life, news-review) are left as-is.
# The Forrest page already carries these three links, so it is not touched.
set -euo pipefail
MINI=mini-ts

ssh "$MINI" 'python3 - <<PY
import re, shutil, pathlib
WEB = pathlib.Path("/Users/george/LLD-health/web")
links = [("/","Network"), ("/personal/","Fitness"), ("/forrest/","Forrest")]
pages = {"/":"index.html", "/personal/":"personal/index.html"}
def block(cur):
    a = "".join(\x27<a href="%s"%s>%s</a>\x27 % (u, (\x27 aria-current="page"\x27 if u==cur else \x27\x27), l) for u,l in links)
    return \x27<!-- grid-life-private-nav:hub-1.0 --><div id="private-pages-nav" role="navigation" aria-label="Private pages">\x27 + a + \x27</div><!-- /grid-life-private-nav -->\x27
pat = re.compile(r\x27<!-- grid-life-private-nav:.*?<!-- /grid-life-private-nav -->\x27, re.S)
for cur, rel in pages.items():
    p = WEB / rel
    t = p.read_text()
    t2, n = pat.subn(lambda m, c=cur: block(c), t)
    assert n == 1, rel + " matched " + str(n)
    shutil.copy2(str(p), str(p) + ".navbak")
    p.write_text(t2)
    print("updated", rel)
PY'

echo "-- live check --"
for u in / /personal/ /forrest/; do
  printf "  %-11s HTTP %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' "http://100.120.201.45:8787$u")"
done
echo "Rollback: ssh $MINI 'cd /Users/george/LLD-health/web && cp index.html.navbak index.html && cp personal/index.html.navbak personal/index.html'"
