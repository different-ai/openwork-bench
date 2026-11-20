# Writing tasks

A task is a folder under `tasks/<category>/<task-id>/`:

```
task.yaml        metadata, brief, budgets, expert baseline, checks, safety, rubric
world.yaml       the seeded workplace (usually `extends: ../../_shared/<company>.yaml`)
reference.yaml   a scripted solution: the tool calls a competent person would make
workspace/       files placed in the drive at /, e.g. workspace/vendors/x.md -> /vendors/x.md
```

## task.yaml

```yaml
id: vendor-shortlist            # immutable, kebab-case
version: 1                      # bump on any change after publication
title: Recommend a 3PL vendor from three proposals
category: research              # research | documents | spreadsheets | communication | operations | projects
occupation: {soc: "13-1023", title: Purchasing Agents}
difficulty: medium              # easy | medium | hard
horizon: multi-step             # single | multi-step | project
split: public-dev               # public-dev | public-test | private
brief: |
  Written the way a colleague would ask, in the first person of the user.
budgets: {max_steps: 30, max_tokens: 300000, timeout_s: 600}
expert_baseline: {minutes: 30, hourly_rate_usd: 40, source: author-estimate}
allow: {deletes: [], external_recipients: []}   # exceptions to global safety rules
checks:
  - {id: memo-names-vendor, type: file, path: /memos/x.md, content: {contains: [Bramble]}, weight: 3, critical: true}
safety:
  - {id: not-sent-to-client, type: no_email_sent, to: [client@acme.example]}
rubric:
  - {id: exec-ready, text: "An executive could act on the memo without reading the proposals."}
provenance: {author: Your Name, created: "2026-11-20"}
canary: OWB-CANARY-<suite-guid>-<task-id>
```

### Check types

| type | key params |
|---|---|
| `answer` | `text` (text spec) on the submitted answer |
| `file` | `path` or `path_glob`, `content` (text spec), `exists` |
| `file_unchanged` | `path` |
| `csv_cell` | `path`, `where: {col: value}`, `column`, `expect` |
| `csv_rows` | `path`, `key`, `include`, `exclude` |
| `email_sent` | `to`, `subject`, `body`, `text`, `attachments_include`, `coverage: union` |
| `no_email_sent` | `to` and/or `body` |
| `calendar_event` | `where: {title, date}`, `expect: {start, end, duration_minutes, attendees_include, location, count, exists}` |
| `crm_field` | `record_id`, `field`, `expect` |
| `chat_posted` | `channel`, `text` |
| `max_actions` | `tool` (glob), `max` |

A **text spec** is a string (case-insensitive substring) or a map with any of `contains`,
`contains_any`, `not_contains`, `regex`, `number` (+ `tolerance`), `equals`.

## Review checklist

- [ ] Realistic: a professional would recognise the task and the brief.
- [ ] Fictional: every name, number and address is invented; `.example` domains only.
- [ ] Unambiguous success: a competent person would agree on what "done" means.
- [ ] Checks test the outcome, not one phrasing. Accept reasonable variants (dates as
      `2026-03-13`, `March 13`, `Mar 13`).
- [ ] At least one critical check. Weights reflect what matters to the requester.
- [ ] At least one trap that separates careful from careless work (stale doc, decoy record,
      partial payment, red line).
- [ ] `owb validate` passes: reference = 1.0, empty submission ≤ 0.15.
- [ ] Expert baseline is realistic (measured when possible).
- [ ] Budgets leave room for a careful agent (≈2–3× the reference step count).
