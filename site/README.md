# OpenWork Bench site

The leaderboard (`src/pages/index.astro`) and the docs (Starlight, synced from `../docs` by
`scripts/sync-docs.mjs`), published to GitHub Pages from `pre-release` by
`.github/workflows/site.yml`.

```bash
uv run owb demo --repeats 1       # writes public/leaderboard.json from the offline demo
cd site && npm ci && npm run dev  # http://localhost:4321/openwork-bench/
npm run build                     # dist/, with every docs link checked
```

The page embeds `public/leaderboard.json` at build time and the build fails without it. For a
published leaderboard, CI writes it with `owb leaderboard --out site/public/leaderboard.json`
from the results revision pinned in `leaderboard/published.yaml`.
