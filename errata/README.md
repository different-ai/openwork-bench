# Errata

Every correction to published results is recorded here as one YAML file, reviewed by pull
request. Published data on Hugging Face is never rewritten; the leaderboard builder applies
these entries instead. See `docs/versioning.md`.

```yaml
id: E-0001                     # sequential
date: 2026-12-01
type: task-fix | grader-fix | void-run | pricing | other
summary: One sentence on what was wrong.
affects:
  tasks: [vendor-shortlist@1]  # task@version
  runs: []                     # run ids
  subjects: []
action: rerun | regrade | void | none
resolution: What was done, with links to the PR and the Hugging Face commit.
```

`action: void` removes the listed runs or subjects from every leaderboard built afterwards.
Task fixes bump the task's `version`, which makes older rows stale automatically.
