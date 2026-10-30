"""Standardize the home-lab hub nav to: Network / Fitness / Forrest.

Runs on the mini (piped in by standardize-nav.sh via `ssh mini-ts 'python3 -'`).
Rewrites the injected nav block in each live page in place, keeping each page's
own styling. Leaves a .navbak copy beside each edited file for rollback.
Parked pages (grid-life, news) are not listed here, so they are left as-is.
"""
import re
import shutil
import pathlib

WEB = pathlib.Path("/Users/george/LLD-health/web")
LINKS = [("/", "Network"), ("/personal/", "Fitness"), ("/forrest/", "Forrest")]
PAGES = {"/": "index.html", "/personal/": "personal/index.html"}
PAT = re.compile(r"<!-- grid-life-private-nav:.*?<!-- /grid-life-private-nav -->", re.S)


def block(cur):
    anchors = "".join(
        '<a href="%s"%s>%s</a>' % (u, ' aria-current="page"' if u == cur else "", label)
        for u, label in LINKS
    )
    return (
        "<!-- grid-life-private-nav:hub-1.0 -->"
        '<div id="private-pages-nav" role="navigation" aria-label="Private pages">'
        + anchors
        + "</div><!-- /grid-life-private-nav -->"
    )


for cur, rel in PAGES.items():
    p = WEB / rel
    text = p.read_text()
    new, n = PAT.subn(lambda m, c=cur: block(c), text)
    assert n == 1, "%s: expected 1 nav block, found %d" % (rel, n)
    shutil.copy2(str(p), str(p) + ".navbak")
    p.write_text(new)
    print("updated", rel)
