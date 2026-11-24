// Gera previsões fictícias para testes (a página usa as reais).
import { readFileSync, writeFileSync } from 'node:fs';
import { polygonToCells, cellToLatLng } from 'h3-js';

const RES = 7;
const geo = JSON.parse(readFileSync(new URL('../src/geo/rmsp-municipios.json', import.meta.url)));

let seed = 20250701;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
const ruido = (amp) => 1 + (rnd() * 2 - 1) * amp;

const meses = [];
for (let i = 0; i < 12; i++) {
  const ano = 2025 + Math.floor((6 + i) / 12);
  const mes = ((6 + i) % 12) + 1;
  meses.push(`${ano}-${String(mes).padStart(2, '0')}`);
}
const alvos = [
  { id: 'crime', nome: 'Crime total' },
  { id: 'furto', nome: 'Furto' },
  { id: 'roubo', nome: 'Roubo' },
];
const N_HEX = 1260;

const focos = [
  [-46.636, -23.548, 1.0, 1.8],
  [-46.615, -23.543, 0.6, 1.4],
  [-46.656, -23.563, 0.55, 1.4],
  [-46.69, -23.566, 0.35, 1.5],
  [-46.705, -23.65, 0.35, 2.0],
  [-46.457, -23.54, 0.3, 2.5],
  [-46.77, -23.67, 0.3, 2.5],
  [-46.533, -23.663, 0.4, 2.0],
  [-46.565, -23.694, 0.35, 2.0],
  [-46.533, -23.462, 0.4, 2.5],
  [-46.792, -23.532, 0.4, 2.0],
  [-46.188, -23.523, 0.3, 2.0],
  [-46.62, -23.686, 0.3, 1.5],
  [-46.31, -23.54, 0.25, 1.8],
  [-46.835, -23.6, 0.2, 1.5],
];
const km = (a, b, c, d) => {
  const x = (c - a) * 111.32 * Math.cos((b * Math.PI) / 180);
  const y = (d - b) * 110.57;
  return Math.hypot(x, y);
};

const sazon = meses.map((m) => ({ 12: 1.12, 1: 0.95, 2: 1.08, 7: 1.0, 10: 1.04 })[Number(m.slice(5, 7))] ?? 1);
const idxCarnaval = meses.indexOf('2026-02');

const candidatos = [];
for (const f of geo.features) {
  const { codigo } = f.properties;
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  const cells = new Set();
  for (const p of polys) for (const c of polygonToCells(p, RES, true)) cells.add(c);
  for (const h of cells) {
    const [lat, lng] = cellToLatLng(h);
    const dCentro = km(-46.636, -23.548, lng, lat);
    let base = 1.6 * Math.exp(-((dCentro / 16) ** 2)) + 0.25;
    for (const [fx, fy, w, r] of focos) base += 9 * w * Math.exp(-((km(fx, fy, lng, lat) / r) ** 2));
    base *= 14 * ruido(0.45);
    const partRoubo = Math.min(0.75, Math.max(0.25, 0.3 + dCentro / 60 + (rnd() - 0.5) * 0.15));
    candidatos.push({ h3: h, municipio: codigo, base, partRoubo, dCentro });
  }
}
candidatos.sort((a, b) => b.base - a.base);
const escolhidos = candidatos.slice(0, N_HEX);

const contagens = escolhidos.map((c) => {
  const crime = meses.map((_, i) => {
    let v = c.base * sazon[i] * ruido(0.15);
    if (i === idxCarnaval && c.dCentro < 2.5) v *= 1.25;
    return Math.max(0, v);
  });
  const roubo = crime.map((v) => v * c.partRoubo * ruido(0.1));
  const furto = crime.map((v, i) => Math.max(0, v - roubo[i]));
  return { crime, furto, roubo };
});

const p90 = (xs) => {
  const ord = xs.filter((x) => x > 0).sort((a, b) => a - b);
  return ord[Math.floor(0.9 * (ord.length - 1))];
};
const K = Object.fromEntries(alvos.map(({ id }) => [id, p90(contagens.flatMap((c) => c[id]))]));
const r3 = (x) => Math.round(x * 1000) / 1000;
const hexagonos = escolhidos.map((c, i) => ({
  h3: c.h3,
  municipio: c.municipio,
  risco: Object.fromEntries(alvos.map(({ id }) => [id, contagens[i][id].map((v) => r3(v / (v + K[id])))])),
}));

writeFileSync(
  new URL('../src/data/previsoes.json', import.meta.url),
  JSON.stringify({
    fonte: 'mock',
    geradoEm: new Date().toISOString().slice(0, 10),
    resolucaoH3: RES,
    unidade: 'nota de risco de 0 a 1 por hexágono e por mês',
    meses,
    alvos,
    hexagonos,
  }),
);

console.log(`hexágonos: ${hexagonos.length}, meses: ${meses.length}, K:`, K);
