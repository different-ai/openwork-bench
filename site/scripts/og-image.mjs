// Renders public/og.png, the 1200x630 image link previews show, with headless Chrome.
// Run it after changing the brand or the headline, and commit the result:
//   node scripts/og-image.mjs           (CHROME=/path/to/chrome to pick a browser)
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(site, 'public/og.png');

const GLYPHS = {
  O: ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
  P: ['11110', '10001', '10001', '11110', '10000', '10000', '10000'],
  E: ['11111', '10000', '10000', '11110', '10000', '10000', '11111'],
  N: ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
};
let x = 0;
const pixels = [];
for (const ch of 'OPEN') {
  GLYPHS[ch].forEach((row, y) => [...row].forEach((bit, i) => {
    if (bit === '1') pixels.push(`<rect x="${(x + i + 0.05).toFixed(2)}" y="${(y + 0.05).toFixed(2)}" width="0.9" height="0.9" rx="0.12"/>`);
  }));
  x += 6;
}
const wordmark = `<svg viewBox="0 -0.6 ${x + 52} 8.2" height="74" fill="#e9edf2">${pixels.join('')}
  <text x="${x + 0.4}" y="6.55" style="font: 600 9.2px Inter; letter-spacing: -0.4px">Work</text>
  <text x="${x + 25.5}" y="6.55" style="font: 400 9.2px Inter; letter-spacing: -0.4px" fill="#6f7f90">Bench</text></svg>`;

// Bars and a dashed trust target: the leaderboard's own chart, reduced to a motif.
const bars = [88, 76, 69, 54, 41, 28];
const chart = `<svg width="330" height="300" viewBox="0 0 330 300">
  <defs><pattern id="h" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <rect width="7" height="7" fill="#1baf7a" opacity=".28"/><line x1="0" y1="0" x2="0" y2="7" stroke="#1baf7a" stroke-width="3.5"/></pattern></defs>
  <line x1="0" x2="330" y1="${300 - 2.6 * 80}" y2="${300 - 2.6 * 80}" stroke="#9fb0c2" stroke-dasharray="7 6" opacity=".7"/>
  <text x="330" y="${300 - 2.6 * 80 - 10}" text-anchor="end" style="font: 500 15px Inter" fill="#9fb0c2">Delegable</text>
  ${bars.map((v, i) => `<rect x="${i * 56}" y="${300 - 2.6 * v}" width="40" height="${2.6 * v}" rx="5" fill="${i === 0 ? '#e9edf2' : 'url(#h)'}"/>`).join('')}
</svg>`;

const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  html, body { margin: 0; width: 1200px; height: 630px; overflow: hidden; }
  body { background: #011627; color: #e9edf2; font-family: Inter, sans-serif; position: relative; }
  .dots { position: absolute; inset: 0; background-image: radial-gradient(circle, rgba(233,237,242,.16) 1.3px, transparent 1.6px); background-size: 12px 12px;
    -webkit-mask-image: radial-gradient(ellipse at 100% 100%, #000 0%, transparent 62%); }
  .card { position: absolute; inset: 72px 80px; display: flex; justify-content: space-between; align-items: stretch; }
  .copy { display: flex; flex-direction: column; justify-content: space-between; max-width: 700px; }
  .kicker { font-size: 22px; color: #9fb0c2; letter-spacing: .01em; margin: 34px 0 0; }
  h1 { font-size: 60px; line-height: 1.06; font-weight: 500; letter-spacing: -0.035em; margin: 26px 0 0; }
  .foot { display: flex; gap: 12px; align-items: center; font-size: 21px; color: #9fb0c2; }
  .pill { background: rgba(233,237,242,.08); border: 1px solid rgba(233,237,242,.14); border-radius: 999px; padding: 8px 18px; color: #e9edf2; }
  .chart { align-self: flex-end; }
</style></head><body><div class="dots"></div>
<div class="card">
  <div class="copy">
    <div>${wordmark}<p class="kicker">Open-weight models, measured on real office work</p>
    <h1>Which open models can you trust with real work?</h1></div>
    <div class="foot"><span class="pill">Quality</span><span class="pill">Cost</span><span class="pill">Speed</span><span class="pill">Safety</span></div>
  </div>
  <div class="chart">${chart}</div>
</div></body></html>`;

const chrome = process.env.CHROME
  ?? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].find((p) => fs.existsSync(p));
if (!chrome) throw new Error('No Chrome found; set CHROME to a Chrome or Chromium binary.');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'owb-og-'));
const page = path.join(dir, 'og.html');
fs.writeFileSync(page, html);
execFileSync(chrome, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1', '--window-size=1200,630',
  '--virtual-time-budget=6000', `--user-data-dir=${path.join(dir, 'profile')}`, `--screenshot=${out}`, `file://${page}`], { stdio: 'ignore' });
fs.rmSync(dir, { recursive: true, force: true });
console.log(`wrote ${path.relative(site, out)}`);
