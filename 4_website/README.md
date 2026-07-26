# Stage 4: website

**Reads** `1_scrape/malls.parquet` and `2_clean/stores_clean.parquet`.
**Writes** a content hashed bundle into `4_website/site/`.

Run it with `uv run mallscape website`, or `--serve` to open it on
<http://localhost:3000>.

## What is generated and what is not

Only `data-<hash>.json` is generated. `index.html`, `styles.css` and `app.js`
are checked in and reviewed like any other source. The build rewrites one
attribute in `index.html` to point at the new bundle.

The hash is the point: the filename changes whenever the data changes, so a
host can cache the bundle forever and a visitor still gets the newest data. The
previous bundle is deleted, so the deploy directory always holds exactly one.

## Why the bundle is shaped the way it is

322 properties, 11,058 tenant identities and roughly 41,000 brand-to-property edges have to reach
a phone. Three choices keep it near 220 KB compressed: columnar arrays instead
of objects, integer indices into shared dictionaries for every repeated string,
and edges as one flat integer array read in pairs.

## Performance and safety

The list is virtualized. A fixed row height means only the visible window plus
a small overscan is ever in the DOM, so 11,489 results cost the same to scroll
as 50. Search is a substring scan over a lowercased array built once at load,
which stays well inside a frame; input is debounced so a fast typist triggers
one pass rather than one per key.

Every value from the data is written with `textContent`. There is no
`innerHTML` anywhere, so a store name can never become markup. The page runs
under a strict Content Security Policy with no inline script, enforced locally
by the dev server and in production by `vercel.json` or the Pages workflow.

## Hosting

The output is a plain directory of static files.

- **Local**: `uv run mallscape website --serve`, which also applies the same
  cache and security headers as production so local behaviour matches.
- **GitHub Pages**: `.github/workflows/pages.yml` publishes the directory and
  fails the deploy if `index.html` points at a bundle that is not committed.
- **Vercel**: `vercel.json` sets the output directory and headers. No build
  command, because there is nothing to build.

### Hosting

Live at <https://alpharomercoma.github.io/philippine-mall-explorer/>.

```bash
make deploy      # build, then publish to the gh-pages branch
```

Pages serves the `gh-pages` branch from its root, so `4_website/deploy/publish.sh`
copies the site directory to the top level of an orphan branch. That route was
chosen deliberately over a workflow: pushing anything into `.github/workflows/`
requires a token carrying the `workflow` scope, which the default one does not
have, so a workflow-based deploy fails at `git push` for most contributors.

The script refuses to publish if `index.html` points at a bundle that is not
present, which is the one failure that would otherwise produce a live page
showing nothing. It also writes `.nojekyll`, without which Pages runs the files
through Jekyll and drops anything it does not recognize.

An Actions workflow is still available at `4_website/deploy/github-pages.yml`
for anyone who does have the scope: move it to `.github/workflows/` and switch
the Pages source to "GitHub Actions".

Vercel needs none of this. Point it at the repo and `vercel.json` does the rest.
