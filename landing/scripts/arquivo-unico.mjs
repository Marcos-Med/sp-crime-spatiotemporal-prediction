// Junta o site compilado em um único HTML.
import { readFileSync, writeFileSync } from 'node:fs';
const css = readFileSync(new URL('../dist/assets/index.css', import.meta.url), 'utf8');
const js = readFileSync(new URL('../dist/assets/app.js', import.meta.url), 'utf8').replace(/<\/script/gi, '<\\/script');
let html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8');
html = html
  .replace(/<script type="module"[^>]*><\/script>\s*/, '')
  .replace(/<link rel="stylesheet"[^>]*index\.css">/, () => `<style>${css}</style>`)
  .replace('</body>', () => `<script type="module">${js}</script>\n</body>`);
writeFileSync(new URL('../landing-rp2-pronto.html', import.meta.url), html);
console.log('ok: landing-rp2-pronto.html', (html.length / 1e6).toFixed(1), 'MB');
