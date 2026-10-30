# Home-lab hub — how to add a page

Quick procedure for future-me / another thread. This is how the Forrest page
(`/forrest/`) was added.

## What the hub is
- A **static site** served at `http://100.120.201.45:8787/` from the **mini**,
  web root `/Users/george/LLD-health/web/`.
- Any subfolder `foo/` under that root is **auto-served at `/foo/`** — no server
  config, no restart (confirmed by how `grid-life/field/` was added).
- SSH alias for the mini: **`mini-ts`**. All deploys run **from the Pro** (it
  has the mini SSH keys). The Pro is the source of truth; the mini only receives.
- Shared nav is injected into each page between
  `<!-- grid-life-private-nav:… -->…<!-- /grid-life-private-nav -->` markers,
  styled by `/grid-life/private-nav.css`.

## To add a page `/NAME/`
1. **Author** `web/hub/NAME/index.html` — self-contained, George's dark style
   (`--bg:#14161a; --card-bg:#1f232a; --text:#e6e8eb; --accent:#6496ff`), plus a
   `NAME.json` the page fetches (`fetch('./NAME.json')`) so later updates are a
   one-line JSON edit, not a redeploy. **Copy `web/hub/forrest/` as the template.**
2. **Deploy** (from the Pro): scp the folder to the mini web root, then check it.
   See `web/hub/forrest/deploy.sh` — it does:
   `scp index.html NAME.json mini-ts:/Users/george/LLD-health/web/NAME/`
   (mkdir the dir first if new), then
   `curl -s -o /dev/null -w '%{http_code}' http://100.120.201.45:8787/NAME/`.
3. **Add to the nav**: edit the `LINKS` list in `web/hub/standardize_nav.py`
   (add `("/NAME/", "Label")`), then run `web/hub/standardize-nav.sh` from the
   Pro. It rewrites the injected nav block in each live page in place, with a
   `.navbak` rollback.

## To update a page's data later
Edit its `.json` — on the mini directly (the page fetches it live) or in the repo
and redeploy.

## Known gap
The hub's own pages (`/`, `/personal/`) currently live **only on the mini** — no
Pro git repo yet, so they aren't version-backed. The Forrest page and these
scripts **are** in git (`OhanaProgramer/Forrest`, under `web/hub/`). Planned fix:
a `lld-health` (or `home-lab`) repo on the Pro that holds the hub web root, mini
pulls from it. Do that before building much more on the hub.
