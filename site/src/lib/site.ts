// The leaderboard data every page is built from, and the formatting and routes they share.
import fs from 'node:fs';
import path from 'node:path';

export interface TaskResult { score: number; success_rate: number; n: number }
export interface Readiness { id: string; label: string; reason?: string }
export interface Subject {
  id: string;
  label: string;
  type: string;
  model: string | null;
  harness: string | null;
  simulated: boolean;
  anchor: boolean;
  board: string | null;
  open_weights: { hf_repo?: string; revision?: string; license?: string } | null;
  served_by: string[];
  cost_source: string | null;
  index: number | null;
  ci: [number, number] | null;
  coverage: number;
  categories: Record<string, number | null>;
  pass_at_1: number;
  pass_hat_k: number;
  k: number;
  safety_rate: number;
  cost_per_task: number | null;
  time_per_task: number | null;
  tokens_per_task: number | null;
  value_per_dollar: number | null;
  speedup_vs_expert: number | null;
  runs: string[];
  tasks: Record<string, TaskResult>;
  readiness: Readiness | null;
}
export interface Task {
  id: string;
  version: number;
  title: string;
  category: string;
  difficulty: string;
  horizon: string;
  occupation: string;
  expert_minutes: number;
  expert_cost_usd: number;
}
export interface Level { id: string; label: string; meaning: string; index?: number }
export interface Leaderboard {
  index: {
    name: string;
    version: string;
    status: string;
    categories: Record<string, { label: string; weight: number }>;
    targets: { levels?: Level[]; category?: number };
  };
  tasks: Task[];
  subjects: Subject[];
  generated_at: string;
  owb_version: string;
  sources?: { paths?: string[]; results_repo?: string; results_revision?: string };
  note?: string;
}

let cached: Leaderboard | undefined;

/** public/leaderboard.json, written before the build by `owb demo` or `owb leaderboard`. */
export function leaderboard(): Leaderboard {
  if (cached) return cached;
  const file = path.resolve('public/leaderboard.json');
  if (!fs.existsSync(file)) {
    throw new Error('site/public/leaderboard.json is missing: run `uv run owb demo` or `uv run owb leaderboard --out site/public/leaderboard.json` first.');
  }
  const parsed: Leaderboard = JSON.parse(fs.readFileSync(file, 'utf8'));
  cached = parsed;
  return parsed;
}

/** JSON for a <script type="application/json">, with "</" escaped so it can never close the tag. */
export const embedJson = (value: unknown) => JSON.stringify(value).replace(/<\//g, '<\\/');

export const SITE_NAME = 'OpenWork Bench';
export const REPO = 'https://github.com/different-ai/openwork-bench';
const HF_RESULTS = 'https://huggingface.co/datasets/different-ai/openwork-bench-results';
/** Where the runs behind the board live: a results folder in this repository, or the Hugging Face results dataset. */
export function resultsUrl(): string {
  const p = leaderboard().sources?.paths?.[0];
  return p?.startsWith('results/') ? `${REPO}/tree/pre-release/${p}` : HF_RESULTS;
}
export const base = import.meta.env.BASE_URL.replace(/\/$/, '');
export const route = (p = '') => `${base}/${p}`;
export const docs = (page?: string) => route(`docs/${page ? `${page}/` : ''}`);
/** URL-safe page names; the leaderboard page's script uses the same rule for its links. */
export const slug = (id: string) => id.toLowerCase().replace(/[^a-z0-9.-]+/g, '-');
export const modelRoute = (s: Pick<Subject, 'id'>) => route(`models/${slug(s.id)}/`);
export const taskRoute = (t: Pick<Task, 'id'>) => route(`tasks/${slug(t.id)}/`);

export const fmt = (v: number | null | undefined, digits = 1) => (v == null || Number.isNaN(v) ? '–' : v.toFixed(digits));
export const pct = (v: number | null | undefined) => (v == null ? '–' : `${Math.round(v * 100)}%`);
export const money = (v: number | null | undefined) => (v == null ? 'n/a' : v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(v < 1 ? 3 : 2)}`);
export const minutes = (seconds: number | null | undefined) => (seconds == null ? '–' : (seconds / 60).toFixed(seconds < 60 ? 2 : 1));
export const subjectName = (s: Subject) => s.label + (s.anchor ? ' (closed, for reference)' : '');
/** The same blue scale as the leaderboard's heat tables, for a 0–100 score. */
export const heat = (v: number | null | undefined) => (v == null ? 'var(--s0)' : `var(--s${Math.max(0, Math.min(7, Math.round((v / 100) * 7)))})`);
export const heatInk = (v: number | null | undefined) => (v != null && v >= 64 ? 'var(--s-ink-hi)' : 'var(--ink)');
export const isSample = (lb: Leaderboard) => !lb.subjects.some((s) => s.type === 'model' || s.type === 'product');
