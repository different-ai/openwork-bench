# Maintaining

How changes reach `main` and the website. The setup mirrors other different-ai repositories.

## Branches

- **`pre-release`** is where work lands. Open every PR against it (`--base pre-release`). It has no
  organization gates, so a PR merges once its checks pass.
- **`main`** is the default branch and holds releases. The organization's ruleset protects it:
  pull requests only, linear history (squash or rebase), signed commits, one approval after the
  last push, and CodeQL results. It accepts PRs from `pre-release` or `hotfix/*` only
  (the `main accepts releases only` check).

## Releasing to `main`

1. Open a PR from `pre-release` to `main`.
2. CI runs. When every job passes, the `approve when CI passes` job approves the PR as
   `github-actions`. That approval satisfies the ruleset; it approves what CI checked, not what a
   person read. A new push dismisses it, and the next green run approves again. Forks are never
   approved.
3. Squash-merge the PR. `sync-pre-release` then merges `main` back into `pre-release`, so the next
   release PR stays conflict-free.

Do not add a `CODEOWNERS` file: the ruleset would then require a code owner's review, which the
CI approval cannot give.

## The website

`site/` is an Astro site: the leaderboard page (`site/src/pages/index.astro`) and the docs
(Starlight, synced from `docs/` by `site/scripts/sync-docs.mjs`). The `site` workflow builds it on
every PR, checking every docs link, and publishes it to
[GitHub Pages](https://different-ai.github.io/openwork-bench/) on every push to `pre-release`.
The leaderboard comes from the results revision pinned in `leaderboard/published.yaml`, or from
the offline demo until one is pinned. See [`site/README.md`](../site/README.md) to run it locally.
