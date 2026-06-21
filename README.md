# Daily Album Prompt — Phase 1

A GitHub Action picks one album from `catalog.json` every morning and
publishes it as a plain-text RSS item. No links, no art, no tracklist yet —
that's Phase 2 and 3. This phase just needs to work, reliably, every day.

## Setup

1. **Create the repo.** On GitHub, create a new repository (public or
   private — public is needed later for GitHub Pages on a free plan, but
   doesn't matter yet). Don't initialize it with a README/.gitignore from
   GitHub's UI — you already have those here.

2. **Push these files.**
   ```bash
   git init
   git add .
   git commit -m "Phase 1: daily picker"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

3. **Update the feed link.** Open `picker.py`, find `FEED_LINK` near the
   top, and change `YOUR-USERNAME` to your actual GitHub username (and the
   repo path if you didn't name it `daily-album-prompt`). Commit and push
   that change.

4. **Enable GitHub Pages.** Repo Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, folder `/ (root)`. This is what will serve
   `feed.xml` once it exists.

5. **Trigger the first run manually.** Go to the Actions tab → "Daily Album
   Pick" workflow → "Run workflow". This generates the first `feed.xml`,
   `today.json`, and updates `catalog.json` with a `last_prompted` date —
   you don't have to wait until 7am CT to see if it works.

6. **Subscribe in your RSS reader.** Once Pages is live, the feed will be at:
   ```
   https://<your-username>.github.io/<repo-name>/feed.xml
   ```
   Add that URL to FreshRSS (or Reeder directly).

7. **Add your real album list.** Replace or extend `albums.csv` with your
   list, then run:
   ```bash
   python3 build_catalog.py --input albums.csv
   ```
   Safe to re-run any time — it skips albums already in the catalog
   (matched by artist + album, case-insensitive) and only adds new ones.
   Use `--dry-run` first if you want to preview what would be added.

## Files

| File | Purpose |
|---|---|
| `albums.csv` | Human-edited source list. Columns: `artist,album,year` (year optional). |
| `build_catalog.py` | Merges `albums.csv` into `catalog.json`. Idempotent. |
| `catalog.json` | Single source of truth. All enrichment fields are `null` until Phase 2/3. |
| `picker.py` | Runs daily in the Action. Picks one album, writes `feed.xml` and `today.json`, updates `catalog.json`. |
| `.github/workflows/daily-pick.yml` | Scheduled trigger, 7am CT (12:00 UTC), plus manual `workflow_dispatch`. |

## Done when

An album shows up in your RSS reader every morning without you touching
anything. That's the whole bar for Phase 1.

## Next: Phase 2

Tappable Plex/Deezer links and the Obsidian note Shortcut. Needs
`plex_sync.py` running on the EQ14 to populate `plex_id` values, and a
device test of whether Reeder 5 actually opens `shortcuts://` links from
inside a feed item — that's the one real unknown.
