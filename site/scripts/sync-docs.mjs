// Builds the Starlight content tree from ../docs so the docs stay single-sourced:
//   ../docs/*.md -> src/content/docs/docs/*.md, plus an index of them at /docs/.
// Relative links become site routes, or GitHub links for files outside docs/.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(site, '..');
const out = path.join(site, 'src/content/docs/docs');
const BASE = '/openwork-bench';
const GITHUB = 'https://github.com/different-ai/openwork-bench';
const BRANCH = 'pre-release';
// Sidebar order; pages not listed follow, alphabetically.
const ORDER = ['methodology', 'open-weights', 'fair-play', 'openwork-desktop', 'harness-adapters', 'task-format', 'data-on-hugging-face', 'versioning', 'maintaining', 'PLAN'];

// Starlight lowercases page slugs (docs/PLAN.md is served at /docs/plan/).
const routeFor = (repoPath) => (/^docs\/[^/]+\.md$/.test(repoPath) ? repoPath.slice(5, -3).toLowerCase() : null);

function rewriteLinks(md, fromRepoPath) {
  const dir = path.posix.dirname(fromRepoPath);
  return md.replace(/(!?)\]\(([^)\s]+)((?:\s+"[^"]*")?)\)/g, (all, bang, target, title) => {
    if (/^(https?:|mailto:|#)/.test(target)) return all;
    const [p, hash = ''] = target.split('#');
    const resolved = path.posix.normalize(path.posix.join(dir, p));
    const route = bang ? null : routeFor(resolved);
    let url;
    if (route !== null) {
      url = `${BASE}/docs/${route}/`;
    } else {
      const abs = path.join(repo, resolved);
      const kind = fs.existsSync(abs) && fs.statSync(abs).isDirectory() ? 'tree' : bang ? 'raw' : 'blob';
      url = `${GITHUB}/${kind}/${BRANCH}/${resolved}`;
    }
    return `${bang}](${url}${hash ? '#' + hash : ''}${title})`;
  });
}

function page(fromRepoPath, md, extra = {}) {
  let title = path.basename(fromRepoPath, '.md');
  const h1 = md.match(/^# (.+)\n/m);
  if (h1 && md.indexOf(h1[0]) === md.search(/\S/)) {
    title = h1[1].trim();
    md = md.replace(h1[0], '');
  }
  const fm = { title: title.replace(/`/g, ''), ...extra };
  const front = Object.entries(fm).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join('\n');
  const source = `\n\n---\n\n<small>Source: [\`${fromRepoPath}\`](${GITHUB}/blob/${BRANCH}/${fromRepoPath})</small>\n`;
  return { title: fm.title, text: `---\n${front}\n---\n${rewriteLinks(md, fromRepoPath)}${source}` };
}

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const files = fs.readdirSync(path.join(repo, 'docs')).filter((f) => f.endsWith('.md'));
const rank = (slug) => (ORDER.includes(slug) ? ORDER.indexOf(slug) : ORDER.length);
files.sort((a, b) => rank(a.slice(0, -3)) - rank(b.slice(0, -3)) || a.localeCompare(b));

const index = [];
files.forEach((file, i) => {
  const rel = `docs/${file}`;
  const { title, text } = page(rel, fs.readFileSync(path.join(repo, rel), 'utf8'), { sidebar: { order: i + 1 } });
  fs.writeFileSync(path.join(out, file), text);
  index.push(`- [${title}](${BASE}/docs/${routeFor(rel)}/)`);
});

fs.writeFileSync(path.join(out, 'index.md'), [
  '---',
  'title: "Documentation"',
  'sidebar: {"order":0,"label":"Overview"}',
  '---',
  'How OpenWork Bench measures AI knowledge work, how to run it and how to contribute.',
  `The [leaderboard](${BASE}/) shows the current results.`,
  '',
  ...index,
  '',
].join('\n'));

console.log(`synced ${files.length} docs into ${path.relative(site, out)}`);
