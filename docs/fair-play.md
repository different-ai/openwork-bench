# Fair play

OpenWork maintains OpenWork Bench and OpenWork appears on it. A vendor-run benchmark is only
useful if the rules make its results hard to dispute. These rules are part of the product.

1. **Anyone can reproduce any public row** with one command and their own keys.
2. **Every adapter and config is public**, OpenWork's included. Vendors may submit or fix their
   own adapter; maintainers run it as submitted.
3. **Same budgets for everyone**: steps, tokens and wall-clock per task, set in the task, not the
   subject. Actual spend is shown.
4. **OpenWork rows are labelled "maintainer"** on the leaderboard.
5. **No home advantage.** Tasks use generic MCP tools, never OpenWork-only features. Task and
   method changes land as public PRs before any results that depend on them.
6. **Publish losses.** If OpenWork is not top in a category, the board says so.
7. **Judges exclude the subject's model family**, and judge–human agreement is published.
8. **Corrections in public.** Errata, regrades and voided runs are listed in `errata/`.
9. **Private split, public rules.** The held-out split's size, categories and refresh schedule are
   public; it is run identically for every subject.
10. **Outside review** (from v0.3): an independent reviewer signs off each index version.

Disputes: open an issue with the run id and task. If a grader is wrong, it is fixed for everyone
and published results are regraded.
